from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from tickets.models import Profile

from .models import Article


class KnowledgeSecurityTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='kbagent',
            password='pass1234',
            is_staff=True,
        )
        Profile.objects.update_or_create(user=self.agent, defaults={'role': 'associate'})
        self.regular_user = User.objects.create_user(
            username='reader',
            password='pass1234',
        )
        Profile.objects.update_or_create(user=self.regular_user, defaults={'role': 'associate'})
        self.article = Article.objects.create(
            title='Reset MFA',
            content='<p>Safe</p>',
            created_by=self.agent,
            last_modified_by=self.agent,
        )

    def test_non_staff_cannot_edit_article(self):
        self.client.login(username='reader', password='pass1234')
        response = self.client.get(reverse('edit_article', args=[self.article.pk]), follow=True)
        self.assertContains(response, 'Only helpdesk staff can edit knowledge articles.')

    def test_article_html_is_sanitized_on_save(self):
        self.client.login(username='kbagent', password='pass1234')
        self.client.post(
            reverse('edit_article', args=[self.article.pk]),
            {
                'title': 'Reset MFA',
                'content': '<p>Hello</p><script>alert(1)</script><a href="javascript:alert(2)">bad</a>',
                'category': 'other',
                'tags': '',
            },
        )
        self.article.refresh_from_db()
        self.assertNotIn('<script', self.article.content)
        self.assertNotIn('javascript:', self.article.content)

    def test_create_article_rejects_short_title(self):
        self.client.login(username='kbagent', password='pass1234')
        response = self.client.post(
            reverse('create_article'),
            {
                'title': 'Bad',
                'content': '<p>This is long enough content for validation.</p>',
                'category': 'other',
                'tags': '',
            },
            follow=True,
        )
        self.assertContains(response, 'Article title must be at least 5 characters long.')

    def test_create_article_rejects_invalid_attachment_type(self):
        self.client.login(username='kbagent', password='pass1234')
        bad_file = SimpleUploadedFile('payload.exe', b'fake-binary', content_type='application/octet-stream')
        response = self.client.post(
            reverse('create_article'),
            {
                'title': 'Reset MFA steps',
                'content': '<p>This article content is long enough to save.</p>',
                'category': 'other',
                'tags': '',
                'attachments': bad_file,
            },
            follow=True,
        )
        self.assertContains(response, 'attachment type is not allowed')

    def test_edit_article_rejects_short_content(self):
        self.client.login(username='kbagent', password='pass1234')
        response = self.client.post(
            reverse('edit_article', args=[self.article.pk]),
            {
                'title': 'Reset MFA',
                'content': 'short',
                'category': 'other',
                'tags': '',
                'revision_note': '',
            },
            follow=True,
        )
        self.assertContains(response, 'Article content must be at least 10 characters long.')
