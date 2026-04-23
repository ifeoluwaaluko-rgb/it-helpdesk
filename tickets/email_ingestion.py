
"""
IMAP Email Ingestion.
Run from a dedicated worker or scheduled command to pull new emails.
Saves inline images and file attachments to TicketAttachment.
"""
import email
import imaplib
import logging
import re
from email.header import decode_header
from email.utils import parseaddr

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from .assignment import auto_assign
from .classifier import classify
from .models import Ticket, TicketAttachment, TicketEvent
from .notifications import notify_ticket_received

logger = logging.getLogger(__name__)

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
    Fall back to Django settings / env values.
    """
    cfg = {
        'host': getattr(settings, 'IMAP_HOST', ''),
        'port': int(getattr(settings, 'IMAP_PORT', 993) or 993),
        'username': getattr(settings, 'IMAP_USER', ''),
        'password': getattr(settings, 'IMAP_PASSWORD', ''),
        'folder': getattr(settings, 'IMAP_FOLDER', 'INBOX') or 'INBOX',
    }
    try:
        from settings_app.models import IntegrationConfig
        db_cfg = IntegrationConfig.objects.get(integration='email_imap')
        if db_cfg and db_cfg.is_active and db_cfg.is_configured():
            cfg.update({
                'host': db_cfg.host or cfg['host'],
                'port': int(db_cfg.port or cfg['port']),
                'username': db_cfg.username or cfg['username'],
                'password': db_cfg.password or cfg['password'],
                'folder': 'INBOX',
            })
    except IntegrationConfig.DoesNotExist:
        pass
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid IMAP config in database: %s", exc)
    return cfg


def _extract_sender_email(msg):
    _, sender = parseaddr(msg.get('From', ''))
    return sender or 'unknown@example.com'


def _looks_like_auto_reply(subject, msg):
    lowered = (subject or '').lower()
    if any(pattern in lowered for pattern in AUTO_REPLY_PATTERNS):
        return True
    auto_submitted = (msg.get('Auto-Submitted') or '').lower()
    precedence = (msg.get('Precedence') or '').lower()
    return auto_submitted not in ('', 'no') or precedence in ('bulk', 'junk', 'list')


def get_email_body(msg):
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get('Content-Disposition') or '')
            if ctype == 'text/plain' and 'attachment' not in disposition.lower():
                payload = part.get_payload(decode=True) or b''
                charset = part.get_content_charset() or 'utf-8'
                parts.append(payload.decode(charset, errors='replace'))
        return '\n'.join([p.strip() for p in parts if p.strip()]).strip()
    payload = msg.get_payload(decode=True) or b''
    charset = msg.get_content_charset() or 'utf-8'
    return payload.decode(charset, errors='replace').strip()


def get_attachments(msg):
    attachments = []
    for part in msg.walk():
        disposition = str(part.get('Content-Disposition') or '')
        if 'attachment' not in disposition.lower():
            continue
        filename = part.get_filename()
        if not filename:
            continue
        decoded_name = ''.join(
            seg.decode(enc or 'utf-8', errors='replace') if isinstance(seg, bytes) else str(seg)
            for seg, enc in decode_header(filename)
        )
        attachments.append({
            'filename': decoded_name,
            'content_type': part.get_content_type() or '',
            'data': part.get_payload(decode=True) or b'',
        })
    return attachments


def _decode_subject(msg):
    subject_parts = decode_header(msg.get('Subject', 'No Subject'))
    return ''.join(
        part.decode(enc or 'utf-8', errors='replace') if isinstance(part, bytes) else str(part)
        for part, enc in subject_parts
    ).strip() or 'No Subject'


def fetch_and_create_tickets():
    """
    Connect to IMAP, read unseen emails, create tickets with attachments.
    Returns count of tickets created.
    """
    created = 0
    cfg = _get_imap_config()
    if not cfg['host'] or not cfg['username'] or not cfg['password']:
        logger.info('[Email Ingestion] IMAP is not configured; skipping fetch.')
        return 0

    try:
        mail = imaplib.IMAP4_SSL(cfg['host'], cfg['port'])
        mail.login(cfg['username'], cfg['password'])
        mail.select(cfg['folder'])

        status, message_ids = mail.search(None, 'UNSEEN')
        if status != 'OK':
            logger.warning("[Email Ingestion Error] IMAP search failed: %s", status)
            mail.logout()
            return 0

        for msg_id in message_ids[0].split():
            try:
                fetch_status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if fetch_status != 'OK' or not msg_data or not msg_data[0]:
                    logger.warning("[Email Parse Error] msg_id=%s: fetch failed", msg_id)
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                title = _decode_subject(msg)

                if _looks_like_auto_reply(title, msg):
                    mail.store(msg_id, '+FLAGS', '\\Seen')
                    continue

                user_email = _extract_sender_email(msg)
                body = get_email_body(msg) or '(No body)'
                message_id = (msg.get('Message-ID') or '').strip()

                if message_id and Ticket.objects.filter(external_message_id=message_id).exists():
                    logger.info("Skipping duplicate inbound email with Message-ID %s", message_id)
                    mail.store(msg_id, '+FLAGS', '\\Seen')
                    continue

                result = classify(title, body)

                with transaction.atomic():
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
                        external_message_id=message_id[:255],
                    )
                    TicketEvent.objects.create(ticket=ticket, actor=None, event_type='created', to_status=ticket.status, note='Ticket created from inbound email.')

                    for att in get_attachments(msg):
                        cf = ContentFile(att['data'], name=att['filename'])
                        TicketAttachment.objects.create(
                            ticket=ticket,
                            file=cf,
                            filename=att['filename'],
                            content_type=att['content_type'],
                            source='email',
                        )

                    assignee = auto_assign(ticket)
                    if assignee:
                        ticket.assigned_to = assignee
                        ticket.save(update_fields=['assigned_to'])
                        TicketEvent.objects.create(ticket=ticket, actor=assignee, event_type='assigned', from_status=ticket.status, to_status=ticket.status, note=f'Auto-assigned to {assignee.get_full_name() or assignee.username}.')

                notify_ticket_received(ticket)
                mail.store(msg_id, '+FLAGS', '\\Seen')
                created += 1

            except (ValueError, TypeError, imaplib.IMAP4.error) as msg_err:
                logger.warning("[Email Parse Error] msg_id=%s: %s", msg_id, msg_err, exc_info=True)
                continue

        mail.logout()

    except (imaplib.IMAP4.error, OSError) as exc:
        logger.warning("[Email Ingestion Error] %s", exc, exc_info=True)

    return created
