from rest_framework import serializers


class ExportQuerySerializer(serializers.Serializer):
    query_id = serializers.UUIDField(
        required=True,
        help_text='查询历史记录ID',
    )
    format = serializers.ChoiceField(
        choices=['csv', 'xlsx'],
        default='csv',
        help_text='导出格式',
    )
