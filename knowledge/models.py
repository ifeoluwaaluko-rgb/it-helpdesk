from django.db import models
from django.contrib.auth.models import User


class Article(models.Model):
    CATEGORY_CHOICES = [
        ('network', 'Network'),
        ('access', 'Access / Permissions'),
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('email', 'Email'),
        ('password', 'Password Reset'),
        ('printer', 'Printer'),
        ('onboarding', 'Onboarding'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    tags = models.CharField(max_length=255, blank=True, help_text='Comma-separated tags')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_articles'
    )
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_articles'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_ticket = models.ForeignKey(
        'tickets.Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='articles'
    )
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)

    def __str__(self):
        return self.title

    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    class Meta:
        ordering = ['-updated_at']


class ArticleRevision(models.Model):
    """Snapshot saved every time an article is edited."""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='revisions')
    title = models.CharField(max_length=255)
    content = models.TextField()
    tags = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=30)
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    edited_at = models.DateTimeField(auto_now_add=True)
    revision_note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Rev #{self.pk} of '{self.article.title}' by {self.edited_by}"

    class Meta:
        ordering = ['-edited_at']


class ArticleFeedback(models.Model):
    """Track who voted so users can only vote once."""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='feedback')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('article', 'user')
