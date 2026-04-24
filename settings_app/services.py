from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings as dj_settings

from .models import IntegrationConfig, IntegrationAuditLog


INTEGRATION_KEYS = [
    "email_smtp",
    "email_imap",
    "microsoft_graph",
    "generic_webhook",
    "whatsapp",
    "teams",
    "slack",
    "openai",
]


@dataclass
class IntegrationTestResult:
    ok: bool
    message: str


@dataclass
class EmailRuntimeConfig:
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    from_email: str = ""
    enabled: bool = False

    @property
    def is_configured(self):
        return bool(self.host and self.port and self.username and self.password)


@dataclass
class ImapRuntimeConfig:
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    folder: str = "INBOX"
    enabled: bool = False

    @property
    def is_configured(self):
        return bool(self.host and self.port and self.username and self.password)


class IntegrationConfigError(ValueError):
    pass


def log_integration_event(user, integration, action, status="success", message=""):
    IntegrationAuditLog.objects.create(
        actor=user,
        integration=integration,
        action=action,
        status=status,
        message=(message or "")[:255],
    )


def get_configs():
    configs = {}
    for key in INTEGRATION_KEYS:
        obj, _ = IntegrationConfig.objects.get_or_create(integration=key)
        configs[key] = obj
    return configs


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _require_text(value, label):
    cleaned = (value or "").strip()
    if not cleaned:
        raise IntegrationConfigError(f"{label} is required.")
    return cleaned


def _parse_port(value, default, label):
    try:
        port = int(value or default)
    except (TypeError, ValueError):
        raise IntegrationConfigError(f"{label} must be a valid number.")
    if port < 1 or port > 65535:
        raise IntegrationConfigError(f"{label} must be between 1 and 65535.")
    return port


def _validate_url(value, label, *, require_https=False):
    cleaned = _require_text(value, label)
    parsed = urlparse(cleaned)
    allowed_schemes = {"https"} if require_https else {"http", "https"}
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        allowed_text = "https" if require_https else "http or https"
        raise IntegrationConfigError(f"{label} must be a valid {allowed_text} URL.")
    return cleaned


def get_smtp_runtime_config():
    config = EmailRuntimeConfig(
        host=getattr(dj_settings, "EMAIL_HOST", ""),
        port=_safe_int(getattr(dj_settings, "EMAIL_PORT", 587), 587),
        username=getattr(dj_settings, "EMAIL_HOST_USER", ""),
        password=getattr(dj_settings, "EMAIL_HOST_PASSWORD", ""),
        use_tls=bool(getattr(dj_settings, "EMAIL_USE_TLS", True)),
        use_ssl=bool(getattr(dj_settings, "EMAIL_USE_SSL", False)),
        from_email=getattr(dj_settings, "DEFAULT_FROM_EMAIL", ""),
        enabled=bool(getattr(dj_settings, "EMAIL_HOST", "")),
    )
    try:
        cfg = IntegrationConfig.objects.get(integration="email_smtp")
    except IntegrationConfig.DoesNotExist:
        return config

    if cfg.is_configured():
        return EmailRuntimeConfig(
            host=cfg.host,
            port=cfg.port or 587,
            username=cfg.username,
            password=cfg.password,
            use_tls=cfg.use_tls,
            use_ssl=cfg.use_ssl,
            from_email=getattr(dj_settings, "DEFAULT_FROM_EMAIL", "") or cfg.username,
            enabled=cfg.is_active,
        )
    return config


def get_imap_runtime_config():
    config = ImapRuntimeConfig(
        host=getattr(dj_settings, "IMAP_HOST", ""),
        port=_safe_int(getattr(dj_settings, "IMAP_PORT", 993), 993),
        username=getattr(dj_settings, "IMAP_USER", ""),
        password=getattr(dj_settings, "IMAP_PASSWORD", ""),
        folder=getattr(dj_settings, "IMAP_FOLDER", "INBOX"),
        enabled=bool(getattr(dj_settings, "IMAP_HOST", "")),
    )
    try:
        cfg = IntegrationConfig.objects.get(integration="email_imap")
    except IntegrationConfig.DoesNotExist:
        return config

    if cfg.is_configured():
        return ImapRuntimeConfig(
            host=cfg.host,
            port=cfg.port or 993,
            username=cfg.username,
            password=cfg.password,
            folder=getattr(dj_settings, "IMAP_FOLDER", "INBOX"),
            enabled=cfg.is_active,
        )
    return config


def save_smtp_config(cfg, payload, user):
    cfg.host = _require_text(payload.get("host"), "SMTP host")
    cfg.port = _parse_port(payload.get("port", 587), 587, "SMTP port")
    cfg.username = _require_text(payload.get("username"), "SMTP username")
    cfg.use_tls = payload.get("use_tls") == "on"
    cfg.use_ssl = payload.get("use_ssl") == "on"
    cfg.is_active = payload.get("is_active") == "on"
    password = payload.get("password", "").strip()
    if password:
        cfg.password = password
    elif not cfg.password:
        raise IntegrationConfigError("SMTP password is required.")
    cfg.updated_by = user
    cfg.save()
    dj_settings.EMAIL_HOST = cfg.host
    dj_settings.EMAIL_PORT = cfg.port or 587
    dj_settings.EMAIL_HOST_USER = cfg.username
    dj_settings.EMAIL_HOST_PASSWORD = cfg.password
    dj_settings.EMAIL_USE_TLS = cfg.use_tls
    dj_settings.EMAIL_USE_SSL = cfg.use_ssl
    return "SMTP settings saved."


