
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tickets.models import Profile
from settings_app.models import IntegrationConfig


class SettingsPermissionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='manager', password='manager', is_staff=True)
        Profile.objects.create(user=self.manager, role='manager')

    def test_save_imap_config(self):
        self.client.login(username='manager', password='manager')
        response = self.client.post(reverse('save_imap'), {
            'host': 'imap.gmail.com',
            'port': '993',
            'username': 'it@example.com',
            'password': 'secret',
            'is_active': 'on',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        cfg = IntegrationConfig.objects.get(integration='email_imap')
        self.assertEqual(cfg.host, 'imap.gmail.com')
        self.assertTrue(cfg.is_active)
