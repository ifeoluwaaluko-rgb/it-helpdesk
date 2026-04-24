from django import template

register = template.Library()

@register.filter
def compact_duration_seconds(value):
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        return '—'
    if seconds < 60:
        return f"{round(seconds)}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{round(minutes)}m"
    hours = minutes / 60
    if hours < 24:
        return f"{round(hours)}h"
    return f"{round(hours / 24)}d"

@register.filter
def compact_minutes(value):
    try:
        return compact_duration_seconds(float(value or 0) * 60)
    except (TypeError, ValueError):
        return '—'

@register.filter
def compact_hours(value):
    try:
        return compact_duration_seconds(float(value or 0) * 3600)
    except (TypeError, ValueError):
        return '—'
