from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import messages
from django.http import JsonResponse
from .models import Ticket, TicketComment, Profile
from .classifier import classify
from .assignment import auto_assign
from .notifications import notify_assignment, notify_status_change
from knowledge.models import Article
import json
from datetime import date, timedelta


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials.')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user
    role = getattr(getattr(user, 'profile', None), 'role', 'associate')
    is_manager = role == 'manager'
    is_consultant = role == 'consultant'

    all_tickets = Ticket.objects.all()
    my_tickets = all_tickets.filter(assigned_to=user).exclude(status__in=['resolved', 'closed'])
    unassigned = all_tickets.filter(assigned_to__isnull=True, status='open')

    total = all_tickets.count()
    open_count = all_tickets.filter(status='open').count()
    in_progress = all_tickets.filter(status='in_progress').count()
    resolved_count = all_tickets.filter(status='resolved').count()
    sla_breached_ids = [t.id for t in all_tickets.filter(status__in=['open', 'in_progress']) if t.is_sla_breached]
    unassigned_count = unassigned.count()

    # SLA compliance %
    closed_tickets = all_tickets.filter(status__in=['resolved', 'closed'])
    if closed_tickets.exists():
        on_time = sum(1 for t in closed_tickets if t.resolved_at and t.resolved_at <= t.sla_deadline)
        sla_compliance = round((on_time / closed_tickets.count()) * 100)
    else:
        sla_compliance = 100

    # Avg resolution time
    resolved_tickets = all_tickets.filter(resolved_at__isnull=False)
    avg_resolution = None
    if resolved_tickets.exists():
        times = [t.resolution_time_hours for t in resolved_tickets if t.resolution_time_hours]
        avg_resolution = round(sum(times) / len(times), 1) if times else None

    # Chart: tickets per day last 7 days
    today = date.today()
    chart_labels, chart_data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%b %d'))
        chart_data.append(all_tickets.filter(created_at__date=day).count())

    # Category breakdown
    category_counts = all_tickets.values('category').annotate(count=Count('id')).order_by('-count')

    # Avg resolution by category
    cat_resolution = {}
    for cat, _ in Ticket.CATEGORY_CHOICES:
        cat_tickets = resolved_tickets.filter(category=cat)
        if cat_tickets.exists():
            times = [t.resolution_time_hours for t in cat_tickets if t.resolution_time_hours]
            if times:
                cat_resolution[cat] = round(sum(times) / len(times), 1)

    # Staff workload (manager only)
    staff_workload = []
    if is_manager:
        staff = User.objects.filter(is_staff=True).annotate(
            open_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['open', 'in_progress']))
        ).order_by('-open_count')
        staff_workload = list(staff)

    # Personal stats
    my_resolved = all_tickets.filter(assigned_to=user, status='resolved').count()
    my_total = all_tickets.filter(assigned_to=user).count()
    my_productivity = round((my_resolved / my_total) * 100) if my_total > 0 else 0

    context = {
        'my_tickets': my_tickets,
        'all_tickets': all_tickets[:20],
        'unassigned_tickets': unassigned[:10],
        'is_manager': is_manager,
        'is_consultant': is_consultant,
        'role': role,
        'stats': {
            'total': total,
            'open': open_count,
            'in_progress': in_progress,
            'resolved': resolved_count,
            'sla_breached': len(sla_breached_ids),
            'unassigned': unassigned_count,
            'sla_compliance': sla_compliance,
            'avg_resolution': avg_resolution or 0,
        },
        'sla_breached_ids': sla_breached_ids,
        'staff_workload': staff_workload,
        'category_counts': category_counts,
        'avg_resolution': avg_resolution,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'cat_resolution': cat_resolution,
        'my_productivity': my_productivity,
        'my_resolved': my_resolved,
        'my_total': my_total,
    }
    return render(request, 'dashboard.html', context)


