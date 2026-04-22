from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import IntegrationConfig


def _is_superadmin(user):
    try:
        return user.profile.role == 'superadmin'
    except Exception:
        return False


def _require_superadmin(request):
    """Returns True if access is allowed, sets error message if not."""
    if not _is_superadmin(request.user):
        messages.error(request,
            'Access denied. Only Super Admins can manage system settings.')
        return False
    return True


# ── Helpers to get-or-create each integration row ────────────────────────────
INTEGRATION_KEYS = ['email_smtp', 'email_imap', 'whatsapp', 'teams', 'slack']


def _get_configs():
    configs = {}
    for key in INTEGRATION_KEYS:
        obj, _ = IntegrationConfig.objects.get_or_create(integration=key)
        configs[key] = obj
    return configs


# ── Main settings page ────────────────────────────────────────────────────────
@login_required
def settings_home(request):
    if not _require_superadmin(request):
        return redirect('dashboard')
    configs = _get_configs()
    return render(request, 'settings/home.html', {'configs': configs})


# ── SMTP ──────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def save_smtp(request):
    if not _require_superadmin(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='email_smtp')
    cfg.host     = request.POST.get('host', '').strip()
    cfg.port     = int(request.POST.get('port', 587) or 587)
    cfg.username = request.POST.get('username', '').strip()
    cfg.use_tls  = request.POST.get('use_tls') == 'on'
    cfg.is_active = request.POST.get('is_active') == 'on'
    pw = request.POST.get('password', '').strip()
    if pw:                        # only update if a new value was entered
        cfg.password = pw
    cfg.updated_by = request.user
    cfg.save()
    _apply_smtp_to_django(cfg)
    messages.success(request, 'SMTP settings saved.')
    return redirect('settings_home')


def _apply_smtp_to_django(cfg):
    """Push live values into Django settings so emails work immediately."""
    from django.conf import settings as dj_settings
    dj_settings.EMAIL_HOST          = cfg.host
    dj_settings.EMAIL_PORT          = cfg.port or 587
    dj_settings.EMAIL_HOST_USER     = cfg.username
    dj_settings.EMAIL_HOST_PASSWORD = cfg.password
    dj_settings.EMAIL_USE_TLS       = cfg.use_tls


# ── IMAP ──────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def save_imap(request):
    if not _require_superadmin(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='email_imap')
    cfg.host     = request.POST.get('host', '').strip()
    cfg.port     = int(request.POST.get('port', 993) or 993)
    cfg.username = request.POST.get('username', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    pw = request.POST.get('password', '').strip()
    if pw:
        cfg.password = pw
    cfg.updated_by = request.user
    cfg.save()
    _apply_imap_to_django(cfg)
    messages.success(request, 'IMAP settings saved.')
    return redirect('settings_home')


def _apply_imap_to_django(cfg):
    from django.conf import settings as dj_settings
    dj_settings.IMAP_HOST     = cfg.host
    dj_settings.IMAP_PORT     = cfg.port or 993
    dj_settings.IMAP_USER     = cfg.username
    dj_settings.IMAP_PASSWORD = cfg.password


# ── WhatsApp Business Cloud API ───────────────────────────────────────────────
@login_required
@require_POST
def save_whatsapp(request):
    if not _require_superadmin(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='whatsapp')
    cfg.phone_number_id = request.POST.get('phone_number_id', '').strip()
    cfg.wa_business_id  = request.POST.get('wa_business_id', '').strip()
    cfg.is_active = request.POST.get('is_active') == 'on'
    token = request.POST.get('access_token', '').strip()
    if token:
        cfg.access_token = token
    cfg.updated_by = request.user
    cfg.save()
    messages.success(request, 'WhatsApp settings saved.')
    return redirect('settings_home')


# ── Teams Webhook ─────────────────────────────────────────────────────────────
@login_required
@require_POST
def save_teams(request):
    if not _require_superadmin(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='teams')
    cfg.webhook_url = request.POST.get('webhook_url', '').strip()
    cfg.is_active   = request.POST.get('is_active') == 'on'
    cfg.updated_by  = request.user
    cfg.save()
    messages.success(request, 'Microsoft Teams webhook saved.')
    return redirect('settings_home')


# ── Slack Webhook ─────────────────────────────────────────────────────────────
@login_required
@require_POST
def save_slack(request):
    if not _require_superadmin(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='slack')
    cfg.webhook_url = request.POST.get('webhook_url', '').strip()
    cfg.is_active   = request.POST.get('is_active') == 'on'
    cfg.updated_by  = request.user
    cfg.save()
    messages.success(request, 'Slack webhook saved.')
    return redirect('settings_home')


# ── Test connection (AJAX) ────────────────────────────────────────────────────
@login_required
def test_connection(request, integration):
    if not _is_superadmin(request.user):
        return JsonResponse({'ok': False, 'msg': 'Permission denied.'})
    try:
        cfg = IntegrationConfig.objects.get(integration=integration)
    except IntegrationConfig.DoesNotExist:
        return JsonResponse({'ok': False, 'msg': 'Not configured yet.'})

    if integration == 'email_smtp':
        ok, msg = _test_smtp(cfg)
    elif integration == 'email_imap':
        ok, msg = _test_imap(cfg)
    elif integration == 'whatsapp':
        ok, msg = _test_whatsapp(cfg)
    elif integration in ('teams', 'slack'):
        ok, msg = _test_webhook(cfg)
    else:
        ok, msg = False, 'Unknown integration.'
    return JsonResponse({'ok': ok, 'msg': msg})


def _test_smtp(cfg):
    try:
        import smtplib
        server = smtplib.SMTP(cfg.host, cfg.port or 587, timeout=8)
        if cfg.use_tls:
            server.starttls()
        server.login(cfg.username, cfg.password)
        server.quit()
        return True, 'SMTP connection successful ✓'
    except Exception as e:
        return False, f'SMTP error: {e}'


def _test_imap(cfg):
    try:
        import imaplib
        mail = imaplib.IMAP4_SSL(cfg.host, cfg.port or 993)
        mail.login(cfg.username, cfg.password)
        mail.logout()
        return True, 'IMAP connection successful ✓'
    except Exception as e:
        return False, f'IMAP error: {e}'


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
            return True, f'WhatsApp API connected ✓ (Number ID: {data["id"]})'
        return False, 'Unexpected response from Meta API.'
    except Exception as e:
        return False, f'WhatsApp API error: {e}'


def _test_webhook(cfg):
    try:
        import urllib.request, json
        payload = json.dumps({'text': '✅ IT Helpdesk webhook test — connection OK'}).encode()
        req = urllib.request.Request(
            cfg.webhook_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True, f'Webhook responded with HTTP {resp.status} ✓'
    except Exception as e:
        return False, f'Webhook error: {e}'
