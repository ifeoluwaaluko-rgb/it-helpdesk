from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from directory.models import StaffMember
from tickets.models import Profile

from .models import Asset


class AssetAccessTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='assetagent',
            password='pass1234',
            is_staff=True,
        )
        Profile.objects.update_or_create(user=self.agent, defaults={'role': 'associate'})
        self.regular_user = User.objects.create_user(
            username='assetviewer',
            password='pass1234',
        )
        Profile.objects.update_or_create(user=self.regular_user, defaults={'role': 'associate'})
        self.asset = Asset.objects.create(
            asset_id='LAPTOP-001',
            name='Dell XPS 15',
            created_by=self.agent,
        )
        self.staff_member = StaffMember.objects.create(
            first_name='Jane',
            last_name='Doe',
            email='jane.asset@example.com',
        )

    def test_non_staff_cannot_open_asset_create_flow(self):
        self.client.login(username='assetviewer', password='pass1234')
        response = self.client.get(reverse('asset_create'), follow=True)
        self.assertContains(response, 'Only helpdesk staff can register assets.')

    def test_non_staff_cannot_update_asset(self):
        self.client.login(username='assetviewer', password='pass1234')
        response = self.client.post(
            reverse('asset_detail', args=[self.asset.pk]),
            {'action': 'status', 'status': 'retired'},
            follow=True,
        )
        self.asset.refresh_from_db()
        self.assertNotEqual(self.asset.status, 'retired')
        self.assertContains(response, 'Only helpdesk staff can update assets.')

    def test_asset_create_rejects_short_asset_id(self):
        self.client.login(username='assetagent', password='pass1234')
        response = self.client.post(
            reverse('asset_create'),
            {'asset_id': 'A', 'name': 'Laptop', 'status': 'active'},
            follow=True,
        )
        self.assertContains(response, 'Asset ID must be at least 3 characters long.')

    def test_asset_import_rejects_non_csv_upload(self):
        self.client.login(username='assetagent', password='pass1234')
        bad_file = SimpleUploadedFile('assets.txt', b'bad-data', content_type='text/plain')
        response = self.client.post(reverse('asset_import'), {'file': bad_file}, follow=True)
        self.assertContains(response, 'Please upload a CSV file.')

    def test_asset_assignment_rejects_invalid_staff_id(self):
        self.client.login(username='assetagent', password='pass1234')
        response = self.client.post(
            reverse('asset_detail', args=[self.asset.pk]),
            {'action': 'assign', 'staff_id': '99999'},
            follow=True,
        )
        self.assertContains(response, 'Invalid staff selection.')
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.assigned_to)

    def test_log_incident_rejects_short_title(self):
        self.client.login(username='assetagent', password='pass1234')
        response = self.client.post(
            reverse('log_incident', args=[self.asset.pk]),
            {'title': 'Bad', 'severity': 'medium', 'description': 'Something happened.'},
            follow=True,
        )
        self.assertContains(response, 'Incident title must be at least 5 characters long.')

    def test_staff_can_assign_asset_with_valid_staff_member(self):
        self.client.login(username='assetagent', password='pass1234')
        response = self.client.post(
            reverse('asset_detail', args=[self.asset.pk]),
            {'action': 'assign', 'staff_id': str(self.staff_member.pk)},
            follow=True,
        )
        self.assertContains(response, 'Assignment updated.')
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to, self.staff_member)
