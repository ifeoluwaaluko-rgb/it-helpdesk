from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda r: redirect('dashboard')),
    path('', include('tickets.urls')),
    path('', include('knowledge.urls')),
    path('', include('directory.urls')),
    path('', include('assets.urls')),
]
