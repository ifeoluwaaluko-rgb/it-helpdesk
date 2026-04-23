"""
IMAP Email Ingestion.
Run on a schedule (cron / management command) to pull new emails.
Saves inline images and file attachments to TicketAttachment.
"""
import imaplib
import email
import os
import mimetypes
from email.header import decode_header
from django.conf import settings
from django.core.files.base import ContentFile
from .models import Ticket, TicketAttachment
from .classifier import classify
from .assignment import auto_assign
from .notifications import notify_ticket_received


def decode_str(value):
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value or ''


def get_email_body(msg):
    """Extract plain-text body. Falls back to stripping HTML tags."""
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain' and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode('utf-8', errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='replace')
    return body.strip()


def get_attachments(msg):
    """
    Walk the email parts and return a list of dicts:
    { 'filename': str, 'content_type': str, 'data': bytes }
    Captures both explicit attachments (Content-Disposition: attachment)
    and inline images (Content-Disposition: inline with a filename).
    """
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        disposition = str(part.get('Content-Disposition') or '')
        filename_raw = part.get_filename()
        if not filename_raw:
            continue
        # Decode filename
        filename_parts = decode_header(filename_raw)
        filename = ''.join(
            p.decode(enc or 'utf-8') if isinstance(p, bytes) else p
            for p, enc in filename_parts
        )
        content_type = part.get_content_type()
        data = part.get_payload(decode=True)
        if data:
            attachments.append({
                'filename': filename,
                'content_type': content_type,
                'data': data,
            })
    return attachments


def fetch_and_create_tickets():
    """
    Connect to IMAP, read unseen emails, create tickets with attachments.
    Returns count of tickets created.
    """
    created = 0
    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        mail.select(settings.IMAP_FOLDER)

        _, message_ids = mail.search(None, 'UNSEEN')

        for msg_id in message_ids[0].split():
            try:
                _, msg_data = mail.fetch(msg_id, '(RFC822)')
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                # Decode subject
                subject_parts = decode_header(msg.get('Subject', 'No Subject'))
                title = ''.join(
                    decode_str(part) if isinstance(part, bytes) else part
                    for part, enc in subject_parts
                ).strip() or 'No Subject'

                # Extract sender email
                sender = msg.get('From', 'unknown@unknown.com')
                if '<' in sender:
                    user_email = sender.split('<')[1].strip('>')
                else:
                    user_email = sender.strip()

                body = get_email_body(msg)
                result = classify(title, body)

                ticket = Ticket.objects.create(
                    title=title,
                    description=body or '(No body)',
                    user_email=user_email,
                    category=result.get('category', 'other'),
                    subcategory=result.get('subcategory', ''),
                    item=result.get('item', ''),
                    priority=result.get('priority', 'medium'),
                    required_level=result.get('level', 'associate'),
                    sla_hours=result.get('sla_hours', 24),
                    channel='email',
                    raw_email=raw.decode('utf-8', errors='replace'),
                )

                notify_ticket_received(ticket)

                # Save attachments
                for att in get_attachments(msg):
                    try:
                        cf = ContentFile(att['data'], name=att['filename'])
                        TicketAttachment.objects.create(
                            ticket=ticket,
                            file=cf,
                            filename=att['filename'],
                            content_type=att['content_type'],
                            source='email',
                        )
                    except Exception as att_err:
                        print(f"[Attachment Save Error] {att_err}")

                # Auto assign
                try:
                    assignee = auto_assign(ticket)
                    if assignee:
                        ticket.assigned_to = assignee
                        ticket.save()
                except Exception:
                    pass

                mail.store(msg_id, '+FLAGS', '\\Seen')
                created += 1

            except Exception as msg_err:
                print(f"[Email Parse Error] msg_id={msg_id}: {msg_err}")
                continue

        mail.logout()

    except Exception as e:
        print(f"[Email Ingestion Error] {e}")

    return created
