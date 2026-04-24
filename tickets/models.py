from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    ROLES = [('associate','Associate'),('consultant','Consultant'),('senior','Senior'),('manager','Manager'),('superadmin','Super Admin')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLES, default='associate')
    specialization = models.CharField(max_length=100, blank=True)
    def __str__(self): return f"{self.user.username} ({self.get_role_display()})"


# ── 3-Level Category System ──────────────────────────────────────────────────
class TicketCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    icon = models.CharField(max_length=10, default='🔧')
    required_level = models.CharField(max_length=20, default='associate')
    sla_hours = models.IntegerField(default=24)
    class Meta: ordering = ['name']
    def __str__(self): return self.name


class TicketSubcategory(models.Model):
    category = models.ForeignKey(TicketCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    class Meta: ordering = ['name']; unique_together = ('category', 'name')
    def __str__(self): return f"{self.category.name} → {self.name}"


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open','Open'),('in_progress','In Progress'),
        ('pending','Pending – Awaiting User'),
        ('resolved','Resolved'),('closed','Closed'),
    ]
    PRIORITY_CHOICES = [('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')]
    CATEGORY_CHOICES = [
        ('network','Network'),('access','Access / Permissions'),('hardware','Hardware'),
        ('software','Software'),('email','Email'),('password','Password Reset'),
        ('printer','Printer'),('onboarding','Onboarding'),('other','Other'),
    ]
    LEVEL_CHOICES = [('associate','Associate'),('consultant','Consultant'),('senior','Senior'),('manager','Manager')]
    CHANNEL_CHOICES = [
        ('email','Email'),('walk_in','Walk-in'),
        ('phone','Phone Call'),('chat','Chat (WhatsApp/Teams/Slack)'),('manual','Manual Entry'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    user_email = models.EmailField()
    requester_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # 3-level category
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    subcategory = models.CharField(max_length=100, blank=True)
    item = models.CharField(max_length=200, blank=True)

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='manual')
    required_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='associate')
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets'
    )
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_tickets'
    )
    watchers = models.ManyToManyField(User, blank=True, related_name='watched_tickets')
    tags = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    sla_paused_at = models.DateTimeField(null=True, blank=True)
    sla_pause_seconds = models.IntegerField(default=0)
    raw_email = models.TextField(blank=True)
    external_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    sla_hours = models.IntegerField(default=24)
    merged_into = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='merged_tickets'
    )
    csat_score = models.IntegerField(null=True, blank=True)
    escalated = models.BooleanField(default=False)

    def __str__(self): return f"#{self.id} - {self.title}"

    @property
    def sla_deadline(self):
        base = self.created_at + timezone.timedelta(hours=self.sla_hours)
        return base + timezone.timedelta(seconds=self.sla_pause_seconds)

    @property
    def is_sla_breached(self):
        if self.status in ['resolved', 'closed']: return False
        if self.sla_paused_at: return False
        return timezone.now() > self.sla_deadline

    @property
    def sla_remaining_seconds(self):
        return int((self.sla_deadline - timezone.now()).total_seconds())

    @property
    def resolution_time_seconds(self):
        if self.resolved_at:
            return int((self.resolved_at - self.created_at).total_seconds())
        return None

    @property
    def resolution_time_hours(self):
        if self.resolved_at:
            return round((self.resolved_at - self.created_at).total_seconds() / 3600, 1)
        return None

    @property
    def first_response_seconds(self):
        if self.first_response_at:
            return int((self.first_response_at - self.created_at).total_seconds())
        return None

    @property
    def first_response_minutes(self):
        if self.first_response_at:
            return round((self.first_response_at - self.created_at).total_seconds() / 60, 1)
        return None

    @property
    def sla_progress_ratio(self):
        total_seconds = max(self.sla_hours * 3600, 1)
        elapsed = (timezone.now() - self.created_at).total_seconds() - self.sla_pause_seconds
        return max(0, min(elapsed / total_seconds, 1))

    @property
    def sla_state(self):
        if self.status in ['resolved', 'closed']:
            return 'resolved'
        if self.is_sla_breached:
            return 'red'
        remaining_ratio = max(self.sla_remaining_seconds, 0) / max(self.sla_hours * 3600, 1)
        return 'green' if remaining_ratio > 0.5 else 'yellow'

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def category_display(self):
        parts = [self.get_category_display()]
        if self.subcategory: parts.append(self.subcategory)
        if self.item: parts.append(self.item)
        return ' → '.join(parts)

    class Meta: ordering = ['-created_at']


class TicketEditHistory(models.Model):
    """Snapshot saved every time a ticket is edited."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='edit_history')
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    edited_at = models.DateTimeField(auto_now_add=True)
    # Snapshot of fields before edit
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=30)
    subcategory = models.CharField(max_length=100, blank=True)
    item = models.CharField(max_length=200, blank=True)
    priority = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    edit_note = models.CharField(max_length=255, blank=True)

    class Meta: ordering = ['-edited_at']
    def __str__(self): return f"Edit of #{self.ticket.id} by {self.edited_by} at {self.edited_at}"


class TicketEvent(models.Model):
    EVENT_TYPES = [
        ('created', 'Created'),
        ('commented', 'Commented'),
        ('assigned', 'Assigned'),
        ('reassigned', 'Reassigned'),
        ('status_changed', 'Status changed'),
        ('resolved', 'Resolved'),
        ('category_changed', 'Category changed'),
        ('edited', 'Edited'),
        ('email_received', 'Email received'),
    ]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=40, choices=EVENT_TYPES)
    message = models.CharField(max_length=500, blank=True)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_event_type_display()} on #{self.ticket_id}"


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_internal = models.BooleanField(default=True)
    class Meta: ordering = ['created_at']


class CannedResponse(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    category = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    class Meta: ordering = ['title']
    def __str__(self): return self.title


class EscalationRule(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, blank=True)
    priority = models.CharField(max_length=20, blank=True)
    hours_without_update = models.IntegerField(default=4)
    escalate_to_role = models.CharField(max_length=20, default='senior')
    is_active = models.BooleanField(default=True)
    class Meta: ordering = ['name']
    def __str__(self): return self.name


class TicketAttachment(models.Model):
    """File/image attached to a ticket — from email or manual upload."""
    ticket       = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    file         = models.FileField(upload_to='ticket_attachments/')
    filename     = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    is_image     = models.BooleanField(default=False)
    uploaded_at  = models.DateTimeField(auto_now_add=True)
    source       = models.CharField(max_length=20, default='email',
                                    choices=[('email','Email'),('manual','Manual')])

    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name.split('/')[-1]
        import mimetypes
        mime, _ = mimetypes.guess_type(self.filename or '')
        self.is_image = bool(mime and mime.startswith('image/'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.filename} → Ticket #{self.ticket.id}"

    class Meta:
        ordering = ['uploaded_at']
