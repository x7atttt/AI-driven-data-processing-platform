import io

import pandas as pd
from django.db import connection


class ExportService:
    """数据导出服务

    根据 QueryHistory 中记录的 SQL 重新执行查询，导出为 CSV/Excel。
    不持久化查询结果，避免存储大量数据。
    """

    @staticmethod
    def execute_query(sql: str) -> list:
        """重新执行历史查询 SQL，返回结果列表"""
        if 'LIMIT' not in sql.upper():
            sql = sql.rstrip(';') + ' LIMIT 1000'
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        # 复用 nl2sql 的净化逻辑，保证 Decimal/datetime 可被 JSON 序列化
        from apps.query.services.nl2sql import _sanitize_for_json
        return [_sanitize_for_json(dict(zip(columns, row))) for row in rows]

    @staticmethod
    def export_csv(data: list) -> bytes:
        df = pd.DataFrame(data)
        return df.to_csv(index=False).encode('utf-8-sig')

    @staticmethod
    def export_excel(data: list) -> bytes:
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='查询结果')
        return buffer.getvalue()
