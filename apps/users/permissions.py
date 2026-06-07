from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    message = '需要管理员权限'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsAnalyst(BasePermission):
    message = '需要分析师权限'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (
            'admin', 'analyst'
        )


class IsViewer(BasePermission):
    message = '需要至少只读权限'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (
            'admin', 'analyst', 'viewer'
        )
