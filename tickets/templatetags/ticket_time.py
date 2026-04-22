from datetime import timedelta
from django import template

register = template.Library()

def _to_seconds(value):
    if value is None or value == '':
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

@register.filter
def human_duration(value):
    seconds = _to_seconds(value)
    if seconds is None:
        return "—"
    seconds = abs(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"

@register.filter
def human_duration_precise(value):
    seconds = _to_seconds(value)
    if seconds is None:
        return "—"
    seconds = abs(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        secs = seconds % 60
        return f"{minutes}m" if secs == 0 else f"{minutes}m {secs}s"
    hours = minutes // 60
    if hours < 24:
        mins = minutes % 60
        return f"{hours}h" if mins == 0 else f"{hours}h {mins}m"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d" if rem_hours == 0 else f"{days}d {rem_hours}h"
