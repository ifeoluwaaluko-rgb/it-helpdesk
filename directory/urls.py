from django.urls import path
from . import views
urlpatterns = [
    path('directory/', views.staff_list, name='staff_list'),
    path('directory/create/', views.staff_create, name='staff_create'),
    path('directory/import/', views.import_staff, name='import_staff'),
    path('directory/template/', views.download_template, name='staff_template'),
    path('directory/<int:pk>/', views.staff_detail, name='staff_detail'),
    path('directory/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
]
