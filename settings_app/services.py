import logging
from django.conf import settings
from .models import IntegrationConfig

logger = logging.getLogger(__name__)

INTEGRATION_KEYS = [
    'email_smtp',
    'email_imap',
    'microsoft_graph',
    'generic_webhook',
    'whatsapp',
    'teams',
    'slack',
    'openai',
]


class IntegrationConfigError(Exception):
    pass


def get_configs():
    configs = {}
    for key in INTEGRATION_KEYS:
        obj, _ = IntegrationConfig.objects.get_or_create(
            integration=key,
            defaults={'use_ssl': key == 'email_imap'}
        )
        configs[key] = obj
    return configs


def get_integration_config(key):
    obj, _ = IntegrationConfig.objects.get_or_create(
        integration=key,
        defaults={'use_ssl': key == 'email_imap'}
    )
    return obj


def get_smtp_runtime_config():
    cfg = get_integration_config('email_smtp')
    return {
        'enabled': bool(getattr(settings, 'EMAIL_ENABLED', False) and cfg.is_active and cfg.is_configured()),
        'host': cfg.host or getattr(settings, 'EMAIL_HOST', ''),
        'port': cfg.port or getattr(settings, 'EMAIL_PORT', 587),
        'username': cfg.username or getattr(settings, 'EMAIL_HOST_USER', ''),
        'password': cfg.password or getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
        'use_tls': bool(cfg.use_tls),
        'use_ssl': bool(getattr(cfg, 'use_ssl', False)),
        'from_email': cfg.username or getattr(settings, 'DEFAULT_FROM_EMAIL', ''),
    }


def get_imap_runtime_config():
    cfg = get_integration_config('email_imap')
    return {
        'enabled': bool(cfg.is_active and cfg.host and cfg.username and cfg.password),
        'host': cfg.host or getattr(settings, 'IMAP_HOST', ''),
        'port': cfg.port or getattr(settings, 'IMAP_PORT', 993),
        'username': cfg.username or getattr(settings, 'IMAP_USER', ''),
        'password': cfg.password or getattr(settings, 'IMAP_PASSWORD', ''),
        'use_ssl': bool(getattr(cfg, 'use_ssl', True)),
    }
