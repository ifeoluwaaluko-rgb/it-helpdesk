import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from .models import ServiceCatalogItem, Ticket, TicketAttachment
from .forms import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_SIZE,
    TicketCategoryUpdateForm,
    TicketCommentForm,
    TicketCreateForm,
    TicketEditForm,
    TicketReassignForm,
    TicketStatusForm,
)
from .classifier import classify, CATEGORY_TREE
from .assignment import auto_assign
from .notifications import notify_assignment, notify_ticket_received
from .permissions import get_role, can_assign, can_delete_edit, is_helpdesk_staff
from .services import add_comment, pickup_ticket, reassign_ticket, update_ticket_category, update_ticket_fields, update_ticket_status
from .analytics import build_dashboard_metrics, build_staff_workload, calculate_agent_productivity
from knowledge.models import Article
import json
import re
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

STOP_WORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'have', 'been', 'cannot',
    'cant', 'into', 'your', 'you', 'are', 'was', 'were', 'not', 'but', 'when', 'what',
    'where', 'while', 'will', 'about', 'need', 'help', 'issue', 'problem', 'error',
    'ticket', 'please', 'after', 'before', 'does', 'doing', 'done', 'cannot', 'email'
}


def _build_triage_brief(ticket):
    signals = []
    if ticket.priority in ['high', 'critical']: signals.append(f'{ticket.get_priority_display()} priority')
    if ticket.impact in ['department', 'company']: signals.append(f'{ticket.get_impact_display()} impact')
    if ticket.approval_status == 'pending': signals.append('approval required')
    if ticket.is_sla_breached: signals.append('SLA breached')
    elif ticket.sla_state == 'yellow': signals.append('SLA at risk')
    if not signals: signals.append('standard workflow')
    return {'headline': f'{ticket.get_request_type_display()} routed to {ticket.get_category_display()}', 'signals': signals, 'action': ticket.next_best_action, 'risk_score': ticket.risk_score, 'health': ticket.health_label}


def _catalog_seed_items():
    return [
        {'name': 'New Starter Launch Kit', 'slug': 'new-starter-launch-kit', 'request_type': 'onboarding', 'category': 'onboarding', 'description': 'Provision laptop, accounts, groups, mailbox, and first-day access from one request.', 'fulfillment_hint': 'Create child tasks for device, identity, email, and app access.', 'default_priority': 'high', 'approval_required': True, 'estimated_hours': 16},
        {'name': 'Access To Business App', 'slug': 'access-to-business-app', 'request_type': 'access_request', 'category': 'access', 'description': 'Request access to finance, CRM, HR, analytics, or internal tools with approval tracking.', 'fulfillment_hint': 'Confirm manager approval and least-privilege role.', 'default_priority': 'medium', 'approval_required': True, 'estimated_hours': 8},
        {'name': 'Device Repair Or Replacement', 'slug': 'device-repair-replacement', 'request_type': 'hardware', 'category': 'hardware', 'description': 'Report broken laptops, phones, peripherals, or warranty repair needs.', 'fulfillment_hint': 'Link the asset record and check warranty before procurement.', 'default_priority': 'high', 'approval_required': False, 'estimated_hours': 24},
        {'name': 'Major Incident', 'slug': 'major-incident', 'request_type': 'incident', 'category': 'network', 'description': 'Use for outages, security-impacting events, or company-wide service disruption.', 'fulfillment_hint': 'Assign senior owner, start timeline, and update stakeholders every 30 minutes.', 'default_priority': 'critical', 'approval_required': False, 'estimated_hours': 2},
        {'name': 'Password Or MFA Recovery', 'slug': 'password-mfa-recovery', 'request_type': 'service_request', 'category': 'password', 'description': 'Restore account access, reset MFA, or recover locked accounts.', 'fulfillment_hint': 'Verify identity before reset and document method used.', 'default_priority': 'medium', 'approval_required': False, 'estimated_hours': 4},
        {'name': 'Software Install Request', 'slug': 'software-install-request', 'request_type': 'service_request', 'category': 'software', 'description': 'Request approved software, license allocation, or installation support.', 'fulfillment_hint': 'Check licensing and device compatibility before install.', 'default_priority': 'medium', 'approval_required': True, 'estimated_hours': 12},
    ]


