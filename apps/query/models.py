import uuid
from django.db import models
from django.conf import settings


class QueryHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        'datasets.Dataset', on_delete=models.CASCADE, related_name='queries'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='queries'
    )
    question = models.TextField(verbose_name='自然语言问题')
    generated_sql = models.TextField(verbose_name='生成的SQL')
    is_success = models.BooleanField(default=False, verbose_name='是否成功')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    execution_time_ms = models.IntegerField(null=True, verbose_name='执行时间(ms)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'query_history'
        verbose_name = '查询历史'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=['dataset', 'created_at'],
                name='idx_query_dataset_created',
            ),
        ]
