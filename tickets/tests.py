from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Profile, Ticket
from .analytics import build_dashboard_metrics, calculate_agent_productivity


class TicketSecurityTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='agent',
            password='pass1234',
            is_staff=True,
        )
        Profile.objects.update_or_create(user=self.agent, defaults={'role': 'associate'})
        self.regular_user = User.objects.create_user(
            username='employee',
            password='pass1234',
        )
        Profile.objects.update_or_create(user=self.regular_user, defaults={'role': 'associate'})
        self.ticket = Ticket.objects.create(
            title='VPN access issue',
            description='Cannot connect to the VPN',
            user_email='user@example.com',
        )

    def test_login_redirect_blocks_external_next_url(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'agent', 'password': 'pass1234', 'next': 'https://evil.example/phish'},
        )
        self.assertRedirects(response, reverse('dashboard'))

    def test_non_staff_cannot_edit_ticket(self):
        self.client.login(username='employee', password='pass1234')
        response = self.client.post(
            reverse('ticket_detail', args=[self.ticket.pk]),
            {'action': 'update_status', 'status': 'resolved'},
            follow=True,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'open')
        self.assertContains(response, 'Only helpdesk staff can update tickets.')

    def test_staff_can_update_ticket_status(self):
        self.client.login(username='agent', password='pass1234')
        response = self.client.post(
            reverse('ticket_detail', args=[self.ticket.pk]),
            {'action': 'update_status', 'status': 'resolved'},
        )
        self.assertRedirects(response, reverse('ticket_detail', args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'resolved')

    def test_staff_can_update_ticket_category(self):
        self.client.login(username='agent', password='pass1234')
        response = self.client.post(
            reverse('ticket_detail', args=[self.ticket.pk]),
            {'action': 'update_category', 'category': 'network', 'subcategory': 'VPN', 'item': 'Cisco AnyConnect'},
            follow=True,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.category, 'network')
        self.assertEqual(self.ticket.subcategory, 'VPN')
        self.assertContains(response, 'Category updated.')

    def test_ticket_create_rejects_short_description(self):
        self.client.login(username='agent', password='pass1234')
        response = self.client.post(
            reverse('create_ticket'),
            {
                'title': 'VPN broken',
                'description': 'Too short',
                'user_email': 'user@example.com',
                'channel': 'manual',
            },
            follow=True,
        )
        self.assertContains(response, 'Description must be at least 10 characters long.')

    def test_ticket_create_rejects_disallowed_attachment_type(self):
        self.client.login(username='agent', password='pass1234')
        bad_file = SimpleUploadedFile('payload.exe', b'fake-binary', content_type='application/octet-stream')
        response = self.client.post(
            reverse('create_ticket'),
            {
                'title': 'VPN is failing badly',
                'description': 'A detailed description of the VPN issue.',
                'user_email': 'user@example.com',
                'channel': 'manual',
                'attachment': bad_file,
            },
            follow=True,
        )
        self.assertContains(response, 'Attachment type is not allowed.')

    def test_ticket_edit_rejects_short_title(self):
        self.client.login(username='agent', password='pass1234')
        response = self.client.post(
            reverse('ticket_edit', args=[self.ticket.pk]),
            {
                'title': 'Bad',
                'description': 'A sufficiently detailed replacement description.',
                'category': self.ticket.category,
                'subcategory': '',
                'item': '',
                'priority': 'medium',
                'tags': 'vpn',
                'edit_note': 'Testing validation',
            },
            follow=True,
        )
        self.assertContains(response, 'Title must be at least 5 characters long.')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.title, 'VPN access issue')

    def test_ticket_comment_rejects_blank_body(self):
        self.client.login(username='agent', password='pass1234')
        response = self.client.post(
            reverse('ticket_detail', args=[self.ticket.pk]),
            {'action': 'comment', 'body': '   '},
            follow=True,
        )
        self.assertContains(response, 'Comment cannot be empty.')
        self.assertEqual(self.ticket.comments.count(), 0)

    def test_dashboard_metrics_summary_counts(self):
        Ticket.objects.create(
            title='Resolved issue',
            description='This issue is fully resolved now.',
            user_email='resolved@example.com',
            status='resolved',
            assigned_to=self.agent,
            resolved_at=timezone.now(),
        )
        metrics = build_dashboard_metrics(Ticket.objects.all())
        self.assertEqual(metrics['total'], 2)
        self.assertEqual(metrics['open'], 1)
        self.assertEqual(metrics['resolved'], 1)

    def test_agent_productivity_summary(self):
        Ticket.objects.create(
            title='Closed issue',
            description='This issue is now closed after some work.',
            user_email='closed@example.com',
            status='closed',
            assigned_to=self.agent,
        )
        metrics = calculate_agent_productivity(Ticket.objects.all(), self.agent)
        self.assertEqual(metrics['resolved'], 1)
        self.assertEqual(metrics['total_assigned'], 1)
        self.assertEqual(metrics['productivity'], 100)
