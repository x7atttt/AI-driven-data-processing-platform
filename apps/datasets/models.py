import uuid
from django.db import models
from django.conf import settings


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='数据集名称')
    description = models.TextField(blank=True, verbose_name='描述')
    file = models.FileField(upload_to='datasets/%Y%m/', verbose_name='上传文件')
    file_name = models.CharField(max_length=255, verbose_name='原始文件名')
    file_size = models.BigIntegerField(verbose_name='文件大小(字节)')
    file_md5 = models.CharField(max_length=32, verbose_name='文件MD5')
    row_count = models.IntegerField(default=0, verbose_name='数据行数')
    column_count = models.IntegerField(default=0, verbose_name='列数')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待处理'),
            ('processing', '处理中'),
            ('completed', '已完成'),
            ('failed', '处理失败'),
        ],
        default='pending',
        verbose_name='处理状态',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='datasets',
        verbose_name='所属用户',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'datasets'
        verbose_name = '数据集'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['owner', 'created_at'], name='idx_dataset_owner_created'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'file_md5'], name='uq_dataset_owner_md5'),
        ]


class DataRow(models.Model):
    id = models.BigAutoField(primary_key=True)
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name='rows'
    )
    row_index = models.IntegerField(verbose_name='行号')
    data = models.JSONField(verbose_name='行数据')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dataset_rows'
        verbose_name = '数据行'
        verbose_name_plural = verbose_name  # 中文无复数，直接复用单数名
        indexes = [
            models.Index(
                fields=['dataset', 'row_index'], name='idx_datarow_dataset_row'
            ),
        ]
        constraints = [
            models.UniqueConstraint(fields=['dataset', 'row_index'], name='uq_datarow_dataset_rowindex'),
        ]


class DatasetShare(models.Model):
    """数据集分享记录：analyst 把数据集授权给指定 viewer。

    对齐 Superset/Metabase 的 Viewer 授权机制——viewer 默认看不到任何
    数据集，必须被 analyst 显式分享才能查询。
    """
    PERMISSION_CHOICES = [
        ('query', '可查询'),
    ]  # 当前只有 query 一种，预留扩展（未来可加 read-only 等）

    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name='shares',
        verbose_name='数据集',
    )
    shared_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='shared_datasets', verbose_name='被分享用户',
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='shared_by_me', verbose_name='分享人',
    )
    permission = models.CharField(
        max_length=10, choices=PERMISSION_CHOICES, default='query',
        verbose_name='权限',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='分享时间')

    class Meta:
        db_table = 'dataset_shares'
        verbose_name = '数据集分享'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['dataset', 'shared_to'],
                name='uq_dataset_share',  # 同一数据集对同一用户只分享一次
            )
        ]