def _ensure_catalog_seeded():
    if ServiceCatalogItem.objects.exists(): return
    ServiceCatalogItem.objects.bulk_create([ServiceCatalogItem(**item) for item in _catalog_seed_items()])


def _normalize_issue_signature(ticket):
    title = re.sub(r'[^a-z0-9\s]', ' ', (ticket.title or '').lower())
    tokens = []
    for token in title.split():
        if len(token) < 3 or token.isdigit() or token in STOP_WORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    keyword_string = ' '.join(tokens[:4]) or ticket.get_category_display().lower()
    return f"{ticket.get_category_display()}::{keyword_string}"


def _get_recurring_issue_summary(limit=5):
    recent_tickets = Ticket.objects.filter(created_at__date__gte=date.today() - timedelta(days=6))
    grouped = {}
    for ticket in recent_tickets:
        key = _normalize_issue_signature(ticket)
        item = grouped.setdefault(key, {
            'label': key.split('::', 1)[1].title(),
            'category': ticket.get_category_display(),
            'count': 0,
            'latest_ticket_id': ticket.id,
        })
        item['count'] += 1
        item['latest_ticket_id'] = max(item['latest_ticket_id'], ticket.id)
    recurring = [value for value in grouped.values() if value['count'] > 1]
    recurring.sort(key=lambda row: (-row['count'], row['category'], row['label']))
    return recurring[:limit]


