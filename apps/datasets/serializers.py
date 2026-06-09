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
        extra_kwargs = {
            'file': {'write_only': True, 'required': True},
            'name': {'required': False},
            'description': {'required': False},
        }
