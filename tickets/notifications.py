"""
Email notifications for ticket events.
Configure SMTP settings in settings.py / environment variables.
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


def notify_assignment(ticket, assignee):
    """Send email to staff member when a ticket is assigned to them."""
    if not assignee.email:
        return
    try:
        subject = f"[Helpdesk] Ticket #{ticket.id} assigned to you: {ticket.title}"
        body = f"""Hi {assignee.get_full_name() or assignee.username},

A new ticket has been assigned to you.

Ticket: #{ticket.id} — {ticket.title}
Priority: {ticket.get_priority_display()}
Category: {ticket.get_category_display()}
SLA Target: {ticket.sla_hours} hours
From: {ticket.user_email}

Description:
{ticket.description[:500]}{'...' if len(ticket.description) > 500 else ''}

Please log in to the helpdesk to action this ticket.

— IT Helpdesk System
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[assignee.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"[Notification Error] {e}")


def notify_status_change(ticket, changed_by):
    """Notify the requester when their ticket status changes."""
    if not ticket.user_email:
        return
    try:
        subject = f"[Helpdesk] Your ticket #{ticket.id} is now {ticket.get_status_display()}"
        body = f"""Hi,

Your IT support ticket has been updated.

Ticket: #{ticket.id} — {ticket.title}
Status: {ticket.get_status_display()}
Updated by: {changed_by.get_full_name() or changed_by.username}

{'Your issue has been resolved. If you experience further problems, please submit a new ticket.' if ticket.status == 'resolved' else 'Our team is working on your request.'}

— IT Helpdesk
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.user_email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"[Notification Error] {e}")
