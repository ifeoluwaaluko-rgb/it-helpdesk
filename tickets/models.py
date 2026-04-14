from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    ROLES = [
        ('associate', 'Associate'),
        ('consultant', 'Consultant'),
        ('senior', 'Senior'),
        ('manager', 'Manager'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLES, default='associate')
    specialization = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
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
    LEVEL_CHOICES = [
        ('associate', 'Associate'),
        ('consultant', 'Consultant'),
        ('senior', 'Senior'),
        ('manager', 'Manager'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    user_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    required_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='associate')
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    raw_email = models.TextField(blank=True)
    sla_hours = models.IntegerField(default=24)

    def __str__(self):
        return f"#{self.id} - {self.title}"

    @property
    def sla_deadline(self):
        return self.created_at + timezone.timedelta(hours=self.sla_hours)

    @property
    def is_sla_breached(self):
        if self.status in ['resolved', 'closed']:
            return False
        return timezone.now() > self.sla_deadline

    @property
    def sla_remaining_seconds(self):
        """Positive = time left. Negative = overdue."""
        delta = self.sla_deadline - timezone.now()
        return int(delta.total_seconds())

    @property
    def resolution_time_hours(self):
        if self.resolved_at:
            delta = self.resolved_at - self.created_at
            return round(delta.total_seconds() / 3600, 1)
        return None

    class Meta:
        ordering = ['-created_at']


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_internal = models.BooleanField(default=True)

    def __str__(self):
        return f"Comment by {self.author.username} on #{self.ticket.id}"

    class Meta:
        ordering = ['created_at']
