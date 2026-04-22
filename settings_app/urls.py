from django.urls import path
from . import views

urlpatterns = [
    path('settings/',                          views.settings_home,    name='settings_home'),
    path('settings/smtp/',                     views.save_smtp,        name='save_smtp'),
    path('settings/imap/',                     views.save_imap,        name='save_imap'),
    path('settings/whatsapp/',                 views.save_whatsapp,    name='save_whatsapp'),
    path('settings/teams/',                    views.save_teams,       name='save_teams'),
    path('settings/slack/',                    views.save_slack,       name='save_slack'),
    path('settings/test/<str:integration>/',   views.test_connection,  name='test_connection'),
]
