"""Aggregations for the analytics dashboards (days are UTC)."""

import datetime

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

PERIODS = (1, 7, 14, 30, 90)   # 1 = today, shown by hour
DEFAULT_PERIOD = 1
BREAKDOWN_LIMIT = 10

METRICS = {
    "visitors": lambda: Count("visitor", distinct=True),
    "sessions": lambda: Count("session", distinct=True),
    "pageviews": lambda: Count("id"),
}


def parse_period(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PERIOD
    return days if days in PERIODS else DEFAULT_PERIOD


def window(days, now=None):
    """``(start, end, previous_start)`` covering the last ``days`` days, today included."""
    now = now or timezone.now()
    first_day = now.date() - datetime.timedelta(days=days - 1)
    start = datetime.datetime.combine(first_day, datetime.time.min, tzinfo=datetime.UTC)
    return start, now, start - datetime.timedelta(days=days)


def totals(queryset):
    data = queryset.aggregate(**{name: metric() for name, metric in METRICS.items()})
    sessions = data["sessions"]
    bounces = queryset.values("session").annotate(views=Count("id")).filter(views=1).count()
    data["bounce_rate"] = round(100 * bounces / sessions) if sessions else None
    data["views_per_session"] = round(data["pageviews"] / sessions, 1) if sessions else None
    return data


def change(current, previous):
    if current is None or not previous:
        return None
    return round(100 * (current - previous) / previous)


def hourly(queryset, start, end):
    """Today's points, one per hour up to the current one."""
    rows = {
        row["hour"]: row
        for row in queryset.annotate(hour=TruncHour("created_at", tzinfo=datetime.UTC))
        .values("hour").annotate(**{name: metric() for name, metric in METRICS.items()})
    }
    series = []
    for hour in range(end.hour + 1):
        moment = start + datetime.timedelta(hours=hour)
        row = rows.get(moment, {})
        series.append({"date": moment.date().isoformat(), "hour": hour, **{name: row.get(name, 0) for name in METRICS}})
    return series


def timeseries(queryset, start, days):
    rows = {
        row["day"]: row
        for row in queryset.annotate(day=TruncDate("created_at", tzinfo=datetime.UTC))
        .values("day").annotate(**{name: metric() for name, metric in METRICS.items()})
    }
    series = []
    for offset in range(days):
        day = start.date() + datetime.timedelta(days=offset)
        row = rows.get(day, {})
        series.append({"date": day.isoformat(), **{name: row.get(name, 0) for name in METRICS}})
    return series


def breakdown(queryset, fields, metric):
    """Top values of ``fields`` ranked by ``metric``, with bar widths relative to the first row."""
    fields = [fields] if isinstance(fields, str) else list(fields)
    rows = list(queryset.values(*fields).annotate(value=METRICS[metric]()).order_by("-value", *fields)[:BREAKDOWN_LIMIT])
    total = queryset.aggregate(total=METRICS[metric]())["total"] or 0
    top = rows[0]["value"] if rows else 0
    for row in rows:
        row["share"] = round(100 * row["value"] / total) if total else 0
        row["width"] = round(100 * row["value"] / top) if top else 0
    return rows


def report(queryset, days, by_project=False):
    start, end, previous_start = window(days)
    current = queryset.filter(created_at__gte=start, created_at__lte=end)
    previous = queryset.filter(created_at__gte=previous_start, created_at__lt=start)

    now_totals, before = totals(current), totals(previous)
    kpis = [
        {"key": key, "value": now_totals[key], "change": change(now_totals[key], before[key]),
         "higher_is_better": key != "bounce_rate"}
        for key in ("visitors", "sessions", "pageviews", "views_per_session", "bounce_rate")
    ]
    data = {
        "days": days,
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "kpis": kpis,
        "totals": now_totals,
        "series": hourly(current, start, end) if days == 1 else timeseries(current, start, days),
        "countries": breakdown(current, "country", "visitors"),
        "mediums": breakdown(current, "medium", "sessions"),
        "sources": breakdown(current, "source", "sessions"),
        "pages": breakdown(current, ["hostname", "path"], "pageviews"),
        "devices": breakdown(current, "device", "visitors"),
        "browsers": breakdown(current, "browser", "visitors"),
        "systems": breakdown(current, "os", "visitors"),
    }
    if by_project:
        data["projects"] = breakdown(current, ["project__name", "project__slug"], "pageviews")
    return data
