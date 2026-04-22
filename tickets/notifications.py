
"""
Email notifications for ticket events.
Supports either:
- direct SMTP using Django's email backend
- Gmail API OAuth2 (refresh token) through settings_app.IntegrationConfig
"""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _get_smtp_config():
    try:
        from settings_app.models import IntegrationConfig
        return IntegrationConfig.objects.filter(integration='email_smtp', is_active=True).first()
    except Exception:
        return None


def _gmail_refresh_access_token(cfg):
    payload = urllib.parse.urlencode({
        'client_id': cfg.oauth_client_id,
        'client_secret': cfg.oauth_client_secret,
        'refresh_token': cfg.oauth_refresh_token,
        'grant_type': 'refresh_token',
    }).encode()
    token_uri = cfg.oauth_token_uri or 'https://oauth2.googleapis.com/token'
    req = urllib.request.Request(token_uri, data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    token = data.get('access_token')
    if not token:
        raise RuntimeError(data.get('error_description') or data.get('error') or 'OAuth token refresh failed')
    try:
        cfg.access_token = token
        cfg.save(update_fields=['_access_token', 'updated_at'])
    except Exception:
        pass
    return token


def _gmail_api_send(subject, body, recipients, cfg):
    raw = (
        f"From: {cfg.username}\r\n"
        f"To: {', '.join(recipients)}\r\n"
        f"Subject: {subject}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        f"{body}"
    ).encode('utf-8')
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    token = _gmail_refresh_access_token(cfg)
    req = urllib.request.Request(
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        data=json.dumps({'raw': encoded}).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status in (200, 202)


def _safe_send(subject, body, recipients):
    recipients = [email for email in recipients if email]
    if not recipients:
        return False

    cfg = _get_smtp_config()
    if cfg and getattr(cfg, 'auth_mode', 'password') == 'gmail_api_oauth':
        try:
            return _gmail_api_send(subject, body, recipients, cfg)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors='ignore')
            logger.exception("Gmail API send failed: %s %s", exc.code, detail[:300])
            return False
        except BaseException as exc:
            logger.exception("Gmail API send failed: %s", exc)
            return False

    try:
        result = send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            fail_silently=True,
        )
        return bool(result)
    except BaseException as exc:
        logger.exception("Notification send failed: %s", exc)
        return False


def notify_ticket_received(ticket):
    subject = f"[Helpdesk] Ticket #{ticket.id} received: {ticket.title}"
    body = f"""Hi,

Your IT request has been received and logged successfully.

Ticket: #{ticket.id} — {ticket.title}
Priority: {ticket.get_priority_display()}
Category: {ticket.category_display}
Expected SLA: {ticket.sla_hours} hours

Our IT team will review it shortly. Please keep this ticket number for future follow-up.

— IT Helpdesk
"""
    return _safe_send(subject, body, [ticket.user_email])


def notify_assignment(ticket, assignee):
    name = assignee.get_full_name() or assignee.username or "there"
    subject = f"[Helpdesk] Ticket #{ticket.id} assigned to you: {ticket.title}"
    body = f"""Hi {name},

A new ticket has been assigned to you.

Ticket: #{ticket.id} — {ticket.title}
Priority: {ticket.get_priority_display()}
Category: {ticket.category_display}
SLA Target: {ticket.sla_hours} hours
From: {ticket.user_email}

Description:
{ticket.description[:500]}{'...' if len(ticket.description) > 500 else ''}

Please log in to the helpdesk to action this ticket.

— IT Helpdesk System
"""
    return _safe_send(subject, body, [assignee.email])


def notify_status_change(ticket, changed_by):
    status_note = (
        "Your issue has been resolved. If you still experience the problem, please reply to this email or contact IT."
        if ticket.status == 'resolved'
        else "Our team is working on your request."
    )
    body = f"""Hi,

Your IT support ticket has been updated.

Ticket: #{ticket.id} — {ticket.title}
Status: {ticket.get_status_display()}
Updated by: {changed_by.get_full_name() or changed_by.username}

{status_note}

— IT Helpdesk
"""
    subject = f"[Helpdesk] Your ticket #{ticket.id} is now {ticket.get_status_display()}"
    return _safe_send(subject, body, [ticket.user_email])
