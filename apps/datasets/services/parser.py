import pandas as pd
from django.db import transaction#保证数据库原子性

from apps.datasets.models import Dataset, DataRow


ALLOWED_EXTENSIONS = ('.csv', '.xlsx', '.xls')

# 数据集规模上限（匹配项目"中小数据集自助分析"定位）
# 文件大小上限在 views.py 的 MAX_FILE_SIZE 单独定义
MAX_ROWS_PER_DATASET = 100_000        # 10 万行
MAX_COLUMNS_PER_DATASET = 100         # 100 列


class DatasetTooLargeError(ValueError):
    """数据集规模超限异常（行数/列数）"""
    pass


def validate_dataframe_size(df: pd.DataFrame) -> None:
    """校验 DataFrame 规模，超限抛 DatasetTooLargeError。

    同步路径（parse_file_sync）和异步路径（tasks.process_large_file）
    都调用此函数，保证两条路径的上限逻辑一致。
    """
    row_count = len(df)
    if row_count > MAX_ROWS_PER_DATASET:
        raise DatasetTooLargeError(
            f'数据集 {row_count} 行超过上限 {MAX_ROWS_PER_DATASET} 行，'
            f'请拆分或筛选后上传'
        )
    col_count = len(df.columns)
    if col_count > MAX_COLUMNS_PER_DATASET:
        raise DatasetTooLargeError(
            f'数据集 {col_count} 列超过上限 {MAX_COLUMNS_PER_DATASET} 列，'
            f'请删减列后上传'
        )


def delete_dataset_completely(dataset: Dataset) -> None:
    """彻底清理 dataset：删除文件 + 删除记录。

    超限等不可恢复的错误用此函数清理，避免留下 failed 状态的垃圾记录
    和 media 目录的残留文件。同步路径和异步路径共用。
    """
    # 失效 schema 缓存（数据集要删了）
    from apps.datasets.services.analyzer import invalidate_schema_cache
    try:
        invalidate_schema_cache(dataset.id)
    except Exception:
        pass  # 缓存清理失败不阻塞删除主流程
    # 先删文件（file.delete(save=False) 不触发 ORM save，避免循环）
    try:
        dataset.file.delete(save=False)
    except Exception:
        pass
    dataset.delete()


def parse_file_sync(dataset: Dataset) -> None:
    """同步解析文件（<10MB）"""
    try:
        dataset.status = 'processing'
        dataset.save(update_fields=['status', 'updated_at'])#保存指定字段
        
        with transaction.atomic():
            df = _read_file(dataset.file.path, dataset.file_name)
            validate_dataframe_size(df)
            df = clean_dataframe(df)
            bulk_create_rows(dataset, df)

            dataset.row_count = len(df)
            dataset.column_count = len(df.columns)
            dataset.status = 'completed'
            dataset.save(update_fields=['row_count', 'column_count', 'status', 'updated_at'])

    except DatasetTooLargeError:
        # 超限是不可恢复的，清理 dataset 记录和文件，避免留下垃圾
        delete_dataset_completely(dataset)
        raise
    except Exception:
        # 其他失败（如解析错误）保留 failed 记录，便于在 Admin 排查
        dataset.status = 'failed'
        dataset.save(update_fields=['status', 'updated_at'])
        raise

# 以下为工具函数
def _read_file(path: str, file_name: str) -> pd.DataFrame:
    if file_name.endswith('.csv'):
        return pd.read_csv(path, index_col=False)
    elif file_name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(path)
    raise ValueError(f'不支持的文件格式: {file_name}')


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """列名规范化、类型尽量数值化、非法/空值统一化。"""
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])  # 尝试把这一整列转成数字
        except (ValueError, TypeError):
            # 无法转换为数值类型，跳过
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


