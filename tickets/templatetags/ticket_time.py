from django import template

register = template.Library()

def _humanize_seconds(total_seconds):
    try:
        total_seconds = int(round(float(total_seconds)))
    except (TypeError, ValueError):
        return '—'
    if total_seconds < 0:
        total_seconds = 0
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"

@register.filter
def duration_from_seconds(value):
    return _humanize_seconds(value)

@register.filter
def duration_from_minutes(value):
    try:
        seconds = float(value) * 60
    except (TypeError, ValueError):
        return '—'
    return _humanize_seconds(seconds)

@register.filter
def duration_from_hours(value):
    try:
        seconds = float(value) * 3600
    except (TypeError, ValueError):
        return '—'
    return _humanize_seconds(seconds)
