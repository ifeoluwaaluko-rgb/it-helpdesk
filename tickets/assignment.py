from django.contrib.auth.models import User
from django.db.models import Count, Q


def auto_assign(ticket):
    level = ticket.required_level
    eligible = User.objects.filter(
        profile__role=level,
        is_active=True
    ).annotate(
        open_count=Count(
            'assigned_tickets',
            filter=Q(assigned_tickets__status__in=['open', 'in_progress'])
        )
    ).order_by('open_count')

    if eligible.exists():
        return eligible.first()
    return None
