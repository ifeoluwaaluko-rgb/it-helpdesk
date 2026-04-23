from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from tickets.models import Profile

from .models import StaffMember


class DirectorySecurityTests(TestCase):
    endpoint = '/api/staff/search/'

    def setUp(self):
        self.agent = User.objects.create_user(
            username='diragent',
            password='pass1234',
            is_staff=True,
        )
        Profile.objects.update_or_create(user=self.agent, defaults={'role': 'associate'})
        self.regular_user = User.objects.create_user(
            username='outsider',
            password='pass1234',
        )
        Profile.objects.update_or_create(user=self.regular_user, defaults={'role': 'associate'})
        StaffMember.objects.create(
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
        )

    def test_staff_search_requires_login(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 302)

    def test_staff_search_rejects_non_staff_users(self):
        self.client.login(username='outsider', password='pass1234')
        response = self.client.get(self.endpoint, {'q': 'ja'})
        self.assertEqual(response.status_code, 403)

    def test_staff_search_allows_helpdesk_staff(self):
        self.client.login(username='diragent', password='pass1234')
        response = self.client.get(self.endpoint, {'q': 'ja'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'jane@example.com')

    def test_staff_create_rejects_short_first_name(self):
        self.client.login(username='diragent', password='pass1234')
        response = self.client.post(
            reverse('staff_create'),
            {'first_name': 'J', 'last_name': 'Doe', 'email': 'jd@example.com'},
            follow=True,
        )
        self.assertContains(response, 'First name must be at least 2 characters long.')

    def test_staff_create_rejects_non_helpdesk_users(self):
        self.client.login(username='outsider', password='pass1234')
        response = self.client.post(
            reverse('staff_create'),
            {'first_name': 'John', 'last_name': 'Doe', 'email': 'john@example.com'},
            follow=True,
        )
        self.assertContains(response, 'Only helpdesk staff can manage the staff directory.')
        self.assertFalse(StaffMember.objects.filter(email='john@example.com').exists())

    def test_staff_import_rejects_non_csv_upload(self):
        self.client.login(username='diragent', password='pass1234')
        bad_file = SimpleUploadedFile('staff.txt', b'not-csv', content_type='text/plain')
        response = self.client.post(reverse('import_staff'), {'file': bad_file}, follow=True)
        self.assertContains(response, 'Please upload a CSV file.')

    def test_staff_import_rejects_non_helpdesk_users(self):
        self.client.login(username='outsider', password='pass1234')
        csv_file = SimpleUploadedFile(
            'staff.csv',
            b'first_name,last_name,email\nJohn,Doe,john@example.com\n',
            content_type='text/csv',
        )
        response = self.client.post(reverse('import_staff'), {'file': csv_file}, follow=True)
        self.assertContains(response, 'Only helpdesk staff can manage the staff directory.')
        self.assertFalse(StaffMember.objects.filter(email='john@example.com').exists())
