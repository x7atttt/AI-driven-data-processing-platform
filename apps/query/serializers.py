from rest_framework import serializers
from .models import QueryHistory


class NL2SQLQuerySerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=1000,
        required=True,
        help_text='自然语言查询问题',
    )


class QueryHistorySerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(
        source='dataset.name', read_only=True
    )

    class Meta:
        model = QueryHistory
        fields = (
            'id', 'dataset', 'dataset_name', 'question',
            'generated_sql', 'is_success', 'error_message',
            'execution_time_ms', 'created_at',
        )
        read_only_fields = fields