def _knowledge_suggestions(ticket, limit=3):
    ticket_text = f"{ticket.title} {ticket.description} {ticket.category} {ticket.subcategory} {ticket.item}".lower()
    ticket_tokens = {
        token for token in re.findall(r'[a-z0-9]{3,}', ticket_text)
        if token not in STOP_WORDS
    }
    suggestions = []
    for article in Article.objects.all():
        article_text = f"{article.title} {article.tags} {article.content}".lower()
        article_tokens = {
            token for token in re.findall(r'[a-z0-9]{3,}', article_text)
            if token not in STOP_WORDS
        }
        overlap = ticket_tokens & article_tokens
        score = len(overlap)
        if article.category == ticket.category:
            score += 2
        if article.tags and ticket.item and ticket.item.lower() in article.tags.lower():
            score += 2
        if score <= 0:
            continue
        article.score = score
        plain_preview = re.sub(r'<[^>]+>', ' ', article.content)
        article.preview_text = re.sub(r'\s+', ' ', plain_preview).strip()
        suggestions.append(article)
    suggestions.sort(key=lambda article: (-article.score, -article.updated_at.timestamp()))
    return suggestions[:limit]

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/'
            if not url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                next_url = '/dashboard/'
            return redirect(next_url)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html', {'next': request.GET.get('next', '')})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user
    role = get_role(user)
    is_manager = role == 'manager'
    is_consultant = role in ('consultant', 'senior')

    all_tickets = Ticket.objects.select_related('assigned_to').all()
    my_tickets = all_tickets.filter(assigned_to=user).exclude(status__in=['resolved','closed'])
    unassigned = all_tickets.filter(assigned_to__isnull=True, status__in=['open'])
    metrics = build_dashboard_metrics(all_tickets)

    staff_workload = []
    if is_manager:
        staff_workload = build_staff_workload()

    personal_metrics = calculate_agent_productivity(all_tickets, user)

    recent = all_tickets[:15] if is_manager else my_tickets[:15]
    recurring_issues = _get_recurring_issue_summary() if is_manager else []

    kpis = [
        (metrics['open'],            'Open',        'text-[#1f73b7]', ''),
        (metrics['in_progress'],     'In Progress', 'text-[#f79a3e]', ''),
        (metrics['resolved'],        'Resolved',    'text-green-600', ''),
        (metrics['sla_breached'], 'SLA Breached', 'text-red-500' if metrics['sla_breached'] else 'text-[#68737d]', ''),
    ]

    context = {
        'my_tickets': my_tickets,
        'recent_tickets': recent,
        'unassigned_tickets': unassigned[:8],
        'is_manager': is_manager,
        'is_consultant': is_consultant,
        'role': role,
        'stats': {
            'total': metrics['total'], 'open': metrics['open'], 'in_progress': metrics['in_progress'],
            'resolved': metrics['resolved'], 'sla_breached': metrics['sla_breached'],
            'unassigned': unassigned.count(), 'sla_compliance': metrics['sla_compliance'],
            'avg_resolution': metrics['avg_resolution'],
            'avg_first_response': metrics['avg_first_response'],
            'at_risk': metrics['at_risk'],
            'awaiting_approval': metrics['awaiting_approval'],
            'high_impact': metrics['high_impact'],
            'automation_candidates': metrics['automation_candidates'],
            'backlog_health': metrics['backlog_health'],
        },
        'kpis': kpis,
        'sla_breached_ids': metrics['sla_breached_ids'],
        'staff_workload': staff_workload,
        'category_counts': metrics['category_counts'],
        'avg_resolution': metrics['avg_resolution'],
        'chart_labels': metrics['chart_labels'],
        'chart_data': metrics['chart_data'],
        'cat_resolution': metrics['cat_resolution'],
        'my_productivity': personal_metrics['productivity'],
        'my_resolved': personal_metrics['resolved'],
        'my_total_assigned': personal_metrics['total_assigned'],
        'recurring_issues': recurring_issues,
        'command_queue': sorted(list(all_tickets.exclude(status__in=['resolved','closed'])[:40]), key=lambda t: t.risk_score, reverse=True)[:6],
        'catalog_items': ServiceCatalogItem.objects.filter(is_active=True)[:6],
    }
    return render(request, 'dashboard.html', context)


