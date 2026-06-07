from django.contrib import admin
from .models import Dataset, DataRow


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
