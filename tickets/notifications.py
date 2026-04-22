
"""
Email notifications for ticket events.
Outbound email is optional and should never break request or worker flows.
"""
import logging
import smtplib
from socket import timeout as SocketTimeout
from email.mime.text import MIMEText

from django.conf import settings

from settings_app.mail import get_outbound_mail_config

logger = logging.getLogger(__name__)


def _safe_send(subject, body, recipients):
    recipients = [email for email in recipients if email]
    if not recipients:
        return False

    cfg = get_outbound_mail_config()
    if not cfg.enabled:
        logger.info("Outbound email disabled; skipping notification to %s", recipients)
        return False

    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = cfg.from_email
        msg['To'] = ', '.join(recipients)

        if cfg.use_ssl:
            server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=getattr(settings, 'EMAIL_TIMEOUT', 5))
        else:
            server = smtplib.SMTP(cfg.host, cfg.port, timeout=getattr(settings, 'EMAIL_TIMEOUT', 5))
            if cfg.use_tls:
                server.starttls()

        if cfg.username and cfg.password:
            server.login(cfg.username, cfg.password)
        server.sendmail(cfg.from_email, recipients, msg.as_string())
        server.quit()
        return True
    except (smtplib.SMTPException, OSError, SocketTimeout) as exc:
        logger.warning("Notification send failed: %s", exc, exc_info=True)
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

A ticket has been assigned to you.

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
