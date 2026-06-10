from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:query_id>/<str:fmt>/', views.ExportView.as_view(), name='export'),
]
