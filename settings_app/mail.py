
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from .models import IntegrationConfig


@dataclass
class OutboundMailConfig:
    enabled: bool = False
    host: str = ''
    port: int = 0
    username: str = ''
    password: str = ''
    use_tls: bool = True
    use_ssl: bool = False
    from_email: str = ''


def get_outbound_mail_config() -> OutboundMailConfig:
    if not getattr(settings, 'EMAIL_ENABLED', False):
        return OutboundMailConfig(enabled=False, from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', ''))

    try:
        cfg = IntegrationConfig.objects.get(integration='email_smtp')
    except IntegrationConfig.DoesNotExist:
        cfg = None

    if cfg and cfg.is_active and cfg.is_configured():
        host = cfg.host or getattr(settings, 'EMAIL_HOST', '')
        port = int(cfg.port or 0)
        use_ssl = bool(cfg.use_ssl or port == 465)
        return OutboundMailConfig(
            enabled=True,
            host=host,
            port=port,
            username=cfg.username or getattr(settings, 'EMAIL_HOST_USER', ''),
            password=cfg.password or getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
            use_tls=bool(cfg.use_tls and not use_ssl),
            use_ssl=use_ssl,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', '') or (cfg.username or ''),
        )

    return OutboundMailConfig(
        enabled=bool(getattr(settings, 'EMAIL_HOST', '') and getattr(settings, 'EMAIL_HOST_USER', '') and getattr(settings, 'EMAIL_HOST_PASSWORD', '')),
        host=getattr(settings, 'EMAIL_HOST', ''),
        port=int(getattr(settings, 'EMAIL_PORT', 0) or 0),
        username=getattr(settings, 'EMAIL_HOST_USER', ''),
        password=getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
        use_tls=bool(getattr(settings, 'EMAIL_USE_TLS', False) and int(getattr(settings, 'EMAIL_PORT', 0) or 0) != 465),
        use_ssl=bool(getattr(settings, 'EMAIL_USE_SSL', False) or int(getattr(settings, 'EMAIL_PORT', 0) or 0) == 465),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', ''),
    )
