from urllib.parse import quote

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.users.permissions import IsAnalyst
from apps.query.models import QueryHistory
from apps.export.services.exporter import ExportService


class ExportView(APIView):
    """数据导出接口（CSV/Excel）

    根据 query_id 重新执行历史 SQL 并导出。
    需要 analyst 及以上权限。
    """
    permission_classes = [IsAnalyst]

    def get(self, request, query_id, fmt):
        if fmt not in ('csv', 'xlsx'):
            return Response(
                {'error': '不支持的格式，仅支持 csv/xlsx'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            query = QueryHistory.objects.get(
                id=query_id,
                user=request.user,
            )
        except QueryHistory.DoesNotExist:
            return Response(
                {'error': '查询记录不存在'}, status=status.HTTP_404_NOT_FOUND
            )

        if not query.is_success:
            return Response(
                {'error': '该查询未成功执行，无法导出'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 重新执行 SQL 获取数据
        try:
            data = ExportService.execute_query(query.generated_sql)
        except Exception as e:
            return Response(
                {'error': f'重新执行查询失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not data:
            return Response(
                {'error': '查询结果为空，无法导出'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 导出
        dataset_name = query.dataset.name.replace(' ', '_')
        filename_csv = quote(f'{dataset_name}_result.csv')
        filename_xlsx = quote(f'{dataset_name}_result.xlsx')
        if fmt == 'csv':
            content = ExportService.export_csv(data)
            response = HttpResponse(content, content_type='text/csv')
            response['Content-Disposition'] = (
                f"attachment; filename*=UTF-8''{filename_csv}"
            )
        else:
            content = ExportService.export_excel(data)
            response = HttpResponse(
                content,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = (
                f"attachment; filename*=UTF-8''{filename_xlsx}"
            )

        return response