def save_imap_config(cfg, payload, user):
    cfg.host = _require_text(payload.get("host"), "IMAP host")
    cfg.port = _parse_port(payload.get("port", 993), 993, "IMAP port")
    cfg.username = _require_text(payload.get("username"), "IMAP username")
    cfg.is_active = payload.get("is_active") == "on"
    password = payload.get("password", "").strip()
    if password:
        cfg.password = password
    elif not cfg.password:
        raise IntegrationConfigError("IMAP password is required.")
    cfg.updated_by = user
    cfg.save()
    dj_settings.IMAP_HOST = cfg.host
    dj_settings.IMAP_PORT = cfg.port or 993
    dj_settings.IMAP_USER = cfg.username
    dj_settings.IMAP_PASSWORD = cfg.password
    return "IMAP settings saved."


def save_graph_config(cfg, payload, user):
    cfg.host = _require_text(payload.get("tenant_id"), "Tenant ID")
    cfg.username = _require_text(payload.get("client_id"), "Client ID")
    cfg.is_active = payload.get("is_active") == "on"
    token = payload.get("access_token", "").strip()
    if token:
        cfg.access_token = token
    elif not cfg.access_token:
        raise IntegrationConfigError("Client secret / token is required.")
    cfg.updated_by = user
    cfg.save()
    return "Microsoft Graph settings saved."


def save_whatsapp_config(cfg, payload, user):
    cfg.phone_number_id = _require_text(payload.get("phone_number_id"), "Phone number ID")
    cfg.wa_business_id = _require_text(payload.get("wa_business_id"), "WhatsApp business ID")
    cfg.is_active = payload.get("is_active") == "on"
    token = payload.get("access_token", "").strip()
    if token:
        cfg.access_token = token
    elif not cfg.access_token:
        raise IntegrationConfigError("WhatsApp access token is required.")
    cfg.updated_by = user
    cfg.save()
    return "WhatsApp settings saved."


def save_webhook_config(cfg, payload, user, label):
    cfg.host = payload.get("host", "").strip()
    cfg.webhook_url = _validate_url(payload.get("webhook_url"), "Webhook URL")
    cfg.is_active = payload.get("is_active") == "on"
    token = payload.get("access_token", "").strip()
    if token:
        cfg.access_token = token
    cfg.updated_by = user
    cfg.save()
    return f"{label} saved."


def save_simple_webhook_config(cfg, payload, user, label):
    cfg.webhook_url = _validate_url(payload.get("webhook_url"), "Webhook URL")
    cfg.is_active = payload.get("is_active") == "on"
    cfg.updated_by = user
    cfg.save()
    return f"{label} saved."


def save_openai_config(cfg, payload, user):
    cfg.host = _validate_url(payload.get("host") or "https://api.openai.com/v1", "AI base URL", require_https=True)
    cfg.username = _require_text(payload.get("model_name") or "gpt-4o-mini", "Model name")
    cfg.is_active = payload.get("is_active") == "on"
    token = payload.get("access_token", "").strip()
    if token:
        cfg.access_token = token
    elif not cfg.access_token:
        raise IntegrationConfigError("AI API key is required.")
    cfg.updated_by = user
    cfg.save()
    return "AI provider settings saved."


def test_smtp(cfg):
    try:
        import smtplib

        server = smtplib.SMTP(cfg.host, cfg.port or 587, timeout=8)
        if cfg.use_tls:
            server.starttls()
        server.login(cfg.username, cfg.password)
        server.quit()
        return IntegrationTestResult(True, "SMTP connection successful.")
    except Exception as exc:
        return IntegrationTestResult(False, f"SMTP error: {exc}")


def test_imap(cfg):
    try:
        import imaplib

        mail = imaplib.IMAP4_SSL(cfg.host, cfg.port or 993)
        mail.login(cfg.username, cfg.password)
        mail.logout()
        return IntegrationTestResult(True, "IMAP connection successful.")
    except Exception as exc:
        return IntegrationTestResult(False, f"IMAP error: {exc}")


def test_graph(cfg):
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/organization",
            headers={"Authorization": f"Bearer {cfg.access_token}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get("value"):
            return IntegrationTestResult(True, "Microsoft Graph token valid.")
        return IntegrationTestResult(False, "Unexpected Graph response.")
    except Exception as exc:
        return IntegrationTestResult(False, f"Microsoft Graph error: {exc}")


def test_whatsapp(cfg):
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            f"https://graph.facebook.com/v18.0/{cfg.phone_number_id}",
            headers={"Authorization": f"Bearer {cfg.access_token}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get("id"):
            return IntegrationTestResult(True, f"WhatsApp API connected (Number ID: {data['id']}).")
        return IntegrationTestResult(False, "Unexpected response from Meta API.")
    except Exception as exc:
        return IntegrationTestResult(False, f"WhatsApp API error: {exc}")


def test_webhook(cfg):
    try:
        import json
        import urllib.request

        payload = json.dumps({"text": "IT Helpdesk webhook test: connection OK"}).encode()
        headers = {"Content-Type": "application/json"}
        if cfg.access_token:
            headers["Authorization"] = f"Bearer {cfg.access_token}"
        req = urllib.request.Request(cfg.webhook_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return IntegrationTestResult(True, f"Webhook responded with HTTP {resp.status}.")
    except Exception as exc:
        return IntegrationTestResult(False, f"Webhook error: {exc}")


def test_openai(cfg):
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            (cfg.host or "https://api.openai.com/v1").rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {cfg.access_token}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if isinstance(data.get("data"), list):
            return IntegrationTestResult(True, "AI provider connection successful.")
        return IntegrationTestResult(False, "Unexpected AI provider response.")
    except Exception as exc:
        return IntegrationTestResult(False, f"AI provider error: {exc}")
