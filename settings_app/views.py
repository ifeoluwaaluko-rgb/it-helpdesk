
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings as dj_settings
from .models import IntegrationConfig, IntegrationAuditLog
from tickets.models import TicketCategory, TicketSubcategory, Ticket


def _role(user):
    try:
        return user.profile.role
    except Exception:
        return ''


def _can_manage(user):
    return _role(user) in ('manager', 'superadmin')


def _require_manager(request):
    if not _can_manage(request.user):
        messages.error(request, 'Access denied. Only Managers can manage integrations.')
        return False
    return True


INTEGRATION_KEYS = [
    'email_smtp',
    'email_imap',
    'microsoft_graph',
    'generic_webhook',
    'whatsapp',
    'teams',
    'slack',
    'openai',
]


def _log(user, integration, action, status='success', message=''):
    IntegrationAuditLog.objects.create(
        actor=user,
        integration=integration,
        action=action,
        status=status,
        message=(message or '')[:255],
    )


def _get_configs():
    configs = {}
    for key in INTEGRATION_KEYS:
        obj, _ = IntegrationConfig.objects.get_or_create(integration=key)
        configs[key] = obj
    return configs




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
    access_token = data.get('access_token')
    if not access_token:
        raise RuntimeError(data.get('error_description') or data.get('error') or 'OAuth token refresh failed')
    cfg.access_token = access_token
    cfg.save(update_fields=['_access_token', 'updated_at'])
    return access_token


