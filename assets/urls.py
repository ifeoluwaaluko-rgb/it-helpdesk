from django.urls import path
from . import views
urlpatterns = [
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/create/', views.asset_create, name='asset_create'),
    path('assets/import/', views.bulk_import, name='asset_import'),
    path('assets/template/', views.asset_template, name='asset_template'),
    path('assets/<int:pk>/', views.asset_detail, name='asset_detail'),
    path('assets/<int:asset_pk>/incident/', views.log_incident, name='log_incident'),
]
