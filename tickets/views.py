from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import messages
from django.http import JsonResponse, Http404
from .models import Ticket, TicketComment, TicketEditHistory, Profile
from .classifier import classify, CATEGORY_TREE
from .assignment import auto_assign
from .notifications import notify_assignment, notify_status_change
from knowledge.models import Article
import json
from datetime import date, timedelta


def get_role(user):
    try: return user.profile.role
    except: return 'associate'


def can_assign(user):
    return get_role(user) in ('manager', 'consultant', 'senior')


def can_delete_edit(user):
    return get_role(user) in ('manager', 'consultant', 'senior')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/'
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

    total = all_tickets.count()
    open_count = all_tickets.filter(status='open').count()
    in_progress = all_tickets.filter(status='in_progress').count()
    resolved_count = all_tickets.filter(status='resolved').count()
    sla_breached_ids = [t.id for t in all_tickets.filter(status__in=['open','in_progress','pending']) if t.is_sla_breached]

    closed = all_tickets.filter(status__in=['resolved','closed'])
    sla_ok = sum(1 for t in closed if t.resolved_at and t.resolved_at <= t.sla_deadline)
    sla_compliance = round((sla_ok / closed.count()) * 100) if closed.exists() else 100

    resolved_tickets = all_tickets.filter(resolved_at__isnull=False)
    times = [t.resolution_time_hours for t in resolved_tickets if t.resolution_time_hours]
    avg_resolution = round(sum(times)/len(times), 1) if times else 0

    today = date.today()
    chart_labels, chart_data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%b %d'))
        chart_data.append(all_tickets.filter(created_at__date=day).count())

    category_counts = all_tickets.values('category').annotate(count=Count('id')).order_by('-count')

    cat_resolution = {}
    for cat, _ in Ticket.CATEGORY_CHOICES:
        cat_tickets = resolved_tickets.filter(category=cat)
        if cat_tickets.exists():
            t2 = [t.resolution_time_hours for t in cat_tickets if t.resolution_time_hours]
            if t2: cat_resolution[cat] = round(sum(t2)/len(t2), 1)

    staff_workload = []
    if is_manager:
        staff = User.objects.filter(is_staff=True).annotate(
            open_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['open','in_progress']))
        ).order_by('-open_count')
        staff_workload = list(staff)

    my_resolved = all_tickets.filter(assigned_to=user, status__in=['resolved','closed']).count()
    my_total_assigned = all_tickets.filter(assigned_to=user).count()
    my_productivity = round((my_resolved / my_total_assigned) * 100) if my_total_assigned > 0 else 0

    recent = all_tickets[:15] if is_manager else my_tickets[:15]

    kpis = [
        (open_count,            'Open',        'text-[#1f73b7]', ''),
        (in_progress,           'In Progress', 'text-[#f79a3e]', ''),
        (resolved_count,        'Resolved',    'text-green-600', ''),
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
            'total': total, 'open': open_count, 'in_progress': in_progress,
            'resolved': resolved_count, 'sla_breached': len(sla_breached_ids),
            'unassigned': unassigned.count(), 'sla_compliance': sla_compliance,
            'avg_resolution': avg_resolution,
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
    related_articles = Article.objects.filter(category=ticket.category)[:3]
    role = get_role(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'comment':
            body = request.POST.get('body','').strip()
            if body:
                TicketComment.objects.create(ticket=ticket, author=request.user, body=body)

        elif action == 'pickup' and not ticket.assigned_to:
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

        elif action == 'reassign' and can_assign(request.user):
            uid = request.POST.get('user_id')
            if uid:
                old = ticket.assigned_to
                ticket.assigned_to_id = int(uid)
                ticket.save()
                if ticket.assigned_to and (not old or old.id != ticket.assigned_to.id):
                    notify_assignment(ticket, ticket.assigned_to)

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
            messages.success(request, 'Category updated.')

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
        'can_edit': True,  # all staff can edit
        'can_delete': can_delete_edit(request.user),
        'role': role,
    })


@login_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    role = get_role(request.user)

    if request.method == 'POST':
        edit_note = request.POST.get('edit_note','').strip()
        # Save snapshot BEFORE applying changes
        TicketEditHistory.objects.create(
            ticket=ticket, edited_by=request.user,
            title=ticket.title, description=ticket.description,
            category=ticket.category, subcategory=ticket.subcategory,
            item=ticket.item, priority=ticket.priority, status=ticket.status,
            edit_note=edit_note or 'Edited',
        )
        ticket.title = request.POST.get('title', ticket.title).strip()
        ticket.description = request.POST.get('description', ticket.description).strip()
        ticket.category = request.POST.get('category', ticket.category)
        ticket.subcategory = request.POST.get('subcategory', '')
        ticket.item = request.POST.get('item', '')
        ticket.priority = request.POST.get('priority', ticket.priority)
        if can_delete_edit(request.user):
            ticket.status = request.POST.get('status', ticket.status)
        ticket.tags = request.POST.get('tags', ticket.tags)
        ticket.save()
        messages.success(request, f'Ticket #{ticket.id} updated.')
        return redirect('ticket_detail', pk=pk)

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
        title = request.POST.get('title','').strip()
        description = request.POST.get('description','').strip()
        user_email = request.POST.get('user_email','').strip()
        channel = request.POST.get('channel','manual')
        staff_id = request.POST.get('staff_member')

        if not user_email:
            messages.error(request, 'Requester email is required.')
            return redirect('create_ticket')

        if title and description and user_email:
            result = classify(title, description)
            ticket = Ticket.objects.create(
                title=title, description=description, user_email=user_email,
                category=result['category'], subcategory=result.get('subcategory',''),
                item=result.get('item',''), priority=result['priority'],
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
            messages.success(request, f'Ticket #{ticket.id} created.')
            return redirect('ticket_detail', pk=ticket.id)
        else:
            messages.error(request, 'Please fill in all required fields.')

    staff_members = []
    try:
        from directory.models import StaffMember
        staff_members = StaffMember.objects.filter(is_active=True).order_by('first_name')
    except: pass

    return render(request, 'create_ticket.html', {
        'staff_members': staff_members,
        'channel_choices': Ticket.CHANNEL_CHOICES,
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
    times = [t.resolution_time_hours for t in all_tickets.filter(resolved_at__isnull=False) if t.resolution_time_hours]
    avg_resolution = round(sum(times)/len(times),1) if times else 0
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
