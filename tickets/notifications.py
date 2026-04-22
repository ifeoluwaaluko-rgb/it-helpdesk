"""
Email notifications for ticket events.
Configure SMTP settings in settings.py / environment variables.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


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
        result = send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            fail_silently=True,
        )
        return bool(result)
    except BaseException as exc:
        # Catch BaseException as well because some runtime/email backends can
        # surface non-Exception failures during connection/setup.
        logger.exception("Notification send failed: %s", exc)
        return False


def notify_ticket_received(ticket):
    """Send an acknowledgment to the requester as soon as a ticket is created."""
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
    """Send email to staff member when a ticket is assigned to them."""
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
    """Notify the requester when their ticket status changes."""
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
