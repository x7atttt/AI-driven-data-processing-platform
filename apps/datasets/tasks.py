from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=0,
    acks_late=True,
)
def process_large_file(self, dataset_id: str):
    """异步处理大文件（>=10MB）

    指数退避重试：2^n 秒（1→2→4→8→16），最多5次。
    超过5次标记为 failed（死信队列），Admin 后台可见。
    """
    from apps.datasets.models import Dataset, DataRow
    from apps.datasets.services.parser import clean_dataframe
    import pandas as pd

    try:
        dataset = Dataset.objects.get(id=dataset_id)
        dataset.status = 'processing'
        dataset.save(update_fields=['status', 'updated_at'])

        chunk_size = 10000
        total_rows = 0
        file_path = dataset.file.path

        if dataset.file_name.endswith('.csv'):
            reader = pd.read_csv(file_path, chunksize=chunk_size)
        else:
            df = pd.read_excel(file_path)
            reader = [df.iloc[i:i + chunk_size] for i in range(0, len(df), chunk_size)]

        for chunk_df in reader:
            chunk_df = clean_dataframe(chunk_df)

            rows = [
                DataRow(dataset=dataset, row_index=total_rows + i, data=row.to_dict())
                for i, row in chunk_df.iterrows()
            ]
            DataRow.objects.bulk_create(rows, batch_size=1000)

            total_rows += len(chunk_df)
            _send_progress(dataset_id, total_rows)

        dataset.row_count = total_rows
        dataset.status = 'completed'
        dataset.save(update_fields=['row_count', 'status', 'updated_at'])

    except Exception as exc:
        logger.error(f'处理数据集 {dataset_id} 失败: {exc}')

        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return

        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            logger.info(f'重试 {self.request.retries + 1}/{self.max_retries}，等待 {countdown}秒')
            raise self.retry(exc=exc, countdown=countdown)
        else:
            dataset.status = 'failed'
            dataset.save(update_fields=['status', 'updated_at'])
            logger.error(f'数据集 {dataset_id} 重试{self.max_retries}次后仍然失败，进入死信队列')


def _send_progress(dataset_id: str, total_rows: int):
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'dataset_{dataset_id}',
            {
                'type': 'progress_update',
                'progress': total_rows,
                'status': 'processing',
                'message': f'已处理 {total_rows} 行',
            },
        )
    except Exception:
        pass
