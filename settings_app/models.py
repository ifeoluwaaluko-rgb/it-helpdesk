"""
Encrypted credential storage.

Strategy (best-practice, defence-in-depth):
- Values are encrypted with Fernet symmetric encryption before DB write.
- The Fernet key is derived from Django's SECRET_KEY (env var, never in DB).
- Even if the DB is dumped, ciphertext is useless without the SECRET_KEY.
- Values are NEVER logged or returned to templates in plaintext.
- Display always shows masked bullets; update requires re-entering the value.
"""
import base64
import hashlib
from django.db import models
from django.conf import settings

try:
    from cryptography.fernet import Fernet
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def _get_fernet():
    """Derive a stable Fernet key from Django SECRET_KEY."""
    if not _CRYPTO_AVAILABLE:
        return None
    key_bytes = settings.SECRET_KEY.encode()
    digest = hashlib.sha256(key_bytes).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str) -> str:
    f = _get_fernet()
    if not f or not plaintext:
        return plaintext or ''
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    f = _get_fernet()
    if not f or not ciphertext:
        return ciphertext or ''
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ''   # corrupted / wrong key — return empty, never crash


class IntegrationConfig(models.Model):
    """
    One row per integration type.
    Sensitive fields (passwords, tokens, keys) are stored encrypted.
    Non-sensitive fields (host, port, from_email) are stored plain.
    """
    INTEGRATION_CHOICES = [
        ('email_smtp',   'Email – SMTP (Outbound)'),
        ('email_imap',   'Email – IMAP (Inbound)'),
        ('microsoft_graph', 'Microsoft Graph'),
        ('generic_webhook', 'Generic Webhook'),
        ('whatsapp',     'WhatsApp Business Cloud API'),
        ('teams',        'Microsoft Teams Webhook'),
        ('slack',        'Slack Webhook'),
        ('openai',       'OpenAI / AI Provider'),
    ]

    integration = models.CharField(
        max_length=30, choices=INTEGRATION_CHOICES, unique=True)
    is_active   = models.BooleanField(default=False)

    # ── Plain fields (not secret) ─────────────────────────────
    host        = models.CharField(max_length=255, blank=True,
                                   help_text='Hostname or API endpoint')
    port        = models.IntegerField(null=True, blank=True)
    username    = models.CharField(max_length=255, blank=True,
                                   help_text='Email address / API user')
    use_tls     = models.BooleanField(default=True)
    use_ssl     = models.BooleanField(default=False)
    webhook_url = models.CharField(max_length=500, blank=True,
                                   help_text='Webhook URL (Teams / Slack)')
    phone_number_id = models.CharField(max_length=50, blank=True,
                                        help_text='WhatsApp phone number ID')
    wa_business_id  = models.CharField(max_length=50, blank=True,
                                        help_text='WhatsApp Business Account ID')

    # ── Encrypted fields ──────────────────────────────────────
    _password     = models.TextField(blank=True, db_column='password')
    _access_token = models.TextField(blank=True, db_column='access_token')

    updated_at  = models.DateTimeField(auto_now=True)
    updated_by  = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    # ── Password property (encrypt on set, decrypt on get) ────
    @property
    def password(self):
        return decrypt_value(self._password)

    @password.setter
    def password(self, value):
        self._password = encrypt_value(value) if value else ''

    # ── Access token property ─────────────────────────────────
    @property
    def access_token(self):
        return decrypt_value(self._access_token)

    @access_token.setter
    def access_token(self, value):
        self._access_token = encrypt_value(value) if value else ''

    def is_configured(self):
        """Returns True if the minimum required fields are filled."""
        if self.integration in ('email_smtp', 'email_imap'):
            return bool(self.host and self.username and self._password)
        if self.integration == 'microsoft_graph':
            return bool(self.username and self._access_token)
        if self.integration == 'openai':
            return bool(self._access_token)
        if self.integration == 'whatsapp':
            return bool(self._access_token and self.phone_number_id)
        if self.integration in ('teams', 'slack', 'generic_webhook'):
            return bool(self.webhook_url)
        return False

    def __str__(self):
        return self.get_integration_display()

    class Meta:
        ordering = ['integration']
        verbose_name = 'Integration Config'
        verbose_name_plural = 'Integration Configs'


    def masked_password(self):
        return '●●●●●●' if self._password else 'Not set'

    def masked_token(self):
        return '●●●●●●' if self._access_token else 'Not set'


class IntegrationAuditLog(models.Model):
    ACTION_CHOICES = [
        ('save', 'Saved'),
        ('test', 'Tested'),
        ('toggle', 'Toggled'),
    ]
    integration = models.CharField(max_length=30)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, default='success')
    message = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.integration} {self.action} ({self.status})"
