from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

urlpatterns = [
    path('admin/', admin.site.urls),

    # Smart homepage
    path('', home_redirect),

    # App routes
    path('', include('tickets.urls')),
    path('', include('knowledge.urls')),
    path('', include('directory.urls')),
    path('', include('assets.urls')),
]