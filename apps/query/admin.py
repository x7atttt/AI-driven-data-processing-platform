from django.contrib import admin
from .models import QueryHistory


@admin.register(QueryHistory)
class QueryHistoryAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'user', 'question_short', 'is_success', 'created_at')
    list_filter = ('is_success', 'created_at')
    search_fields = ('question', 'generated_sql')
    readonly_fields = ('dataset', 'user', 'question', 'generated_sql', 'error_message')
    ordering = ('-created_at',)

    @admin.display(description='问题')
    def question_short(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
