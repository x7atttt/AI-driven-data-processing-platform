from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from apps.users.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'phone')

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'phone', 'is_active', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class ChangeRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('role',)
