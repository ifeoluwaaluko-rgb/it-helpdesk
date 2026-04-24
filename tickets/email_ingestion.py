import email
import imaplib
import logging
import mimetypes
from email.header import decode_header

from django.core.files.base import ContentFile

from settings_app.services import get_imap_runtime_config
from .assignment import auto_assign
from .classifier import classify
from .models import Ticket, TicketAttachment, TicketEvent
from .notifications import notify_ticket_received

logger = logging.getLogger(__name__)


def decode_str(value):
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value or ''


def get_email_body(msg):
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain' and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')
    return body.strip()


def get_attachments(msg):
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        filename_raw = part.get_filename()
        if not filename_raw:
            continue
        filename = ''.join(
            p.decode(enc or 'utf-8', errors='replace') if isinstance(p, bytes) else p
            for p, enc in decode_header(filename_raw)
        )
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        attachments.append({
            'filename': filename,
            'content_type': part.get_content_type() or mimetypes.guess_type(filename)[0] or '',
            'data': payload,
        })
    return attachments


def fetch_and_create_tickets(limit=20):
    cfg = get_imap_runtime_config()
    if not cfg.get('enabled'):
        logger.info("IMAP is not configured or inactive; skipping fetch.")
        return 0

    created = 0
    mail = None
    try:
        if cfg.get('use_ssl', True):
            mail = imaplib.IMAP4_SSL(cfg['host'], int(cfg['port'] or 993))
        else:
            mail = imaplib.IMAP4(cfg['host'], int(cfg['port'] or 143))
        mail.login(cfg['username'], cfg['password'])
        mail.select('INBOX')
        status, data = mail.search(None, 'UNSEEN')
        if status != 'OK':
            return 0
        ids = data[0].split()[:limit]
        for eid in ids:
            status, msg_data = mail.fetch(eid, '(RFC822)')
            if status != 'OK' or not msg_data:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            message_id = (msg.get('Message-ID') or '').strip()
            if message_id and Ticket.objects.filter(external_message_id=message_id).exists():
                mail.store(eid, '+FLAGS', '\\Seen')
                continue

            subject = decode_str(msg.get('Subject', 'No subject'))
            sender = email.utils.parseaddr(msg.get('From', ''))[1] or 'unknown@example.com'
            body = get_email_body(msg) or subject
            result = classify(subject, body)
            ticket = Ticket.objects.create(
                title=subject[:255],
                description=body,
                user_email=sender,
                requester_name=email.utils.parseaddr(msg.get('From', ''))[0],
                category=result.get('category', 'other'),
                subcategory=result.get('subcategory', ''),
                item=result.get('item', ''),
                priority=result.get('priority', 'medium'),
                required_level=result.get('level', 'associate'),
                sla_hours=result.get('sla_hours', 24),
                channel='email',
                raw_email=raw.decode('utf-8', errors='replace')[:10000],
                external_message_id=message_id,
            )
            TicketEvent.objects.create(ticket=ticket, event_type='email_received', message=f'Email received from {sender}')
            for att in get_attachments(msg):
                TicketAttachment.objects.create(
                    ticket=ticket,
                    file=ContentFile(att['data'], name=att['filename']),
                    filename=att['filename'],
                    content_type=att['content_type'],
                    source='email',
                )
            assignee = auto_assign(ticket)
            if assignee:
                ticket.assigned_to = assignee
                ticket.save(update_fields=['assigned_to', 'updated_at'])
                TicketEvent.objects.create(ticket=ticket, actor=assignee, event_type='assigned', message=f'Auto-assigned to {assignee.get_full_name() or assignee.username}')
            notify_ticket_received(ticket)
            mail.store(eid, '+FLAGS', '\\Seen')
            created += 1
    except (imaplib.IMAP4.error, OSError, ValueError):
        logger.exception("IMAP fetch failed")
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
    return created


# Backwards-compatible alias used by older commands/scripts.
fetch_emails = fetch_and_create_tickets
