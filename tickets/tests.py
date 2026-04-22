
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from tickets.models import Profile, Ticket, TicketEvent
from settings_app.models import IntegrationConfig


class TicketFlowTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='manager', password='manager', is_staff=True)
        Profile.objects.create(user=self.manager, role='manager')

    def test_dashboard_loads_for_logged_in_user(self):
        self.client.login(username='manager', password='manager')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_create_ticket_creates_event(self):
        self.client.login(username='manager', password='manager')
        resp = self.client.post(reverse('create_ticket'), {
            'title': 'Laptop issue',
            'description': 'Blue screen on startup',
            'user_email': 'user@example.com',
            'channel': 'manual',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        ticket = Ticket.objects.latest('id')
        self.assertTrue(TicketEvent.objects.filter(ticket=ticket, event_type='created').exists())

    def test_status_update_logs_event(self):
        ticket = Ticket.objects.create(title='VPN broken', description='Cannot connect', user_email='u@example.com')
        self.client.login(username='manager', password='manager')
        resp = self.client.post(reverse('ticket_detail', args=[ticket.pk]), {'action': 'update_status', 'status': 'resolved'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'resolved')
        self.assertTrue(TicketEvent.objects.filter(ticket=ticket, event_type='resolved').exists())


class IntegrationTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='manager', password='manager', is_staff=True)
        Profile.objects.create(user=self.manager, role='manager')

    def test_settings_page_loads(self):
        self.client.login(username='manager', password='manager')
        resp = self.client.get(reverse('settings_home'))
        self.assertEqual(resp.status_code, 200)

    @patch('tickets.email_ingestion.fetch_and_create_tickets', return_value=0)
    def test_fetch_emails_command_runs(self, mocked):
        from django.core.management import call_command
        call_command('fetch_emails')
        mocked.assert_called()
