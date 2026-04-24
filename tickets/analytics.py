import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q

from .models import Ticket


def summarize_sla_breaches(tickets):
    breached = [ticket.id for ticket in tickets.filter(status__in=["open", "in_progress", "pending"]) if ticket.is_sla_breached]
    return breached, len(breached)


def calculate_sla_compliance(tickets):
    closed = tickets.filter(status__in=["resolved", "closed"])
    if not closed.exists():
        return 100
    sla_ok = sum(1 for ticket in closed if ticket.resolved_at and ticket.resolved_at <= ticket.sla_deadline)
    return round((sla_ok / closed.count()) * 100)


def calculate_avg_resolution_hours(tickets):
    resolved = tickets.filter(resolved_at__isnull=False)
    times = [ticket.resolution_time_hours for ticket in resolved if ticket.resolution_time_hours]
    return round(sum(times) / len(times), 1) if times else 0


def calculate_avg_first_response_minutes(tickets):
    values = [ticket.first_response_minutes for ticket in tickets if ticket.first_response_minutes is not None]
    return round(sum(values) / len(values), 1) if values else 0


def build_ticket_volume_chart(tickets, days=7):
    labels = []
    data = []
    today = date.today()
    for offset in range(days - 1, -1, -1):
        current_day = today - timedelta(days=offset)
        labels.append(current_day.strftime("%b %d"))
        data.append(tickets.filter(created_at__date=current_day).count())
    return labels, data


def calculate_category_resolution_hours(tickets):
    resolved = tickets.filter(resolved_at__isnull=False)
    metrics = {}
    for category, _ in Ticket.CATEGORY_CHOICES:
        category_tickets = resolved.filter(category=category)
        times = [ticket.resolution_time_hours for ticket in category_tickets if ticket.resolution_time_hours]
        if times:
            metrics[category] = round(sum(times) / len(times), 1)
    return metrics


def build_staff_workload():
    return list(
        User.objects.filter(is_staff=True)
        .annotate(open_count=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=["open", "in_progress"])))
        .order_by("-open_count")
    )


def calculate_agent_productivity(tickets, user):
    resolved_count = tickets.filter(assigned_to=user, status__in=["resolved", "closed"]).count()
    total_assigned = tickets.filter(assigned_to=user).count()
    productivity = round((resolved_count / total_assigned) * 100) if total_assigned > 0 else 0
    return {
        "resolved": resolved_count,
        "total_assigned": total_assigned,
        "productivity": productivity,
    }


def build_dashboard_metrics(tickets):
    sla_breached_ids, sla_breached_count = summarize_sla_breaches(tickets)
    chart_labels, chart_data = build_ticket_volume_chart(tickets)
    return {
        "total": tickets.count(),
        "open": tickets.filter(status="open").count(),
        "in_progress": tickets.filter(status="in_progress").count(),
        "resolved": tickets.filter(status="resolved").count(),
        "unassigned": tickets.filter(assigned_to__isnull=True, status="open").count(),
        "sla_breached_ids": sla_breached_ids,
        "sla_breached": sla_breached_count,
        "sla_compliance": calculate_sla_compliance(tickets),
        "avg_resolution": calculate_avg_resolution_hours(tickets),
        "avg_first_response": calculate_avg_first_response_minutes(tickets),
        "category_counts": tickets.values("category").annotate(count=Count("id")).order_by("-count"),
        "cat_resolution": calculate_category_resolution_hours(tickets),
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
    }
