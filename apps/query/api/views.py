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

        try:
            dataset = Dataset.objects.get(
                id=dataset_id,
                owner=request.user,
            )
            
        except Dataset.DoesNotExist:
            return Response(
                {'error': '数据集不存在'}, status=status.HTTP_404_NOT_FOUND
            )

        if dataset.status != 'completed':
            return Response(
                {'error': '数据集尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST
            )

        service = NL2SQLService(dataset)
        result = service.query(question)

        # 记录查询历史
        history = QueryHistory.objects.create(
            dataset=dataset,
            user=request.user,
            question=question,
            generated_sql=result.get('sql', ''),
            is_success=result.get('success', False),
            error_message=result.get('error', ''),
            execution_time_ms=result.get('execution_time_ms'),
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
