from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, Ticket, TicketEvent


class TicketFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='manager', password='manager', is_staff=True)
        Profile.objects.create(user=self.user, role='manager')

    def test_dashboard_loads(self):
        self.client.login(username='manager', password='manager')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_ticket_create_logs_event(self):
        self.client.login(username='manager', password='manager')
        response = self.client.post(reverse('create_ticket'), {
            'title': 'Cannot access VPN',
            'description': 'VPN does not connect.',
            'user_email': 'user@example.com',
            'channel': 'manual',
        })
        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.first()
        self.assertIsNotNone(ticket)
        self.assertTrue(TicketEvent.objects.filter(ticket=ticket, event_type='created').exists())

    def test_status_update_logs_event(self):
        self.client.login(username='manager', password='manager')
        ticket = Ticket.objects.create(title='Issue', description='Desc', user_email='user@example.com')
        response = self.client.post(reverse('ticket_detail', args=[ticket.pk]), {'action': 'update_status', 'status': 'resolved'})
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'resolved')
        self.assertEqual(ticket.resolved_by, self.user)
        self.assertTrue(TicketEvent.objects.filter(ticket=ticket, event_type='resolved').exists())
