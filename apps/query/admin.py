from django.contrib import admin
from .models import QueryHistory


@admin.register(QueryHistory)
class QueryHistoryAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'user', 'question_short', 'is_success', 'created_at')
    list_filter = ('is_success', 'created_at')#右侧会出现筛选器，可以按“是否成功”和“创建时间”过滤记录
    search_fields = ('question', 'generated_sql')#顶部搜索框会支持按问题文本和生成的 SQL 搜索。
    readonly_fields = ('dataset', 'user', 'question', 'generated_sql', 'error_message')
    ordering = ('-created_at',)

    @admin.display(description='问题')
    def question_short(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
