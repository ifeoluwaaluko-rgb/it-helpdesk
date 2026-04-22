"""
Email notifications for ticket events.
Configure SMTP settings in settings.py / environment variables.
"""
import logging

from django.conf import settings
from django.core.mail import get_connection, send_mail

logger = logging.getLogger(__name__)


def _db_email_connection():
    """
    Build an SMTP connection from IntegrationConfig if available.
    Falls back to Django settings if not configured.
    """
    try:
        from settings_app.models import IntegrationConfig
        cfg = IntegrationConfig.objects.filter(integration='email_smtp', is_active=True).first()
        if cfg and cfg.host and cfg.username and cfg.password:
            port = cfg.port or 587
            use_ssl = (port == 465 and not cfg.use_tls)
            return get_connection(
                host=cfg.host,
                port=port,
                username=cfg.username,
                password=cfg.password,
                use_tls=bool(cfg.use_tls),
                use_ssl=bool(use_ssl),
                timeout=getattr(settings, 'EMAIL_TIMEOUT', 8),
                fail_silently=True,
            )
    except Exception:
        logger.exception("Failed to build DB-backed email connection")
    return None


def _safe_send(subject, body, recipients):
    """
    Best-effort email sender.

    Never raise back into request flow. Email problems must not break
    ticket creation, assignment, or status updates.
    """
    recipients = [email for email in recipients if email]
    if not recipients:
        return False

    try:
        connection = _db_email_connection()
        result = send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            connection=connection,
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
