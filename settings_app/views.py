
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import IntegrationConfig, IntegrationAuditLog
from .services import (
    IntegrationConfigError,
    get_configs,
    log_integration_event,
    save_graph_config,
    save_imap_config,
    save_openai_config,
    save_simple_webhook_config,
    save_smtp_config,
    save_webhook_config,
    save_whatsapp_config,
    test_graph,
    test_imap,
    test_openai,
    test_smtp,
    test_webhook,
    test_whatsapp,
)
from tickets.permissions import can_manage_settings, get_role
from tickets.models import TicketCategory, Ticket


def _role(user):
    return get_role(user)


def _can_manage(user):
    return can_manage_settings(user)


def _require_manager(request):
    if not _can_manage(request.user):
        messages.error(request, 'Access denied. Only Managers can manage integrations.')
        return False
    return True


@login_required
def settings_home(request):
    if not _require_manager(request):
        return redirect('dashboard')
    configs = get_configs()
    recent_logs = IntegrationAuditLog.objects.select_related('actor')[:20]

    categories = TicketCategory.objects.prefetch_related('subcategories').all()
    category_rows = []
    for category in categories:
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
    try:
        message = save_smtp_config(cfg, request.POST, request.user)
        log_integration_event(request.user, 'email_smtp', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'email_smtp', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_imap(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='email_imap')
    try:
        message = save_imap_config(cfg, request.POST, request.user)
        log_integration_event(request.user, 'email_imap', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'email_imap', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_graph(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='microsoft_graph')
    try:
        message = save_graph_config(cfg, request.POST, request.user)
        log_integration_event(request.user, 'microsoft_graph', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'microsoft_graph', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_whatsapp(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='whatsapp')
    try:
        message = save_whatsapp_config(cfg, request.POST, request.user)
        log_integration_event(request.user, 'whatsapp', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'whatsapp', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_teams(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='teams')
    try:
        message = save_simple_webhook_config(cfg, request.POST, request.user, 'Microsoft Teams webhook')
        log_integration_event(request.user, 'teams', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'teams', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_slack(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='slack')
    try:
        message = save_simple_webhook_config(cfg, request.POST, request.user, 'Slack webhook')
        log_integration_event(request.user, 'slack', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'slack', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_generic_webhook(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='generic_webhook')
    try:
        message = save_webhook_config(cfg, request.POST, request.user, 'Generic webhook')
        log_integration_event(request.user, 'generic_webhook', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'generic_webhook', 'save', 'error', str(exc))
        messages.error(request, str(exc))
    return redirect('settings_home')


@login_required
@require_POST
def save_openai(request):
    if not _require_manager(request):
        return redirect('settings_home')
    cfg, _ = IntegrationConfig.objects.get_or_create(integration='openai')
    try:
        message = save_openai_config(cfg, request.POST, request.user)
        log_integration_event(request.user, 'openai', 'save', 'success', message)
        messages.success(request, message)
    except IntegrationConfigError as exc:
        log_integration_event(request.user, 'openai', 'save', 'error', str(exc))
        messages.error(request, str(exc))
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
            result = test_smtp(cfg)
        elif integration == 'email_imap':
            result = test_imap(cfg)
        elif integration == 'microsoft_graph':
            result = test_graph(cfg)
        elif integration == 'whatsapp':
            result = test_whatsapp(cfg)
        elif integration in ('teams', 'slack', 'generic_webhook'):
            result = test_webhook(cfg)
        elif integration == 'openai':
            result = test_openai(cfg)
        else:
            result = None
            msg = 'Unknown integration.'
    except Exception as exc:
        result = None
        msg = str(exc)

    if result is None:
        ok = False
    else:
        ok = result.ok
        msg = result.message

    log_integration_event(request.user, integration, 'test', 'success' if ok else 'error', msg)
    return JsonResponse({'ok': ok, 'msg': msg})