def _test_gmail_api(cfg):
    try:
        token = _gmail_refresh_access_token(cfg)
        req = urllib.request.Request(
            'https://gmail.googleapis.com/gmail/v1/users/me/profile',
            headers={'Authorization': f'Bearer {token}'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        email_addr = data.get('emailAddress', cfg.username)
        return True, f'Gmail API OAuth2 connection successful for {email_addr}.'
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='ignore')
        return False, f'Gmail API error: {e.code} {detail[:180]}'
    except Exception as e:
        return False, f'Gmail API error: {e}'

@login_required
def settings_home(request):
    if not _require_manager(request):
        return redirect('dashboard')
    configs = _get_configs()
    recent_logs = IntegrationAuditLog.objects.select_related('actor')[:20]

    categories = TicketCategory.objects.prefetch_related('subcategories').all()
    category_rows = []
    for category in categories:
        # Ticket.category is a CharField matching the Ticket.CATEGORY_CHOICES slugs,
        # not a FK — match by slug (which equals the choice key)
        item_count = Ticket.objects.filter(category=category.slug).count()
        category_rows.append({
            'name': category.name,
            'icon': category.icon,
            'required_level': category.required_level,
            'sla_hours': category.sla_hours,
            'subcategory_count': category.subcategories.count(),
            'ticket_count': item_count,
        })

    notification_rows = [
        {
            'event': 'New ticket assignment',
            'channel': 'Email',
            'enabled': bool(configs['email_smtp'].is_configured() and configs['email_smtp'].is_active),
            'detail': 'Uses SMTP to notify assignees when a ticket lands in their queue.',
        },
        {
            'event': 'Requester status updates',
            'channel': 'Email',
            'enabled': bool(configs['email_smtp'].is_configured() and configs['email_smtp'].is_active),
            'detail': 'Sends resolved / in-progress updates to the requester.',
        },
        {
            'event': 'Team alerting',
            'channel': 'Slack / Teams / Webhook',
            'enabled': any(configs[key].is_configured() and configs[key].is_active for key in ('slack', 'teams', 'generic_webhook')),
            'detail': 'Can post operational alerts into external channels.',
        },
    ]

    context = {
        'configs': configs,
        'recent_logs': recent_logs,
        'category_rows': category_rows,
        'notification_rows': notification_rows,
        'priority_slas': [
            {'priority': 'Critical', 'response': '15 mins', 'resolution': '4 hours'},
            {'priority': 'High', 'response': '1 hour', 'resolution': '8 hours'},
            {'priority': 'Medium', 'response': '4 hours', 'resolution': '24 hours'},
            {'priority': 'Low', 'response': '1 business day', 'resolution': '48 hours'},
        ],
        'active_tab': request.GET.get('tab', 'integrations'),
        'ticket_count': Ticket.objects.count(),
    }
    return render(request, 'settings/home.html', context)


@login_required
@require_POST
def save_smtp(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='email_smtp')
    cfg.auth_mode = request.POST.get('auth_mode', 'password').strip() or 'password'
    cfg.host = request.POST.get('host', '').strip()
    cfg.port = int(request.POST.get('port', 587) or 587)
    cfg.username = request.POST.get('username', '').strip()
    cfg.use_tls = request.POST.get('use_tls') == 'on'
    cfg.use_ssl = request.POST.get('use_ssl') == 'on'
    cfg.is_active = request.POST.get('is_active') == 'on'
    cfg.oauth_client_id = request.POST.get('oauth_client_id', '').strip()
    token_uri = request.POST.get('oauth_token_uri', '').strip()
    cfg.oauth_token_uri = token_uri or 'https://oauth2.googleapis.com/token'
    pw = request.POST.get('password', '').strip()
    if pw:
        cfg.password = pw
    oauth_secret = request.POST.get('oauth_client_secret', '').strip()
    if oauth_secret:
        cfg.oauth_client_secret = oauth_secret
    refresh_token = request.POST.get('oauth_refresh_token', '').strip()
    if refresh_token:
        cfg.oauth_refresh_token = refresh_token
    cfg.updated_by = request.user
    cfg.save()
    dj_settings.EMAIL_HOST = cfg.host
    dj_settings.EMAIL_PORT = cfg.port or 587
    dj_settings.EMAIL_HOST_USER = cfg.username
    dj_settings.EMAIL_HOST_PASSWORD = cfg.password
    dj_settings.EMAIL_USE_TLS = cfg.use_tls
    dj_settings.EMAIL_USE_SSL = getattr(cfg, 'use_ssl', False)
    dj_settings.EMAIL_AUTH_MODE = cfg.auth_mode
    _log(request.user, 'email_smtp', 'save', 'success', 'SMTP settings saved')
    messages.success(request, 'SMTP settings saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_imap(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='email_imap')
    cfg.host = request.POST.get('host', '').strip()
    cfg.port = int(request.POST.get('port', 993) or 993)
    cfg.username = request.POST.get('username', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    pw = request.POST.get('password', '').strip()
    if pw:
        cfg.password = pw
    cfg.updated_by = request.user
    cfg.save()
    dj_settings.IMAP_HOST = cfg.host
    dj_settings.IMAP_PORT = cfg.port or 993
    dj_settings.IMAP_USER = cfg.username
    dj_settings.IMAP_PASSWORD = cfg.password
    _log(request.user, 'email_imap', 'save', 'success', 'IMAP settings saved')
    messages.success(request, 'IMAP settings saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_graph(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='microsoft_graph')
    cfg.host = request.POST.get('tenant_id', '').strip()
    cfg.username = request.POST.get('client_id', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    token = request.POST.get('access_token', '').strip()
    if token:
        cfg.access_token = token
    cfg.updated_by = request.user
    cfg.save()
    _log(request.user, 'microsoft_graph', 'save', 'success', 'Microsoft Graph settings saved')
    messages.success(request, 'Microsoft Graph settings saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_whatsapp(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='whatsapp')
    cfg.phone_number_id = request.POST.get('phone_number_id', '').strip()
    cfg.wa_business_id = request.POST.get('wa_business_id', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    token = request.POST.get('access_token', '').strip()
    if token:
        cfg.access_token = token
    cfg.updated_by = request.user
    cfg.save()
    _log(request.user, 'whatsapp', 'save', 'success', 'WhatsApp settings saved')
    messages.success(request, 'WhatsApp settings saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_teams(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='teams')
    cfg.webhook_url = request.POST.get('webhook_url', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    cfg.updated_by = request.user
    cfg.save()
    _log(request.user, 'teams', 'save', 'success', 'Teams webhook saved')
    messages.success(request, 'Microsoft Teams webhook saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_slack(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='slack')
    cfg.webhook_url = request.POST.get('webhook_url', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    cfg.updated_by = request.user
    cfg.save()
    _log(request.user, 'slack', 'save', 'success', 'Slack webhook saved')
    messages.success(request, 'Slack webhook saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_generic_webhook(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='generic_webhook')
    cfg.host = request.POST.get('host', '').strip()
    cfg.webhook_url = request.POST.get('webhook_url', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    token = request.POST.get('access_token', '').strip()
    if token:
        cfg.access_token = token
    cfg.updated_by = request.user
    cfg.save()
    _log(request.user, 'generic_webhook', 'save', 'success', 'Generic webhook saved')
    messages.success(request, 'Generic webhook saved.')
    return redirect('settings_home')


@login_required
@require_POST
def save_openai(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='openai')
    cfg.host = request.POST.get('host', '').strip() or 'https://api.openai.com/v1'
    cfg.username = request.POST.get('model_name', '').strip() or 'gpt-4o-mini'
    cfg.is_active = request.POST.get('is_active') == 'on'
    token = request.POST.get('access_token', '').strip()
    if token:
        cfg.access_token = token
    cfg.updated_by = request.user
    cfg.save()
    _log(request.user, 'openai', 'save', 'success', 'OpenAI settings saved')
    messages.success(request, 'AI provider settings saved.')
    return redirect('settings_home')


@login_required
def test_connection(request, integration):
    if not _can_manage(request.user):
        return JsonResponse({'ok': False, 'msg': 'Permission denied.'})
    try:
        cfg = IntegrationConfig.objects.get(integration=integration)
    except IntegrationConfig.DoesNotExist:
        return JsonResponse({'ok': False, 'msg': 'Not configured yet.'})

    try:
        if integration == 'email_smtp':
            ok, msg = _test_smtp(cfg)
        elif integration == 'email_imap':
            ok, msg = _test_imap(cfg)
        elif integration == 'microsoft_graph':
            ok, msg = _test_graph(cfg)
        elif integration == 'whatsapp':
            ok, msg = _test_whatsapp(cfg)
        elif integration in ('teams', 'slack', 'generic_webhook'):
            ok, msg = _test_webhook(cfg)
        elif integration == 'openai':
            ok, msg = _test_openai(cfg)
        else:
            ok, msg = False, 'Unknown integration.'
    except Exception as exc:
        ok, msg = False, str(exc)

    _log(request.user, integration, 'test', 'success' if ok else 'error', msg)
    return JsonResponse({'ok': ok, 'msg': msg})



def _test_smtp(cfg):
    if getattr(cfg, 'auth_mode', 'password') == 'gmail_api_oauth':
        return _test_gmail_api(cfg)
    try:
        import smtplib
        use_ssl = getattr(cfg, 'use_ssl', False)
        port = cfg.port or (465 if use_ssl else 587)
        if use_ssl:
            server = smtplib.SMTP_SSL(cfg.host, port, timeout=8)
        else:
            server = smtplib.SMTP(cfg.host, port, timeout=8)
            if cfg.use_tls:
                server.starttls()
        server.login(cfg.username, cfg.password)
        server.quit()
        return True, f'SMTP connection successful (port {port}).'
    except ConnectionRefusedError:
        return False, f'SMTP error: Connection refused on port {cfg.port}. On Railway, try port 465 with SSL or use Gmail API OAuth2 / a relay service (Mailgun/Resend) on port 2525.'
    except OSError as e:
        if 'unreachable' in str(e).lower() or '101' in str(e):
            return False, 'SMTP error: Network unreachable from Railway. Use Gmail API OAuth2, Microsoft Graph, or a relay service on port 2525.'
        return False, f'SMTP error: {e}'
    except Exception as e:
        return False, f'SMTP error: {e}'


def _test_imap(cfg):
    try:
        import imaplib
        mail = imaplib.IMAP4_SSL(cfg.host, cfg.port or 993)
        mail.login(cfg.username, cfg.password)
        mail.logout()
        return True, 'IMAP connection successful.'
    except Exception as e:
        return False, f'IMAP error: {e}'


def _test_graph(cfg):
    try:
        import urllib.request, json
        req = urllib.request.Request(
            'https://graph.microsoft.com/v1.0/organization',
            headers={'Authorization': f'Bearer {cfg.access_token}'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get('value'):
            return True, 'Microsoft Graph token valid.'
        return False, 'Unexpected Graph response.'
    except Exception as e:
        return False, f'Microsoft Graph error: {e}'


def _test_whatsapp(cfg):
    try:
        import urllib.request, json
        url = f'https://graph.facebook.com/v18.0/{cfg.phone_number_id}'
        req = urllib.request.Request(
            url,
            headers={'Authorization': f'Bearer {cfg.access_token}'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get('id'):
            return True, f'WhatsApp API connected (Number ID: {data["id"]}).'
        return False, 'Unexpected response from Meta API.'
    except Exception as e:
        return False, f'WhatsApp API error: {e}'


def _test_webhook(cfg):
    try:
        import urllib.request, json
        payload = json.dumps({'text': 'IT Helpdesk webhook test: connection OK'}).encode()
        headers = {'Content-Type': 'application/json'}
        if cfg.access_token:
            headers['Authorization'] = f'Bearer {cfg.access_token}'
        req = urllib.request.Request(
            cfg.webhook_url,
            data=payload,
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True, f'Webhook responded with HTTP {resp.status}.'
    except Exception as e:
        return False, f'Webhook error: {e}'


def _test_openai(cfg):
    try:
        import urllib.request, json
        req = urllib.request.Request(
            (cfg.host or 'https://api.openai.com/v1').rstrip('/') + '/models',
            headers={'Authorization': f'Bearer {cfg.access_token}'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if isinstance(data.get('data'), list):
            return True, 'AI provider connection successful.'
        return False, 'Unexpected AI provider response.'
    except Exception as e:
        return False, f'AI provider error: {e}'
