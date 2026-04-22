import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Q, Avg, Case, When, F, IntegerField, DurationField, ExpressionWrapper
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, Http404, FileResponse
from django.db import transaction
from .models import Ticket, TicketComment, TicketEditHistory, Profile, TicketAttachment, TicketEvent
from .classifier import classify, CATEGORY_TREE
from .assignment import auto_assign
from .notifications import notify_assignment, notify_status_change, notify_ticket_received
from knowledge.models import Article
import json
import re
from datetime import date, timedelta
from django.db.models.functions import TruncDate
import logging
from pathlib import Path
import mimetypes
from types import SimpleNamespace

logger = logging.getLogger(__name__)

ALLOWED_ATTACHMENT_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.docx', '.xlsx', '.txt', '.zip'}
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB


STOP_WORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'have', 'been', 'cannot',
    'cant', 'into', 'your', 'you', 'are', 'was', 'were', 'not', 'but', 'when', 'what',
    'where', 'while', 'will', 'about', 'need', 'help', 'issue', 'problem', 'error',
    'ticket', 'please', 'after', 'before', 'does', 'doing', 'done', 'cannot', 'email'
}


def setup_required():
    return not User.objects.exists()




def _mark_first_response(ticket):
    if not ticket.first_response_at:
        ticket.first_response_at = timezone.now()
        ticket.save(update_fields=['first_response_at', 'updated_at'])




def _log_status_event(ticket, actor, action, from_status='', to_status='', note=''):
    TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=action,
        from_status=from_status or '',
        to_status=to_status or ticket.status,
        note=(note or '')[:255],
    )


def _get_status_events(ticket):
    label_map = dict(TicketEvent.EVENT_CHOICES)
    events = [
        SimpleNamespace(
            action='created',
            action_display='Created',
            created_at=ticket.created_at,
            actor=None,
            from_status='',
            to_status=ticket.status,
            note='Ticket created',
        )
    ]

    for event in ticket.events.select_related('actor').all():
        events.append(
            SimpleNamespace(
                action=event.event_type,
                action_display=label_map.get(event.event_type, event.event_type.replace('_', ' ').title()),
                created_at=event.created_at,
                actor=event.actor,
                from_status=event.from_status,
                to_status=event.to_status,
                note=event.note,
            )
        )

    events.sort(key=lambda e: e.created_at, reverse=True)
    return events[:20]


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



def get_role(user):
    try: return user.profile.role
    except: return 'associate'


def can_assign(user):
    return get_role(user) in ('manager', 'consultant', 'senior')


def can_delete_edit(user):
    return get_role(user) in ('manager', 'consultant', 'senior')


def login_view(request):
    if setup_required():
        return redirect('first_time_setup')
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/'
            return redirect(next_url)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html', {'next': request.GET.get('next', '')})



def first_time_setup(request):
    if not setup_required():
        messages.info(request, 'Initial setup has already been completed. Please sign in.')
        return redirect('login')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not username:
            errors.append('Username is required.')
        if not email:
            errors.append('Email is required.')
        if not password:
            errors.append('Password is required.')
        if password and len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if username and User.objects.filter(username=username).exists():
            errors.append('That username is already taken.')
        if email and User.objects.filter(email=email).exists():
            errors.append('That email is already in use.')

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            first_name = full_name.split()[0]
            last_name = ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True,
                    is_superuser=True,
                )
                Profile.objects.update_or_create(
                    user=user,
                    defaults={'role': 'superadmin'}
                )
                login(request, user)
                messages.success(request, 'Setup complete. Welcome to IT Helpdesk.')
                return redirect('dashboard')

    context = {
        'setup_mode': True,
        'any_users_exist': User.objects.exists(),
    }
    return render(request, 'setup_first_admin.html', context)


def logout_view(request):
    logout(request)
    return redirect('login')



