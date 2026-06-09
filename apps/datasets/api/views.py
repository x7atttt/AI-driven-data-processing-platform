import hashlib

from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.response import Response

from apps.users.permissions import IsAnalyst, IsViewer
from apps.datasets.models import Dataset
from apps.datasets.serializers import DatasetSerializer
from apps.datasets.services.upload_lock import UploadLockService
from apps.datasets.services.parser import ALLOWED_EXTENSIONS

SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB


class DatasetViewSet(viewsets.ModelViewSet):
    """数据集管理接口：上传/列表/详情/删除"""

    serializer_class = DatasetSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsAnalyst()]
        return [IsViewer()]

    def get_queryset(self):
        return Dataset.objects.filter(owner=self.request.user).order_by('-created_at')

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


def _compute_md5(file) -> str:
    md5_hash = hashlib.md5()
    for chunk in file.chunks():
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


def _get_extension(filename: str) -> str:
    return '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
