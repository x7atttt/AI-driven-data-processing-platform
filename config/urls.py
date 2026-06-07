from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.api.urls')),
    path('api/datasets/', include('apps.datasets.api.urls')),
    path('api/query/', include('apps.query.api.urls')),
    path('api/export/', include('apps.export.api.urls')),
]