@login_required
def ticket_list(request):
    tickets = Ticket.objects.select_related('assigned_to').all()
    q = request.GET.get('q','').strip()
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    category_filter = request.GET.get('category')
    assigned_filter = request.GET.get('mine')
    unassigned_filter = request.GET.get('unassigned')
    type_filter = request.GET.get('type')
    impact_filter = request.GET.get('impact')
    sort_filter = request.GET.get('sort') or 'newest'

    if q:
        tickets = tickets.filter(Q(title__icontains=q)|Q(description__icontains=q)|Q(user_email__icontains=q)|Q(requester_name__icontains=q))
    if status_filter: tickets = tickets.filter(status=status_filter)
    if priority_filter: tickets = tickets.filter(priority=priority_filter)
    if category_filter: tickets = tickets.filter(category=category_filter)
    if type_filter: tickets = tickets.filter(request_type=type_filter)
    if impact_filter: tickets = tickets.filter(impact=impact_filter)
    if assigned_filter == '1': tickets = tickets.filter(assigned_to=request.user)
    if unassigned_filter == '1': tickets = tickets.filter(assigned_to__isnull=True)
    if sort_filter == 'risk': tickets = sorted(list(tickets), key=lambda ticket: ticket.risk_score, reverse=True)
    elif sort_filter == 'sla': tickets = sorted(list(tickets), key=lambda ticket: ticket.sla_remaining_seconds)

    return render(request, 'ticket_list.html', {
        'tickets': tickets,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'type_choices': Ticket.REQUEST_TYPE_CHOICES,
        'impact_choices': Ticket.IMPACT_CHOICES,
        'filters': {'q':q,'status':status_filter,'priority':priority_filter, 'category':category_filter,'mine':assigned_filter,'unassigned':unassigned_filter, 'type': type_filter, 'impact': impact_filter, 'sort': sort_filter},
        'result_count': len(tickets) if isinstance(tickets, list) else tickets.count(),
    })


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    comments = ticket.comments.select_related('author').all()
    related_articles = _knowledge_suggestions(ticket)
    role = get_role(request.user)
    comment_form = TicketCommentForm()
    status_form = TicketStatusForm(initial={'status': ticket.status})
    category_form = TicketCategoryUpdateForm(initial={
        'category': ticket.category,
        'subcategory': ticket.subcategory,
        'item': ticket.item,
    })
    reassign_form = TicketReassignForm(initial={
        'user_id': ticket.assigned_to_id or '',
    })

    if request.method == 'POST':
        if not is_helpdesk_staff(request.user):
            messages.error(request, 'Only helpdesk staff can update tickets.')
            return redirect('ticket_detail', pk=pk)

        action = request.POST.get('action')

        if action == 'comment':
            comment_form = TicketCommentForm(request.POST)
            if comment_form.is_valid():
                add_comment(ticket, request.user, comment_form.cleaned_data['body'])
            else:
                for errors in comment_form.errors.values():
                    for error in errors:
                        messages.error(request, error)

        elif action == 'pickup' and not ticket.assigned_to:
            result = pickup_ticket(ticket, request.user)
            if result.message:
                messages.success(request, result.message)

        elif action == 'update_status':
            status_form = TicketStatusForm(request.POST)
            if status_form.is_valid():
                update_ticket_status(ticket, request.user, status_form.cleaned_data['status'])
            else:
                for errors in status_form.errors.values():
                    for error in errors:
                        messages.error(request, error)

        elif action == 'reassign' and can_assign(request.user):
            reassign_form = TicketReassignForm(request.POST)
            if reassign_form.is_valid():
                try:
                    reassign_ticket(ticket, reassign_form.cleaned_data['user_id'])
                except (ValueError, User.DoesNotExist):
                    messages.error(request, 'Invalid staff selection.')
            else:
                for errors in reassign_form.errors.values():
                    for error in errors:
                        messages.error(request, error)

        elif action == 'update_category':
            category_form = TicketCategoryUpdateForm(request.POST)
            if category_form.is_valid():
                result = update_ticket_category(
                    ticket,
                    request.user,
                    category_form.cleaned_data['category'],
                    category_form.cleaned_data['subcategory'],
                    category_form.cleaned_data['item'],
                )
                if result.message:
                    messages.success(request, result.message)
            else:
                for errors in category_form.errors.values():
                    for error in errors:
                        messages.error(request, error)

        return redirect('ticket_detail', pk=pk)

    staff_users = User.objects.filter(is_staff=True).select_related('profile') if can_assign(request.user) else []

    return render(request, 'ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'related_articles': related_articles,
        'staff_users': staff_users,
        'status_choices': Ticket.STATUS_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'category_tree_json': json.dumps(CATEGORY_TREE),
        'can_assign': can_assign(request.user),
        'can_edit': is_helpdesk_staff(request.user),
        'can_delete': can_delete_edit(request.user),
        'role': role,
        'triage_brief': _build_triage_brief(ticket),
        'comment_form': comment_form,
        'status_form': status_form,
        'category_form': category_form,
        'reassign_form': reassign_form,
    })


