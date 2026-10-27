from django import template

from uptime.notify import human_duration

register = template.Library()


@register.filter
def duration(delta):
    """timedelta -> "12 min", "3 h 5 min", "4 days" ("—" when empty)."""
    return human_duration(delta) if delta else "—"
