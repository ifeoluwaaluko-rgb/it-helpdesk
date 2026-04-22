"""
IMAP Email Ingestion.
Run on a schedule (cron / management command) to pull new emails.
Saves inline images and file attachments to TicketAttachment.
"""
import imaplib
import email
import re
from email.header import decode_header

from django.conf import settings
from django.core.files.base import ContentFile

from .models import Ticket, TicketAttachment
from .classifier import classify
from .assignment import auto_assign
from .notifications import notify_ticket_received


AUTO_REPLY_PATTERNS = (
    'automatic reply',
    'out of office',
    'autoreply',
    'auto-reply',
    'undeliverable',
    'delivery status notification',
)


def _get_imap_config():
    """
    Prefer DB-backed integration settings saved from the frontend settings page.
    Fall back to Django settings / env vars if no active DB config exists.
    """
    try:
        from settings_app.models import IntegrationConfig
        cfg = IntegrationConfig.objects.filter(
            integration='email_imap',
            is_active=True,
        ).first()
        if cfg and cfg.is_configured():
            return {
                'host': cfg.host,
                'port': int(cfg.port or 993),
                'username': cfg.username,
                'password': cfg.password,
                'folder': 'INBOX',
            }
    except Exception as exc:
        print(f"[Email Ingestion Config Warning] Falling back to env IMAP config: {exc}")

    return {
        'host': getattr(settings, 'IMAP_HOST', ''),
        'port': int(getattr(settings, 'IMAP_PORT', 993) or 993),
        'username': getattr(settings, 'IMAP_USER', ''),
        'password': getattr(settings, 'IMAP_PASSWORD', ''),
        'folder': getattr(settings, 'IMAP_FOLDER', 'INBOX'),
    }


def decode_str(value):
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value or ''


def get_email_body(msg):
    """Extract plain-text body. Falls back to best-effort text extraction."""
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
    Captures both explicit attachments and inline images with filenames.
    """
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        filename_raw = part.get_filename()
        if not filename_raw:
            continue
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


def _looks_like_auto_reply(subject: str, msg) -> bool:
    subject_l = (subject or '').strip().lower()
    if any(p in subject_l for p in AUTO_REPLY_PATTERNS):
        return True
    auto_submitted = (msg.get('Auto-Submitted') or '').lower()
    precedence = (msg.get('Precedence') or '').lower()
    if auto_submitted and auto_submitted != 'no':
        return True
    if precedence in ('bulk', 'auto_reply', 'junk', 'list'):
        return True
    return False


def _extract_sender_email(msg):
    sender = msg.get('From', 'unknown@unknown.com')
    match = re.search(r'<([^>]+)>', sender)
    return (match.group(1) if match else sender).strip()


def fetch_and_create_tickets():
    """
    Connect to IMAP, read unseen emails, create tickets with attachments.
    Returns count of tickets created.
    """
    created = 0
    cfg = _get_imap_config()
    if not cfg['host'] or not cfg['username'] or not cfg['password']:
        print('[Email Ingestion] IMAP is not configured; skipping fetch.')
        return 0

    try:
        mail = imaplib.IMAP4_SSL(cfg['host'], cfg['port'])
        mail.login(cfg['username'], cfg['password'])
        mail.select(cfg['folder'])

        status, message_ids = mail.search(None, 'UNSEEN')
        if status != 'OK':
            print(f"[Email Ingestion Error] IMAP search failed: {status}")
            mail.logout()
            return 0

        for msg_id in message_ids[0].split():
            try:
                fetch_status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if fetch_status != 'OK' or not msg_data or not msg_data[0]:
                    print(f"[Email Parse Error] msg_id={msg_id}: fetch failed")
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject_parts = decode_header(msg.get('Subject', 'No Subject'))
                title = ''.join(
                    part.decode(enc or 'utf-8', errors='replace') if isinstance(part, bytes) else str(part)
                    for part, enc in subject_parts
                ).strip() or 'No Subject'

                if _looks_like_auto_reply(title, msg):
                    mail.store(msg_id, '+FLAGS', '\Seen')
                    continue

                user_email = _extract_sender_email(msg)
                body = get_email_body(msg) or '(No body)'

                result = classify(title, body)

                ticket = Ticket.objects.create(
                    title=title,
                    description=body,
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

                # Save attachments before assign/notify so ticket detail is complete.
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

                try:
                    assignee = auto_assign(ticket)
                    if assignee:
                        ticket.assigned_to = assignee
                        ticket.save(update_fields=['assigned_to'])
                except Exception as assign_err:
                    print(f"[Auto Assign Warning] Ticket {ticket.pk}: {assign_err}")

                notify_ticket_received(ticket)

                mail.store(msg_id, '+FLAGS', '\Seen')
                created += 1

            except Exception as msg_err:
                print(f"[Email Parse Error] msg_id={msg_id}: {msg_err}")
                continue

        mail.logout()

    except Exception as e:
        print(f"[Email Ingestion Error] {e}")

    return created