@login_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    can_edit_status = can_delete_edit(request.user)

    if not is_helpdesk_staff(request.user):
        messages.error(request, 'Only helpdesk staff can edit tickets.')
        return redirect('ticket_detail', pk=pk)

    initial = {
        'title': ticket.title,
        'description': ticket.description,
        'category': ticket.category,
        'subcategory': ticket.subcategory,
        'item': ticket.item,
        'priority': ticket.priority,
        'request_type': ticket.request_type,
        'impact': ticket.impact,
        'urgency': ticket.urgency,
        'approval_status': ticket.approval_status,
        'business_service': ticket.business_service,
        'status': ticket.status,
        'tags': ticket.tags,
        'edit_note': '',
    }
    form = TicketEditForm(
        request.POST or None,
        ticket=ticket,
        can_edit_status=can_edit_status,
        initial=initial,
    )

    if request.method == 'POST':
        if form.is_valid():
            try:
                result = update_ticket_fields(ticket, request.user, form.cleaned_data, can_edit_status)
                if result.message:
                    messages.success(request, result.message)
                return redirect('ticket_detail', pk=pk)
            except Exception as e:
                logger.exception('ticket_edit failed for ticket_id=%s user_id=%s', pk, request.user.id)
                messages.error(request, f'Could not save changes: {e}')
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

    return render(request, 'ticket_edit.html', {
        'ticket': ticket,
        'form': form,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'status_choices': Ticket.STATUS_CHOICES,
        'category_tree_json': json.dumps(CATEGORY_TREE),
        'can_edit_status': can_edit_status,
    })


@login_required
def ticket_history(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    history = ticket.edit_history.select_related('edited_by').all()
    return render(request, 'ticket_history.html', {'ticket': ticket, 'history': history})


@login_required
def ticket_delete(request, pk):
    if not can_delete_edit(request.user):
        messages.error(request, 'You do not have permission to delete tickets.')
        return redirect('ticket_detail', pk=pk)
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        ticket.delete()
        messages.success(request, f'Ticket #{pk} deleted.')
        return redirect('ticket_list')
    return render(request, 'ticket_confirm_delete.html', {'ticket': ticket})


@login_required
def create_ticket(request):
    from directory.models import StaffMember
    _ensure_catalog_seeded()
    catalog_slug = request.GET.get('catalog')
    selected_catalog_item = ServiceCatalogItem.objects.filter(slug=catalog_slug, is_active=True).first() if catalog_slug else None
    initial = {}
    if selected_catalog_item:
        initial = {'title': selected_catalog_item.name, 'description': selected_catalog_item.description, 'request_type': selected_catalog_item.request_type, 'catalog_item': selected_catalog_item}
    form = TicketCreateForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST':
        if form.is_valid():
            title = form.cleaned_data['title']
            description = form.cleaned_data['description']
            user_email = form.cleaned_data['user_email']
            channel = form.cleaned_data['channel']
            request_type = form.cleaned_data.get('request_type') or 'incident'
            impact = form.cleaned_data.get('impact') or 'single_user'
            urgency = form.cleaned_data.get('urgency') or 'normal'
            business_service = form.cleaned_data.get('business_service', '')
            catalog_item = form.cleaned_data.get('catalog_item') or selected_catalog_item
            staff_id = form.cleaned_data.get('staff_member')
            attachment = form.cleaned_data.get('attachment')
            try:
                result = classify(title, description)
                ticket = Ticket.objects.create(
                    title=title, description=description, user_email=user_email,
                    category=result.get('category', 'other'),
                    subcategory=result.get('subcategory', ''),
                    item=result.get('item', ''),
                    priority=(catalog_item.default_priority if catalog_item else result.get('priority', 'medium')),
                    request_type=request_type, impact=impact, urgency=urgency,
                    approval_status='pending' if catalog_item and catalog_item.approval_required else 'not_required',
                    business_service=business_service, catalog_item=catalog_item,
                    required_level=result.get('level', 'associate'),
                    sla_hours=(catalog_item.estimated_hours if catalog_item else result.get('sla_hours', 24)),
                    channel=channel,
                    external_message_id='',
                )
                if staff_id:
                    try:
                        sm = StaffMember.objects.get(pk=int(staff_id))
                        ticket.requester_name = sm.full_name
                        ticket.save()
                    except (StaffMember.DoesNotExist, ValueError):
                        pass

                if attachment:
                    TicketAttachment.objects.create(
                        ticket=ticket,
                        file=attachment,
                        filename=attachment.name,
                        content_type=getattr(attachment, 'content_type', '') or '',
                        source='manual',
                    )

                notify_ticket_received(ticket)

                try:
                    assignee = auto_assign(ticket)
                    if assignee:
                        ticket.assigned_to = assignee
                        ticket.save()
                        notify_assignment(ticket, assignee)
                except Exception:
                    pass
                messages.success(request, f'Ticket #{ticket.id} created.')
                return redirect('ticket_detail', pk=ticket.id)
            except Exception as e:
                logger.exception('Ticket create failed')
                messages.error(request, f'Could not create ticket: {e}')
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

    staff_members = []
    try:
        staff_members = StaffMember.objects.filter(is_active=True).order_by('first_name')
    except Exception:
        pass

    return render(request, 'create_ticket.html', {
        'form': form,
        'staff_members': staff_members,
        'channel_choices': Ticket.CHANNEL_CHOICES,
        'type_choices': Ticket.REQUEST_TYPE_CHOICES,
        'impact_choices': Ticket.IMPACT_CHOICES,
        'urgency_choices': Ticket.URGENCY_CHOICES,
        'catalog_items': ServiceCatalogItem.objects.filter(is_active=True),
        'selected_catalog_item': selected_catalog_item,
        'allowed_attachment_types': ', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS)),
        'max_attachment_mb': 10,
    })


@login_required
def request_catalog(request):
    _ensure_catalog_seeded()
    q = request.GET.get('q', '').strip()
    request_type = request.GET.get('type', '').strip()
    items = ServiceCatalogItem.objects.filter(is_active=True)
    if q: items = items.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(fulfillment_hint__icontains=q))
    if request_type: items = items.filter(request_type=request_type)
    return render(request, 'catalog.html', {'items': items, 'filters': {'q': q, 'type': request_type}, 'type_choices': ServiceCatalogItem.REQUEST_TYPES})