@login_required
def dashboard(request):
    user = request.user
    role = get_role(user)
    is_manager = role == 'manager'
    is_consultant = role in ('consultant', 'senior')

    all_tickets = Ticket.objects.select_related('assigned_to')
    active_statuses = ['open', 'in_progress', 'pending']
    base_counts = all_tickets.aggregate(
        total=Count('id'),
        open=Count('id', filter=Q(status='open')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        resolved=Count('id', filter=Q(status='resolved')),
        unassigned=Count('id', filter=Q(assigned_to__isnull=True, status='open')),
        my_total=Count('id', filter=Q(assigned_to=user)),
        my_resolved=Count('id', filter=Q(assigned_to=user, status__in=['resolved', 'closed'])),
    )

    my_tickets = all_tickets.filter(assigned_to=user).exclude(status__in=['resolved', 'closed'])
    unassigned = all_tickets.filter(assigned_to__isnull=True, status='open')
    recent = all_tickets.order_by('-created_at')[:15] if is_manager else my_tickets.order_by('-created_at')[:15]

    sla_candidates = list(all_tickets.filter(status__in=active_statuses).only('id', 'created_at', 'priority', 'status', 'resolved_at', 'sla_deadline'))
    sla_breached_ids = [t.id for t in sla_candidates if t.is_sla_breached]

    closed = list(all_tickets.filter(status__in=['resolved', 'closed']).only('resolved_at', 'sla_deadline'))
    sla_ok = sum(1 for t in closed if t.resolved_at and t.sla_deadline and t.resolved_at <= t.sla_deadline)
    sla_compliance = round((sla_ok / len(closed)) * 100) if closed else 100

    resolved_tickets = list(all_tickets.filter(resolved_at__isnull=False).only('category', 'created_at', 'resolved_at'))
    resolution_seconds = [t.resolution_time_seconds for t in resolved_tickets if t.resolution_time_seconds is not None]
    avg_resolution = round(sum(resolution_seconds) / len(resolution_seconds)) if resolution_seconds else 0

    first_response_tickets = list(all_tickets.filter(first_response_at__isnull=False).only('created_at', 'first_response_at'))
    first_response_values = [t.first_response_seconds for t in first_response_tickets if t.first_response_seconds is not None]
    avg_first_response = round(sum(first_response_values) / len(first_response_values)) if first_response_values else 0

    today = date.today()
    raw_chart = {
        row['day'].date(): row['count']
        for row in all_tickets.annotate(day=TruncDate('created_at')).values('day').annotate(count=Count('id'))
        if row['day']
    }
    chart_labels, chart_data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%b %d'))
        chart_data.append(raw_chart.get(day, 0))

    category_counts = all_tickets.values('category').annotate(count=Count('id')).order_by('-count')

    cat_resolution = {}
    by_cat = {}
    for t in resolved_tickets:
        secs = t.resolution_time_seconds
        if secs is None:
            continue
        by_cat.setdefault(t.category, []).append(secs)
    for cat, values in by_cat.items():
        if values:
            cat_resolution[cat] = round(sum(values) / len(values))

    staff_workload = []
    if is_manager:
        staff_workload = list(
            User.objects.filter(is_staff=True)
            .annotate(open_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['open', 'in_progress'])))
            .order_by('-open_count')
        )

    my_total_assigned = base_counts['my_total'] or 0
    my_resolved = base_counts['my_resolved'] or 0
    my_productivity = round((my_resolved / my_total_assigned) * 100) if my_total_assigned > 0 else 0
    recurring_issues = _get_recurring_issue_summary() if is_manager else []

    kpis = [
        (base_counts['open'] or 0, 'Open', 'text-[#1f73b7]', ''),
        (base_counts['in_progress'] or 0, 'In Progress', 'text-[#f79a3e]', ''),
        (base_counts['resolved'] or 0, 'Resolved', 'text-green-600', ''),
        (len(sla_breached_ids), 'SLA Breached', 'text-red-500' if sla_breached_ids else 'text-[#68737d]', ''),
    ]

    context = {
        'my_tickets': my_tickets,
        'recent_tickets': recent,
        'unassigned_tickets': unassigned[:8],
        'is_manager': is_manager,
        'is_consultant': is_consultant,
        'role': role,
        'stats': {
            'total': base_counts['total'] or 0,
            'open': base_counts['open'] or 0,
            'in_progress': base_counts['in_progress'] or 0,
            'resolved': base_counts['resolved'] or 0,
            'sla_breached': len(sla_breached_ids),
            'unassigned': base_counts['unassigned'] or 0,
            'sla_compliance': sla_compliance,
            'avg_resolution': avg_resolution,
            'avg_first_response': avg_first_response,
        },
        'kpis': kpis,
        'sla_breached_ids': sla_breached_ids,
        'staff_workload': staff_workload,
        'category_counts': category_counts,
        'avg_resolution': avg_resolution,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'cat_resolution': cat_resolution,
        'my_productivity': my_productivity,
        'my_resolved': my_resolved,
        'my_total_assigned': my_total_assigned,
        'recurring_issues': recurring_issues,
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

    if q:
        tickets = tickets.filter(Q(title__icontains=q)|Q(description__icontains=q)|Q(user_email__icontains=q)|Q(requester_name__icontains=q))
    if status_filter: tickets = tickets.filter(status=status_filter)
    if priority_filter: tickets = tickets.filter(priority=priority_filter)
    if category_filter: tickets = tickets.filter(category=category_filter)
    if assigned_filter == '1': tickets = tickets.filter(assigned_to=request.user)
    if unassigned_filter == '1': tickets = tickets.filter(assigned_to__isnull=True)

    return render(request, 'ticket_list.html', {
        'tickets': tickets,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'filters': {'q':q,'status':status_filter,'priority':priority_filter,
                    'category':category_filter,'mine':assigned_filter,'unassigned':unassigned_filter},
        'result_count': tickets.count(),
    })


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    comments = ticket.comments.select_related('author').all()
    related_articles = _knowledge_suggestions(ticket)
    role = get_role(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'comment':
            body = request.POST.get('body','').strip()
            if body:
                TicketComment.objects.create(ticket=ticket, author=request.user, body=body)
                TicketEvent.objects.create(ticket=ticket, actor=request.user, event_type='commented', from_status=ticket.status, to_status=ticket.status, note='Internal comment added.')
                _mark_first_response(ticket)

        elif action == 'pickup' and not ticket.assigned_to:
            previous_status = ticket.status
            ticket.assigned_to = request.user
            ticket.status = 'in_progress'
            ticket.save()
            _mark_first_response(ticket)
            notify_assignment(ticket, request.user)
            _log_status_event(ticket, request.user, 'picked_up', from_status=previous_status, to_status='in_progress', note=f'Picked up by {request.user.get_full_name() or request.user.username}.')
            messages.success(request, f'You picked up ticket #{ticket.id}.')

        elif action == 'update_status':
            new_status = request.POST.get('status', '').strip()
            valid_statuses = [s for s, _ in Ticket.STATUS_CHOICES]

            if not new_status or new_status not in valid_statuses:
                messages.error(request, 'Invalid status selection.')
                return redirect('ticket_detail', pk=pk)

            try:
                old_status = ticket.status
                update_fields = ['status', 'updated_at']

                ticket.status = new_status

                if new_status in ['resolved', 'closed']:
                    if not ticket.resolved_at:
                        ticket.resolved_at = timezone.now()
                        update_fields.append('resolved_at')
                elif new_status in ['open', 'in_progress', 'pending']:
                    if ticket.resolved_at:
                        ticket.resolved_at = None
                        update_fields.append('resolved_at')

                ticket.save(update_fields=update_fields)

                if new_status in ['in_progress', 'pending', 'resolved', 'closed']:
                    _mark_first_response(ticket)

                if new_status != old_status:
                    action_name = 'status_changed'
                    note = ''
                    if new_status == 'resolved':
                        action_name = 'resolved'
                        note = f'Resolved by {request.user.get_full_name() or request.user.username}.'
                    elif new_status == 'closed':
                        action_name = 'closed'
                        note = f'Closed by {request.user.get_full_name() or request.user.username}.'
                    elif old_status in ['resolved', 'closed'] and new_status in ['open', 'in_progress', 'pending']:
                        action_name = 'reopened'
                        note = f'Reopened by {request.user.get_full_name() or request.user.username}.'

                    _log_status_event(ticket, request.user, action_name, from_status=old_status, to_status=new_status, note=note)

                    notify_status_change(ticket, request.user)
                    messages.success(
                        request,
                        f'Ticket #{ticket.id} status updated from {dict(Ticket.STATUS_CHOICES).get(old_status, old_status)} to {ticket.get_status_display()}.'
                    )
                else:
                    messages.info(request, f'Ticket #{ticket.id} is already marked as {ticket.get_status_display()}.')
            except RuntimeError:
                logger.exception('Failed to update status for ticket %s', ticket.id)
                messages.error(request, 'We could not update the ticket status. Please try again.')

        elif action == 'reassign' and can_assign(request.user):
            uid = request.POST.get('user_id', '').strip()
            if uid:
                try:
                    old = ticket.assigned_to
                    ticket.assigned_to_id = int(uid)
                    ticket.save()
                    ticket.refresh_from_db()
                    if ticket.assigned_to and (not old or old.id != ticket.assigned_to.id):
                        notify_assignment(ticket, ticket.assigned_to)
                        _mark_first_response(ticket)
                        action_name = 'reassigned' if old else 'assigned'
                        note = f'Assigned to {ticket.assigned_to.get_full_name() or ticket.assigned_to.username}'
                        if old:
                            note = f'Reassigned from {old.get_full_name() or old.username} to {ticket.assigned_to.get_full_name() or ticket.assigned_to.username}'
                        _log_status_event(ticket, request.user, action_name, from_status=ticket.status, to_status=ticket.status, note=note)
                        if old:
                            messages.success(request, f'Ticket #{ticket.id} reassigned from {old.get_full_name() or old.username} to {ticket.assigned_to.get_full_name() or ticket.assigned_to.username}.')
                        else:
                            messages.success(request, f'Ticket #{ticket.id} assigned to {ticket.assigned_to.get_full_name() or ticket.assigned_to.username}.')
                    else:
                        messages.info(request, 'Ticket assignee is unchanged.')
                except (ValueError, User.DoesNotExist):
                    messages.error(request, 'Invalid staff selection.')
            else:
                messages.error(request, 'Please choose a staff member to reassign this ticket.')

        elif action == 'update_category':
            # Save snapshot before changing
            TicketEditHistory.objects.create(
                ticket=ticket, edited_by=request.user,
                title=ticket.title, description=ticket.description,
                category=ticket.category, subcategory=ticket.subcategory,
                item=ticket.item, priority=ticket.priority, status=ticket.status,
                edit_note='Category updated',
            )
            ticket.category = request.POST.get('category', ticket.category)
            ticket.subcategory = request.POST.get('subcategory', '')
            ticket.item = request.POST.get('item', '')
            ticket.save()
            TicketEvent.objects.create(ticket=ticket, actor=request.user, event_type='category_updated', from_status=ticket.status, to_status=ticket.status, note='Category/subcategory/item updated.')
            messages.success(request, 'Category updated.')

        return redirect('ticket_detail', pk=pk)

    staff_users = User.objects.filter(is_staff=True).select_related('profile') if can_assign(request.user) else []
    status_events = _get_status_events(ticket)
    resolved_event = next((event for event in status_events if event.action in ['resolved', 'closed']), None)

    return render(request, 'ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'related_articles': related_articles,
        'staff_users': staff_users,
        'status_events': status_events,
        'resolved_event': resolved_event,
        'status_choices': Ticket.STATUS_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'category_tree_json': json.dumps(CATEGORY_TREE),
        'can_assign': can_assign(request.user),
        'can_edit': True,  # all staff can edit
        'can_delete': can_delete_edit(request.user),
        'role': role,
    })


@login_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    role = get_role(request.user)

    if request.method == 'POST':
        try:
            edit_note = request.POST.get('edit_note', '').strip()
            TicketEditHistory.objects.create(
                ticket=ticket, edited_by=request.user,
                title=ticket.title, description=ticket.description,
                category=ticket.category, subcategory=ticket.subcategory,
                item=ticket.item, priority=ticket.priority, status=ticket.status,
                edit_note=edit_note or 'Edited',
            )
            valid_priorities = [p for p, _ in Ticket.PRIORITY_CHOICES]
            valid_statuses   = [s for s, _ in Ticket.STATUS_CHOICES]
            valid_categories = [c for c, _ in Ticket.CATEGORY_CHOICES]
            new_title = request.POST.get('title', ticket.title).strip()
            new_desc  = request.POST.get('description', ticket.description).strip()
            new_cat   = request.POST.get('category', ticket.category)
            new_pri   = request.POST.get('priority', ticket.priority)
            ticket.title       = new_title or ticket.title
            ticket.description = new_desc  or ticket.description
            ticket.category    = new_cat if new_cat in valid_categories else ticket.category
            ticket.subcategory = request.POST.get('subcategory', '')
            ticket.item        = request.POST.get('item', '')
            ticket.priority    = new_pri if new_pri in valid_priorities else ticket.priority
            ticket.tags        = request.POST.get('tags', ticket.tags)
            if can_delete_edit(request.user):
                new_status = request.POST.get('status', ticket.status)
                ticket.status = new_status if new_status in valid_statuses else ticket.status
                if ticket.status == 'resolved' and not ticket.resolved_at:
                    ticket.resolved_at = timezone.now()
            ticket.save()
            messages.success(request, f'Ticket #{ticket.id} updated.')
            return redirect('ticket_detail', pk=pk)
        except (ValueError, RuntimeError) as e:
            logger.exception('ticket_edit failed for ticket_id=%s user_id=%s', pk, request.user.id)
            messages.error(request, f'Could not save changes: {e}')

    return render(request, 'ticket_edit.html', {
        'ticket': ticket,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'status_choices': Ticket.STATUS_CHOICES,
        'category_tree_json': json.dumps(CATEGORY_TREE),
        'can_edit_status': can_delete_edit(request.user),
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
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        user_email = request.POST.get('user_email', '').strip()
        channel = request.POST.get('channel', 'manual')
        staff_id = request.POST.get('staff_member', '').strip()
        attachment = request.FILES.get('attachment')

        valid_channels = [c for c, _ in Ticket.CHANNEL_CHOICES]
        if channel not in valid_channels:
            channel = 'manual'

        if not (title and description and user_email):
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                result = classify(title, description)
                with transaction.atomic():
                    ticket = Ticket.objects.create(
                        title=title, description=description, user_email=user_email,
                        category=result.get('category', 'other'),
                        subcategory=result.get('subcategory', ''),
                        item=result.get('item', ''),
                        priority=result.get('priority', 'medium'),
                        required_level=result.get('level', 'associate'),
                        sla_hours=result.get('sla_hours', 24),
                        channel=channel,
                    )
                    TicketEvent.objects.create(ticket=ticket, actor=request.user, event_type='created', to_status=ticket.status, note='Ticket created manually.')

                    if staff_id:
                        try:
                            sm = StaffMember.objects.get(pk=int(staff_id))
                            ticket.requester_name = sm.full_name
                            ticket.save(update_fields=['requester_name'])
                        except (StaffMember.DoesNotExist, ValueError):
                            logger.warning('Invalid staff member selected for ticket create: %s', staff_id)

                    if attachment:
                        ext = os.path.splitext(attachment.name)[1].lower()
                        if attachment.size > MAX_ATTACHMENT_SIZE:
                            messages.warning(request, 'Attachment was skipped because it exceeded the 10 MB limit.')
                        elif ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
                            messages.warning(request, 'Attachment type is not allowed and was skipped.')
                        else:
                            TicketAttachment.objects.create(
                                ticket=ticket,
                                file=attachment,
                                filename=attachment.name,
                                content_type=getattr(attachment, 'content_type', '') or '',
                                source='manual',
                            )

                    assignee = auto_assign(ticket)
                    if assignee:
                        ticket.assigned_to = assignee
                        ticket.save(update_fields=['assigned_to'])
                        TicketEvent.objects.create(ticket=ticket, actor=request.user, event_type='assigned', to_status=ticket.status, note=f'Assigned to {assignee.get_full_name() or assignee.username}.')
                notify_ticket_received(ticket)
                if ticket.assigned_to:
                    notify_assignment(ticket, ticket.assigned_to)
                messages.success(request, f'Ticket #{ticket.id} created.')
                return redirect('ticket_detail', pk=ticket.id)
            except ValueError as e:
                logger.warning('Ticket create validation failed: %s', e, exc_info=True)
                messages.error(request, f'Could not create ticket: {e}')
            except RuntimeError:
                logger.exception('Ticket create failed due to runtime error')
                messages.error(request, 'Could not create ticket right now.')

    try:
        staff_members = list(StaffMember.objects.filter(is_active=True).order_by('first_name'))
    except RuntimeError:
        staff_members = []

    return render(request, 'create_ticket.html', {
        'staff_members': staff_members,
        'channel_choices': Ticket.CHANNEL_CHOICES,
        'allowed_attachment_types': ', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS)),
        'max_attachment_mb': 10,
    })


@login_required
def live_dashboard(request):
    all_tickets = Ticket.objects.all()
    open_t = all_tickets.filter(status='open').count()
    in_progress_t = all_tickets.filter(status='in_progress').count()
    resolved_t = all_tickets.filter(status='resolved').count()
    total = all_tickets.count()
    closed = all_tickets.filter(status__in=['resolved','closed'])
    sla_ok = sum(1 for t in closed if t.resolved_at and t.resolved_at <= t.sla_deadline)
    sla_compliance = round((sla_ok/closed.count())*100) if closed.exists() else 100
    times = [t.resolution_time_seconds for t in all_tickets.filter(resolved_at__isnull=False) if t.resolution_time_seconds is not None]
    avg_resolution = round(sum(times)/len(times)) if times else 0
    total_assigned = all_tickets.exclude(assigned_to__isnull=True).count()
    productivity = round((resolved_t/total_assigned)*100) if total_assigned > 0 else 0
    sla_breached = sum(1 for t in all_tickets.filter(status__in=['open','in_progress']) if t.is_sla_breached)
    agents = User.objects.filter(is_staff=True).annotate(
        open_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['open','in_progress']))
    )
    return render(request, 'live_dashboard.html', {
        'open':open_t,'in_progress':in_progress_t,'resolved':resolved_t,
        'total':total,'sla_compliance':sla_compliance,'avg_resolution':avg_resolution,
        'productivity':productivity,'sla_breached':sla_breached,'agents':agents,
    })


@login_required
def staff_search_api(request):
    from directory.models import StaffMember
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




@login_required
def dashboard_snapshot_api(request):
    all_tickets = Ticket.objects.select_related('assigned_to').all()
    data = {
        'open': all_tickets.filter(status='open').count(),
        'in_progress': all_tickets.filter(status='in_progress').count(),
        'resolved': all_tickets.filter(status='resolved').count(),
        'total': all_tickets.count(),
        'unassigned': all_tickets.filter(assigned_to__isnull=True, status='open').count(),
        'my_open': all_tickets.filter(assigned_to=request.user).exclude(status__in=['resolved', 'closed']).count(),
    }
    return JsonResponse(data)


@login_required
def ticket_list_snapshot_api(request):
    tickets = Ticket.objects.select_related('assigned_to').all()
    q = request.GET.get('q','').strip()
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    category_filter = request.GET.get('category')
    assigned_filter = request.GET.get('mine')
    unassigned_filter = request.GET.get('unassigned')

    if q:
        tickets = tickets.filter(Q(title__icontains=q)|Q(description__icontains=q)|Q(user_email__icontains=q)|Q(requester_name__icontains=q))
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    if category_filter:
        tickets = tickets.filter(category=category_filter)
    if assigned_filter == '1':
        tickets = tickets.filter(assigned_to=request.user)
    if unassigned_filter == '1':
        tickets = tickets.filter(assigned_to__isnull=True)

    items = []
    for t in tickets.order_by('-created_at')[:50]:
        items.append({
            'id': t.id,
            'title': t.title,
            'status': t.get_status_display(),
            'priority': t.get_priority_display(),
            'requester': t.requester_name or t.user_email,
            'category': t.category_display,
            'assigned_to': (t.assigned_to.get_full_name() or t.assigned_to.username) if t.assigned_to else 'Unassigned',
            'created_at': t.created_at.isoformat(),
            'url': f'/tickets/{t.id}/',
        })
    return JsonResponse({'count': tickets.count(), 'items': items})


@login_required
def protected_media(request, path):
    """
    Serve media files from MEDIA_ROOT for authenticated users.
    Prevent path traversal and return the correct mime type.
    """
    requested = (Path(settings.MEDIA_ROOT) / path).resolve()
    media_root = Path(settings.MEDIA_ROOT).resolve()

    if media_root not in requested.parents and requested != media_root:
        raise Http404("Invalid media path")

    if not requested.exists() or not requested.is_file():
        raise Http404("File not found")

    content_type, _ = mimetypes.guess_type(str(requested))
    return FileResponse(open(requested, 'rb'), content_type=content_type or 'application/octet-stream')
