from django.urls import path

from apps.users.api.views import (
    RegisterView,
    LoginView,
    LogoutView,
    ProfileView,
    UserListView,
    UserManageView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('profile/', ProfileView.as_view(), name='user-profile'),
    path('manage/', UserListView.as_view(), name='user-list'),
    path('manage/<int:pk>/', UserManageView.as_view(), name='user-manage'),
]