@login_required
def live_dashboard(request):
    all_tickets = Ticket.objects.all()
    metrics = build_dashboard_metrics(all_tickets)
    agents = build_staff_workload()
    total_assigned = all_tickets.exclude(assigned_to__isnull=True).count()
    productivity = round((metrics['resolved'] / total_assigned) * 100) if total_assigned > 0 else 0
    return render(request, 'live_dashboard.html', {
        'open':metrics['open'],'in_progress':metrics['in_progress'],'resolved':metrics['resolved'],
        'total':metrics['total'],'sla_compliance':metrics['sla_compliance'],'avg_resolution':metrics['avg_resolution'],
        'productivity':productivity,'sla_breached':metrics['sla_breached'],'agents':agents,
    })


@login_required
def staff_search_api(request):
    from directory.models import StaffMember
    if not is_helpdesk_staff(request.user):
        return JsonResponse({'results': []}, status=403)
    q = request.GET.get('q','').strip()
    if len(q) < 2: return JsonResponse({'results':[]})
    members = StaffMember.objects.filter(
        Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(email__icontains=q), is_active=True
    )[:10]
    return JsonResponse({'results':[
        {'id':m.id,'name':m.full_name,'email':m.email,'department':m.department.name if m.department else ''}
        for m in members
    ]})


@login_required
def subcategory_api(request):
    """Return subcategories for a given category slug."""
    from .classifier import CATEGORY_TREE
    cat = request.GET.get('category','')
    data = CATEGORY_TREE.get(cat, {})
    subs = list(data.get('subcategories',{}).keys())
    return JsonResponse({'subcategories': subs})


@login_required
def item_api(request):
    """Return items for a given category + subcategory."""
    from .classifier import CATEGORY_TREE
    cat = request.GET.get('category','')
    sub = request.GET.get('subcategory','')
    data = CATEGORY_TREE.get(cat,{}).get('subcategories',{}).get(sub,[])
    return JsonResponse({'items': data})
