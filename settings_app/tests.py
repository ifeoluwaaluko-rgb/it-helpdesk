from django.contrib.auth.models import User
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from tickets.models import Profile
from .models import IntegrationConfig
from .services import get_imap_runtime_config, get_smtp_runtime_config


class SettingsAccessTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='manager1',
            password='pass1234',
            is_staff=True,
        )
        Profile.objects.update_or_create(user=self.manager, defaults={'role': 'manager'})
        self.agent = User.objects.create_user(
            username='agent1',
            password='pass1234',
            is_staff=True,
        )
        Profile.objects.update_or_create(user=self.agent, defaults={'role': 'associate'})

    def test_non_manager_cannot_access_settings_home(self):
        self.client.login(username='agent1', password='pass1234')
        response = self.client.get(reverse('settings_home'), follow=True)
        self.assertContains(response, 'Access denied. Only Managers can manage integrations.')

    def test_manager_can_access_settings_home(self):
        self.client.login(username='manager1', password='pass1234')
        response = self.client.get(reverse('settings_home'))
        self.assertEqual(response.status_code, 200)

    def test_manager_can_save_openai_settings(self):
        self.client.login(username='manager1', password='pass1234')
        response = self.client.post(
            reverse('save_openai'),
            {'host': 'https://api.openai.com/v1', 'model_name': 'gpt-4o-mini', 'access_token': 'sk-test', 'is_active': 'on'},
            follow=True,
        )
        cfg = IntegrationConfig.objects.get(integration='openai')
        self.assertEqual(cfg.host, 'https://api.openai.com/v1')
        self.assertEqual(cfg.username, 'gpt-4o-mini')
        self.assertTrue(cfg.is_active)
        self.assertContains(response, 'AI provider settings saved.')

    def test_manager_cannot_save_invalid_webhook_url(self):
        self.client.login(username='manager1', password='pass1234')
        response = self.client.post(
            reverse('save_generic_webhook'),
            {'host': 'Automation', 'webhook_url': 'not-a-url', 'is_active': 'on'},
            follow=True,
        )
        self.assertContains(response, 'Webhook URL must be a valid http or https URL.')

    def test_manager_cannot_save_invalid_smtp_port(self):
        self.client.login(username='manager1', password='pass1234')
        response = self.client.post(
            reverse('save_smtp'),
            {'host': 'smtp.example.com', 'port': '99999', 'username': 'it@example.com', 'password': 'secret', 'is_active': 'on'},
            follow=True,
        )
        self.assertContains(response, 'SMTP port must be between 1 and 65535.')

    @override_settings(
        EMAIL_HOST='smtp.env.local',
        EMAIL_PORT=2525,
        EMAIL_HOST_USER='env-user',
        EMAIL_HOST_PASSWORD='env-pass',
        DEFAULT_FROM_EMAIL='support@example.com',
    )
    def test_smtp_runtime_config_falls_back_to_environment(self):
        runtime = get_smtp_runtime_config()
        self.assertEqual(runtime.host, 'smtp.env.local')
        self.assertEqual(runtime.port, 2525)
        self.assertEqual(runtime.username, 'env-user')
        self.assertEqual(runtime.password, 'env-pass')
        self.assertEqual(runtime.from_email, 'support@example.com')
        self.assertTrue(runtime.enabled)

    @override_settings(
        EMAIL_HOST='smtp.env.local',
        EMAIL_PORT=2525,
        EMAIL_HOST_USER='env-user',
        EMAIL_HOST_PASSWORD='env-pass',
        DEFAULT_FROM_EMAIL='support@example.com',
    )
    def test_smtp_runtime_config_prefers_active_database_config(self):
        cfg = IntegrationConfig.objects.create(
            integration='email_smtp',
            host='smtp.db.local',
            port=587,
            username='db-user',
            is_active=True,
            updated_by=self.manager,
        )
        cfg.password = 'db-pass'
        cfg.save()

        runtime = get_smtp_runtime_config()
        self.assertEqual(runtime.host, 'smtp.db.local')
        self.assertEqual(runtime.port, 587)
        self.assertEqual(runtime.username, 'db-user')
        self.assertEqual(runtime.password, 'db-pass')
        self.assertTrue(runtime.enabled)

    @override_settings(
        IMAP_HOST='imap.env.local',
        IMAP_PORT=993,
        IMAP_USER='env-imap',
        IMAP_PASSWORD='env-secret',
        IMAP_FOLDER='Inbox',
    )
    def test_imap_runtime_config_falls_back_to_environment(self):
        runtime = get_imap_runtime_config()
        self.assertEqual(runtime.host, 'imap.env.local')
        self.assertEqual(runtime.port, 993)
        self.assertEqual(runtime.username, 'env-imap')
        self.assertEqual(runtime.password, 'env-secret')
        self.assertEqual(runtime.folder, 'Inbox')
        self.assertTrue(runtime.enabled)
