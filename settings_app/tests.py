from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tickets.models import Profile


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='manager', password='manager', is_staff=True)
        Profile.objects.create(user=self.user, role='manager')

    def test_settings_page_loads(self):
        self.client.login(username='manager', password='manager')
        response = self.client.get(reverse('settings_home'))
        self.assertEqual(response.status_code, 200)