@login_required
def ticket_list(request):
    tickets = Ticket.objects.all()
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    category_filter = request.GET.get('category')
    assigned_filter = request.GET.get('mine')
    unassigned_filter = request.GET.get('unassigned')

    if q:
        tickets = tickets.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(user_email__icontains=q))
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

    return render(request, 'ticket_list.html', {
        'tickets': tickets,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'filters': {'q': q, 'status': status_filter, 'priority': priority_filter,
                    'category': category_filter, 'mine': assigned_filter, 'unassigned': unassigned_filter},
        'result_count': tickets.count(),
    })


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    comments = ticket.comments.all()
    related_articles = Article.objects.filter(category=ticket.category)[:3]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'comment':
            body = request.POST.get('body', '').strip()
            if body:
                TicketComment.objects.create(ticket=ticket, author=request.user, body=body)
        elif action == 'pickup':
            if not ticket.assigned_to:
                ticket.assigned_to = request.user
                ticket.status = 'in_progress'
                ticket.save()
                notify_assignment(ticket, request.user)
                messages.success(request, f'You picked up ticket #{ticket.id}.')
        elif action == 'update_status':
            new_status = request.POST.get('status')
            old_status = ticket.status
            ticket.status = new_status
            if new_status == 'resolved' and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
            ticket.save()
            if new_status != old_status:
                notify_status_change(ticket, request.user)
        elif action == 'reassign':
            uid = request.POST.get('user_id')
            if uid:
                old_assignee = ticket.assigned_to
                ticket.assigned_to_id = int(uid)
                ticket.save()
                new_assignee = ticket.assigned_to
                if new_assignee and (not old_assignee or old_assignee.id != new_assignee.id):
                    notify_assignment(ticket, new_assignee)
        elif action == 'update_category':
            ticket.category = request.POST.get('category', ticket.category)
            ticket.save()
            messages.success(request, 'Category updated.')
        return redirect('ticket_detail', pk=pk)

    staff_users = User.objects.filter(is_staff=True)
    return render(request, 'ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'related_articles': related_articles,
        'staff_users': staff_users,
        'status_choices': Ticket.STATUS_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
    })


@login_required
def create_ticket(request):
    from directory.models import StaffMember
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        user_email = request.POST.get('user_email', '').strip()
        channel = request.POST.get('channel', 'manual')
        staff_id = request.POST.get('staff_member')

        if title and description and user_email:
            result = classify(title, description)
            ticket = Ticket.objects.create(
                title=title, description=description, user_email=user_email,
                category=result['category'], priority=result['priority'],
                required_level=result['level'], sla_hours=result['sla_hours'],
                channel=channel,
            )
            if staff_id:
                try:
                    sm = StaffMember.objects.get(pk=staff_id)
                    ticket.requester_name = sm.full_name
                    ticket.save()
                except StaffMember.DoesNotExist:
                    pass
            assignee = auto_assign(ticket)
            if assignee:
                ticket.assigned_to = assignee
                ticket.save()
                notify_assignment(ticket, assignee)
            messages.success(request, f'Ticket #{ticket.id} created and assigned.')
            return redirect('ticket_detail', pk=ticket.id)

    from directory.models import StaffMember
    staff_members = StaffMember.objects.filter(is_active=True).order_by('first_name')
    return render(request, 'create_ticket.html', {'staff_members': staff_members})


@login_required
def live_dashboard(request):
    """Wall display — no login check needed for public display, auto-refreshes."""
    all_tickets = Ticket.objects.all()
    open_t = all_tickets.filter(status='open').count()
    in_progress_t = all_tickets.filter(status='in_progress').count()
    resolved_t = all_tickets.filter(status='resolved').count()
    total = all_tickets.count()

    closed = all_tickets.filter(status__in=['resolved', 'closed'])
    sla_ok = sum(1 for t in closed if t.resolved_at and t.resolved_at <= t.sla_deadline)
    sla_compliance = round((sla_ok / closed.count()) * 100) if closed.exists() else 100

    resolved_with_time = all_tickets.filter(resolved_at__isnull=False)
    times = [t.resolution_time_hours for t in resolved_with_time if t.resolution_time_hours]
    avg_resolution = round(sum(times) / len(times), 1) if times else 0

    total_assigned = all_tickets.exclude(assigned_to__isnull=True).count()
    productivity = round((resolved_t / total_assigned) * 100) if total_assigned > 0 else 0

    sla_breached = sum(1 for t in all_tickets.filter(status__in=['open', 'in_progress']) if t.is_sla_breached)

    agents = User.objects.filter(is_staff=True).annotate(
        open_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['open', 'in_progress']))
    )

    return render(request, 'live_dashboard.html', {
        'open': open_t, 'in_progress': in_progress_t, 'resolved': resolved_t,
        'total': total, 'sla_compliance': sla_compliance, 'avg_resolution': avg_resolution,
        'productivity': productivity, 'sla_breached': sla_breached, 'agents': agents,
    })


@login_required
def staff_search_api(request):
    """JSON endpoint for staff directory typeahead."""
    from directory.models import StaffMember
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    members = StaffMember.objects.filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q), is_active=True
    )[:10]
    return JsonResponse({'results': [
        {'id': m.id, 'name': m.full_name, 'email': m.email,
         'department': m.department.name if m.department else ''}
        for m in members
    ]})
