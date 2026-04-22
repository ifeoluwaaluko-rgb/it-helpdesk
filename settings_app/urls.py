from django.urls import path
from . import views

urlpatterns = [
    path('settings/', views.settings_home, name='settings_home'),
    path('settings/smtp/', views.save_smtp, name='save_smtp'),
    path('settings/imap/', views.save_imap, name='save_imap'),
    path('settings/graph/', views.save_graph, name='save_graph'),
    path('settings/webhook/', views.save_generic_webhook, name='save_generic_webhook'),
    path('settings/whatsapp/', views.save_whatsapp, name='save_whatsapp'),
    path('settings/teams/', views.save_teams, name='save_teams'),
    path('settings/slack/', views.save_slack, name='save_slack'),
    path('settings/openai/', views.save_openai, name='save_openai'),
    path('settings/test/<str:integration>/', views.test_connection, name='test_connection'),
]
