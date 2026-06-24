import hashlib

from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.users.permissions import IsAnalyst, IsViewer
from apps.datasets.models import Dataset
from apps.datasets.serializers import DatasetSerializer
from apps.datasets.services.upload_lock import UploadLockService
from apps.datasets.services.parser import ALLOWED_EXTENSIONS

SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB，与 Nginx client_max_body_size 对齐


class DatasetViewSet(viewsets.ModelViewSet):
    """数据集管理接口：上传/列表/详情/删除"""

    serializer_class = DatasetSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'destroy', 'share'):
            return [IsAnalyst()]
        return [IsViewer()]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            # admin 看全部（管理需要）
            return Dataset.objects.all().order_by('-created_at')
        if user.is_analyst:
            # analyst 只看自己上传的
            return Dataset.objects.filter(owner=user).order_by('-created_at')
        # viewer：只看被分享给自己的（核心修复 viewer 死锁）
        return Dataset.objects.filter(
            shares__shared_to=user
        ).distinct().order_by('-created_at')

    def create(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请选择文件'}, status=status.HTTP_400_BAD_REQUEST
            )

        ext = _get_extension(file.name)
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {'error': f'不支持的文件格式，仅支持 {", ".join(ALLOWED_EXTENSIONS)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 文件大小校验（与 Nginx client_max_body_size 对齐，
        # 本地开发无 Nginx 时这层兜底，保证本地/生产行为一致）
        if file.size > MAX_FILE_SIZE:
            return Response(
                {'error': f'文件超过 {MAX_FILE_SIZE // 1024 // 1024}MB 上限'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        # 流式计算 MD5
        file_md5 = _compute_md5(file)
        file.seek(0)

        lock_service = UploadLockService()
        user_id = request.user.id

        # 先获取分布式锁，再查库（避免并发请求都通过 is_duplicate）
        if not lock_service.try_acquire_lock(user_id, file_md5):
            return Response(
                {'error': '该文件正在处理中'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            # 在锁内查库，保证原子性
            if lock_service.is_duplicate(user_id, file_md5):
                return Response(
                    {'error': '该文件已存在', 'file_md5': file_md5},
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                dataset = Dataset.objects.create(
                    name=request.data.get('name') or file.name,
                    description=request.data.get('description', ''),
                    file=file,
                    file_name=file.name,
                    file_size=file.size,
                    file_md5=file_md5,
                    owner=request.user,
                )
            except IntegrityError:
                return Response(
                    {'error': '该文件已存在'},
                    status=status.HTTP_409_CONFLICT,
                )

            if file.size < SMALL_FILE_THRESHOLD:
                from apps.datasets.services.parser import parse_file_sync
                parse_file_sync(dataset)
            else:
                from apps.datasets.tasks import process_large_file
                process_large_file.delay(str(dataset.id))

            serializer = DatasetSerializer(dataset)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        finally:
            lock_service.release_lock(user_id, file_md5)

    def destroy(self, request, *args, **kwargs):
        dataset = self.get_object()
        dataset.file.delete(save=False)
        dataset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='analysis')
    def analysis(self, request, pk=None):
        """数据集分析统计"""
        dataset = self.get_object()
        if dataset.status != 'completed':
            return Response(
                {'error': '数据集尚未处理完成'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.datasets.services.analyzer import (
            get_dataset_overview, get_column_stats,
        )
        return Response({
            'overview': get_dataset_overview(dataset),
            'column_stats': get_column_stats(dataset),
        })

    @action(detail=True, methods=['post'], url_path='share')
    def share(self, request, pk=None):
        """analyst 把数据集分享给指定用户（viewer）。

        分享 = 可见性授权：viewer 默认看不到任何数据集，必须被 analyst
        显式分享后才能查询。对齐 Superset/Metabase 的 Viewer 授权机制。
        """
        dataset = self.get_object()  # 走 get_queryset，analyst 只能分享自己的

        target_user_id = request.data.get('user_id')
        if not target_user_id:
            return Response(
                {'error': '请提供 user_id'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User
        try:
            target = User.objects.get(id=target_user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {'error': '目标用户不存在'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if target.id == request.user.id:
            return Response(
                {'error': '不能分享给自己'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.datasets.models import DatasetShare
        share, created = DatasetShare.objects.get_or_create(
            dataset=dataset,
            shared_to=target,
            defaults={'shared_by': request.user, 'permission': 'query'},
        )
        if not created:
            return Response(
                {'message': '已分享过，无需重复'},
                status=status.HTTP_200_OK,
            )
        return Response(
            {'message': f'已分享给 {target.username}'},
            status=status.HTTP_201_CREATED,
        )


def _compute_md5(file) -> str:
    md5_hash = hashlib.md5()
    for chunk in file.chunks():
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


def _get_extension(filename: str) -> str:
    return '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
