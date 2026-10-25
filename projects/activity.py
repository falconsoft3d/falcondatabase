"""Project activity: what changed, by whom, and the yearly contribution graph built from it."""

import datetime

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import ActivityEvent

LEVELS = 4  # colored levels besides "no activity"


def record(project, kind, user=None, actor="", target="", count=1):
    """Store one activity event. ``user`` is a dashboard account; ``actor`` names anyone else."""
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return ActivityEvent.objects.create(project=project, kind=kind, user=user, actor=actor[:255],
                                        target=str(target)[:255], count=max(1, int(count)))


def contributions(events, today=None):
    """GitHub-style calendar of the last year: weeks (columns) of 7 days, Sunday first.

    Each day counts the events of that day (an event inserting 50 rows counts once).
    """
    today = today or timezone.now().date()
    first_day = today - datetime.timedelta(days=364)
    start = first_day - datetime.timedelta(days=(first_day.weekday() + 1) % 7)  # back to Sunday
    counts = {
        row["day"]: row["n"]
        for row in events.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at", tzinfo=datetime.UTC)).values("day")
        .annotate(n=Count("id")).values("day", "n")
    }
    busiest = max(counts.values(), default=0)

    weeks, months, day = [], [], start
    while day <= today:
        week = []
        for _weekday in range(7):
            count = counts.get(day, 0) if first_day <= day <= today else None  # None: outside the year
            level = 0 if not count else min(LEVELS, 1 + (count - 1) * LEVELS // max(busiest, 1))
            week.append({"date": day, "count": count, "level": level})
            day += datetime.timedelta(days=1)
        month_start = next((d["date"] for d in week if d["date"].day == 1 and d["count"] is not None), None)
        if month_start:
            months.append({"index": len(weeks), "date": month_start})
        weeks.append(week)
    return {
        "weeks": weeks,
        "months": months,
        "total": sum(counts.get(first_day + datetime.timedelta(days=i), 0) for i in range(365)),
        "busiest": busiest,
    }
