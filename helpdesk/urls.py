from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from tickets.views import protected_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='landing.html'), name='landing'),
    path('', include('tickets.urls')),
    path('', include('knowledge.urls')),
    path('', include('directory.urls')),
    path('', include('assets.urls')),
    path('', include('settings_app.urls')),
    path('media/<path:path>', protected_media, name='protected_media'),
]
