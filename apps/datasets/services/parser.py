import pandas as pd
from django.db import transaction#保证数据库原子性

from apps.datasets.models import Dataset, DataRow


ALLOWED_EXTENSIONS = ('.csv', '.xlsx', '.xls')


def parse_file_sync(dataset: Dataset) -> None:
    """同步解析文件（<10MB）"""
    try:
        dataset.status = 'processing'
        dataset.save(update_fields=['status', 'updated_at'])#保存指定字段
        
        with transaction.atomic():
            df = _read_file(dataset.file.path, dataset.file_name)
            df = clean_dataframe(df)
            bulk_create_rows(dataset, df)

            dataset.row_count = len(df)
            dataset.column_count = len(df.columns)
            dataset.status = 'completed'
            dataset.save(update_fields=['row_count', 'column_count', 'status', 'updated_at'])

    except Exception:
        dataset.status = 'failed'
        dataset.save(update_fields=['status', 'updated_at'])
        raise


def _read_file(path: str, file_name: str) -> pd.DataFrame:
    if file_name.endswith('.csv'):
        return pd.read_csv(path, index_col=False)
    elif file_name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(path)
    raise ValueError(f'不支持的文件格式: {file_name}')


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass

    # astype(object) 确保数值列的 NaN/Inf 被替换为 Python None，兼容 JSONField
    df = df.astype(object).where(pd.notnull(df), None)
    df = df.replace([float('inf'), float('-inf')], None)
    return df


def bulk_create_rows(dataset: Dataset, df: pd.DataFrame, batch_size: int = 1000):
    records = df.to_dict('records')
    for i in range(0, len(records), batch_size):
        batch = [
            DataRow(
                dataset=dataset,
                row_index=i + j,
                data=rec,
            )
            for j, rec in enumerate(records[i:i + batch_size])
        ]
        DataRow.objects.bulk_create(batch, batch_size=batch_size)


