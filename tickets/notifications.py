import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _safe_send(subject, body, recipients):
    if not getattr(settings, 'EMAIL_ENABLED', False):
        return False
    recipients = [email for email in recipients if email]
    if not recipients:
        return False
    try:
        return bool(send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=recipients,
            fail_silently=True,
        ))
    except Exception:
        logger.exception("Notification send failed")
        return False


def notify_ticket_received(ticket):
    subject = f"[Zynaros] Ticket #{ticket.id} received: {ticket.title}"
    body = f"""Hi,

Your request has been received and logged successfully.

Ticket: #{ticket.id} — {ticket.title}
Priority: {ticket.get_priority_display()}
Category: {ticket.category_display}

— Zynaros
"""
    return _safe_send(subject, body, [ticket.user_email])


def notify_assignment(ticket, assignee):
    subject = f"[Zynaros] Ticket #{ticket.id} assigned to you: {ticket.title}"
    body = f"""Hi {assignee.get_full_name() or assignee.username},

A ticket has been assigned to you.

Ticket: #{ticket.id} — {ticket.title}
Priority: {ticket.get_priority_display()}
Category: {ticket.category_display}

— Zynaros
"""
    return _safe_send(subject, body, [assignee.email])


def notify_status_change(ticket, changed_by):
    subject = f"[Zynaros] Ticket #{ticket.id} is now {ticket.get_status_display()}"
    body = f"""Hi,

Ticket #{ticket.id} — {ticket.title} has been updated.

Status: {ticket.get_status_display()}
Updated by: {changed_by.get_full_name() or changed_by.username}

— Zynaros
"""
    return _safe_send(subject, body, [ticket.user_email])
