from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', '管理员'
        ANALYST = 'analyst', '分析师'
        VIEWER = 'viewer', '只读用户'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.VIEWER,
        verbose_name='角色',
    )
    phone = models.CharField(max_length=11, blank=True, verbose_name='手机号')

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_analyst(self):
        return self.role == self.Role.ANALYST

    @property
    def is_viewer(self):
        return self.role == self.Role.VIEWER
