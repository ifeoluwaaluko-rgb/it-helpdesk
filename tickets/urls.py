from django.urls import path
from . import views
urlpatterns = [
    path('setup/', views.first_time_setup, name='first_time_setup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('live/', views.live_dashboard, name='live_dashboard'),
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/create/', views.create_ticket, name='create_ticket'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'),
    path('tickets/<int:pk>/delete/', views.ticket_delete, name='ticket_delete'),
    path('tickets/<int:pk>/history/', views.ticket_history, name='ticket_history'),
    path('api/staff/search/', views.staff_search_api, name='staff_search_api'),
    path('api/subcategories/', views.subcategory_api, name='subcategory_api'),
    path('api/items/', views.item_api, name='item_api'),
]
