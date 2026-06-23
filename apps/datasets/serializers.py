from rest_framework import serializers

from apps.datasets.models import Dataset


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = [
            'id', 'name', 'description', 'file', 'file_name', 'file_size',
            'row_count', 'column_count', 'status',
            'owner', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'file_name', 'file_size',
            'row_count', 'column_count', 'status', 'owner',
            'created_at', 'updated_at',
        ]
        #这段是在给 Django REST Framework 的序列化器补充字段级别的输入规则，
        # 作用是控制前端提交数据时哪些字段必须填、哪些字段只允许写入但不回传。
        extra_kwargs = {
            'file': {'write_only': True, 'required': True},
            'name': {'required': False},
            'description': {'required': False},
        }
