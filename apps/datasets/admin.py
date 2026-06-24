from django.contrib import admin
from .models import Dataset, DataRow, DatasetShare


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'row_count', 'file_size', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'file_name')
    readonly_fields = ('file_md5', 'row_count', 'column_count')
    ordering = ('-created_at',)


@admin.register(DataRow)
class DataRowAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'row_index', 'created_at')
    readonly_fields = ('dataset', 'row_index', 'data')
    ordering = ('dataset', 'row_index')


@admin.register(DatasetShare)
class DatasetShareAdmin(admin.ModelAdmin):
    """数据集分享记录后台：analyst 分享数据集给 viewer 的授权关系。"""
    list_display = ('dataset', 'shared_to', 'shared_by', 'permission', 'created_at')
    list_filter = ('permission',)
    search_fields = ('dataset__name', 'shared_to__username', 'shared_by__username')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
