from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.users.permissions import IsViewer
from apps.datasets.models import Dataset
from apps.query.models import QueryHistory
from apps.query.serializers import NL2SQLQuerySerializer, QueryHistorySerializer
from apps.query.services.nl2sql import NL2SQLService


class NL2SQLQueryView(APIView):
    """自然语言查询接口"""
    permission_classes = [IsViewer]

    def post(self, request, dataset_id):
        serializer = NL2SQLQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']

        # 数据集可见性：与 DatasetViewSet.get_queryset 分层一致
        # admin 任意、analyst 只查自己的、viewer 只查被分享的
        user = request.user
        if user.is_admin:
            dataset = Dataset.objects.filter(id=dataset_id).first()
        elif user.is_analyst:
            dataset = Dataset.objects.filter(id=dataset_id, owner=user).first()
        else:  # viewer
            from django.db.models import Q
            dataset = Dataset.objects.filter(
                Q(owner=user) | Q(shares__shared_to=user)
            ).filter(id=dataset_id).distinct().first()

        if dataset is None:
            return Response(
                {'error': '数据集不存在或无权访问'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if dataset.status != 'completed':
            return Response(
                {'error': '数据集尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST
            )

        service = NL2SQLService(dataset)
        result = service.query(question)

        # 记录查询历史（成功查询持久化前 20 行预览，失败留 null）
        is_success = result.get('success', False)
        data = result.get('data', []) if is_success else []
        history = QueryHistory.objects.create(
            dataset=dataset,
            user=request.user,
            question=question,
            generated_sql=result.get('sql', ''),
            is_success=is_success,
            error_message=result.get('error', ''),
            execution_time_ms=result.get('execution_time_ms'),
            result_count=len(data),
            result_preview=data[:20] if data else None,
            result_columns=list(data[0].keys()) if data else None,
        )

        result['query_id'] = str(history.id)
        return Response(result)


class QueryHistoryView(APIView):
    """查询历史列表"""
    permission_classes = [IsViewer]

    def get(self, request):
        queryset = QueryHistory.objects.filter(
            user=request.user
        ).select_related('dataset').order_by('-created_at')

        dataset_id = request.query_params.get('dataset_id')
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)

        try:
            page = int(request.query_params.get('page', 1))
        except (ValueError, TypeError):
            page = 1
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()
        records = queryset[start:end]

        serializer = QueryHistorySerializer(records, many=True)
        return Response({
            'count': total,
            'results': serializer.data,
            'page': page,
            'page_size': page_size,
        })


class QueryRerunView(APIView):
    """重跑历史查询：用历史记录里的 SQL 重新执行，返回完整结果（不落库）。

    场景：查询历史只存前 20 行预览，用户想看完整结果时点重跑。
    项目是"上传快照"模式，数据集不变，重跑结果与当时一致，所以无需缓存。
    复用 ExportService.execute_query（已含自动 LIMIT 1000）。
    """
    permission_classes = [IsViewer]

    def post(self, request, history_id):
        # 1. 取历史记录（按 user 隔离，只能重跑自己的）
        try:
            history = QueryHistory.objects.get(id=history_id, user=request.user)
        except QueryHistory.DoesNotExist:
            return Response(
                {'error': '查询记录不存在'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. 校验：只有当时成功的查询才能重跑
        if not history.is_success:
            return Response(
                {'error': '该查询当时执行失败，无法重跑'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. 校验：数据集是否还在（被删除的不能重跑）
        if not history.dataset or history.dataset.status != 'completed':
            return Response(
                {'error': '数据集已不存在或状态异常，无法重跑'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 4. 重跑：复用 ExportService（已含自动 LIMIT 1000）
        from apps.export.services.exporter import ExportService
        try:
            data = ExportService.execute_query(history.generated_sql)
        except Exception as e:
            return Response(
                {'error': f'重跑失败：{e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 5. 返回完整结果（不存）
        return Response({
            'history_id': str(history.id),
            'question': history.question,
            'generated_sql': history.generated_sql,
            'data': data,
            'row_count': len(data),
        })
