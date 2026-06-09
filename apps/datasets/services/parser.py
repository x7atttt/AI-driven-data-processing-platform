import pandas as pd

from apps.datasets.models import Dataset, DataRow


ALLOWED_EXTENSIONS = ('.csv', '.xlsx', '.xls')


def parse_file_sync(dataset: Dataset) -> None:
    """同步解析文件（<10MB）"""
    try:
        dataset.status = 'processing'
        dataset.save(update_fields=['status', 'updated_at'])

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
        return pd.read_csv(path)
    elif file_name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(path)
    raise ValueError(f'不支持的文件格式: {file_name}')


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='ignore')

    df = df.where(pd.notnull(df), None)
    return df


def bulk_create_rows(dataset: Dataset, df: pd.DataFrame, batch_size: int = 1000):
    rows = []
    for index, row in df.iterrows():
        rows.append(
            DataRow(
                dataset=dataset,
                row_index=index,
                data=row.to_dict(),
            )
        )
        if len(rows) >= batch_size:
            DataRow.objects.bulk_create(rows, batch_size=batch_size)
            rows = []

    if rows:
        DataRow.objects.bulk_create(rows, batch_size=batch_size)
