import json
import logging

import pandas as pd

from apps.datasets.models import Dataset, DataRow

logger = logging.getLogger(__name__)

MAX_ROWS = 50000


def _load_dataframe(dataset: Dataset, max_rows: int = MAX_ROWS) -> dict:
    """从 DataRow 加载数据到 DataFrame

    Returns:
        {'df': DataFrame, 'types': dict, 'total_rows': int, 'sampled': bool}
    """
    rows = []
    total_rows = 0
    for data in (
        DataRow.objects.filter(dataset=dataset)
        .order_by('row_index')
        .values_list('data', flat=True)
        .iterator(chunk_size=1000)
    ):
        if total_rows >= max_rows:
            break
        rows.append(data)
        total_rows += 1

    actual_count = DataRow.objects.filter(dataset=dataset).count()
    sampled = actual_count > max_rows

    if not rows:
        return {
            'df': pd.DataFrame(),
            'types': {},
            'total_rows': 0,
            'sampled': False,
        }

    df = pd.DataFrame(rows)
    types = _classify_columns(df)

    return {
        'df': df,
        'types': types,
        'total_rows': actual_count,
        'sampled': sampled,
    }


def _classify_columns(df: pd.DataFrame) -> dict:
    """推断每列的数据类型"""
    types = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            types[col] = 'text'
            continue

        sample = series.head(100)
        has_bool = any(isinstance(v, bool) for v in sample)
        has_str = any(isinstance(v, str) for v in sample)

        if has_bool and not has_str:
            types[col] = 'boolean'
        elif has_str:
            types[col] = 'text'
        elif all(isinstance(v, int) for v in sample):
            types[col] = 'integer'
        else:
            types[col] = 'numeric'
    return types


def get_column_stats(dataset: Dataset) -> dict:
    """每列统计信息,给前端表格渲染"""
    if dataset.status != 'completed':
        return {'columns': [], 'total_rows': 0, 'sampled': False}

    loaded = _load_dataframe(dataset)
    df = loaded['df']
    types = loaded['types']

    if df.empty:
        return {
            'columns': [],
            'total_rows': 0,
            'sampled': False,
        }

    columns = []
    for col in df.columns:
        series = df[col]
        col_type = types.get(col, 'text')
        null_count = int(series.isna().sum())
        distinct_count = int(series.nunique())

        stats = {'null_count': null_count, 'distinct_count': distinct_count}

        if col_type in ('integer', 'numeric'):
            clean = pd.to_numeric(series, errors='coerce').dropna()
            if len(clean) > 0:
                stats['min'] = round(float(clean.min()), 2)
                stats['max'] = round(float(clean.max()), 2)
                stats['avg'] = round(float(clean.mean()), 2)
                stats['median'] = round(float(clean.median()), 2)
        elif col_type in ('text', 'boolean'):
            top = series.value_counts().head(10)
            stats['top_values'] = [
                {'value': str(v), 'count': int(c)} for v, c in top.items()
            ]

        columns.append({
            'name': col,
            'type': col_type,
            **stats,
        })

    return {
        'columns': columns,
        'total_rows': loaded['total_rows'],
        'sampled': loaded['sampled'],
    }


def get_schema_summary(dataset: Dataset) -> str:
    """生成结构化 schema 摘要，供 NL2SQL prompt 注入"""
    if dataset.status != 'completed':
        return '数据集尚未处理完成'

    loaded = _load_dataframe(dataset)
    df = loaded['df']
    types = loaded['types']

    if df.empty:
        return '数据集为空'

    lines = [
        f'Table: dataset_rows (共 {loaded["total_rows"]} 行)',
        '',
        'Columns:',
    ]

    for col in df.columns:
        col_type = types.get(col, 'text')
        series = df[col]
        distinct_count = int(series.nunique())

        if col_type in ('integer', 'numeric'):
            clean = pd.to_numeric(series, errors='coerce').dropna()
            if len(clean) > 0:
                lines.append(
                    f'  - {col} ({col_type}): '
                    f'min={round(float(clean.min()), 2)}, '
                    f'max={round(float(clean.max()), 2)}, '
                    f'avg={round(float(clean.mean()), 2)}, '
                    f'{distinct_count} distinct'
                )
            else:
                lines.append(f'  - {col} ({col_type}): all null')
        elif col_type == 'boolean':
            top = series.value_counts().head(2)
            parts = [f'{v}={int(c)}' for v, c in top.items()]
            lines.append(f'  - {col} ({col_type}): {", ".join(parts)}')
        else:
            top_vals = series.dropna().value_counts().head(5)
            top_str = ', '.join(str(v) for v in top_vals.index)
            lines.append(
                f'  - {col} ({col_type}): {distinct_count} distinct, top: {top_str}'
            )

    lines.append('')
    lines.append('Sample rows:')
    for _, row in df.head(3).iterrows():
        lines.append('  ' + json.dumps(row.to_dict(), ensure_ascii=False, default=str))

    if loaded['sampled']:
        lines.append('')
        lines.append(
            f'(Note: stats based on {len(df)} row sample of {loaded["total_rows"]} total)'
        )

    return '\n'.join(lines)


def get_dataset_overview(dataset: Dataset) -> dict:
    """数据集概览"""
    if dataset.status != 'completed':
        return {
            'row_count': 0,
            'column_count': 0,
            'columns': [],
            'status': dataset.status,
            'sampled': False,
        }

    loaded = _load_dataframe(dataset)
    df = loaded['df']

    if df.empty:
        return {
            'row_count': dataset.row_count,
            'column_count': dataset.column_count,
            'columns': [],
            'status': dataset.status,
            'null_summary': {},
            'sampled': False,
        }

    memory_mb = round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
    if loaded['sampled']:
        memory_mb = round(memory_mb * dataset.row_count / len(df), 2)

    return {
        'row_count': dataset.row_count,
        'column_count': dataset.column_count,
        'columns': list(df.columns),
        'status': dataset.status,
        'memory_estimate_mb': memory_mb,
        'null_summary': {
            col: int(df[col].isna().sum()) for col in df.columns
        },
        'sampled': loaded['sampled'],
    }
