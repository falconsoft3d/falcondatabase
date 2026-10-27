"""Uptime percentages, daily status bars and response-time series (days are UTC)."""

import datetime

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from .models import Check, Incident

PERIODS = (1, 7, 30, 90)   # 1 = last 24 hours, by hour
DEFAULT_PERIOD = 1
BAR_DAYS = 30              # status bars in the monitor lists
DETAIL_BAR_DAYS = 90
GOOD = 100.0               # a day at 100% is "up"; from WARNING it is "degraded"; below, "down"
WARNING = 95.0


def parse_period(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PERIOD
    return days if days in PERIODS else DEFAULT_PERIOD


def since(days, now=None):
    return (now or timezone.now()) - datetime.timedelta(days=days)


def percent(ok, total):
    return round(100 * ok / total, 2) if total else None


def level(pct):
    if pct is None:
        return "none"
    if pct >= GOOD:
        return "up"
    return "degraded" if pct >= WARNING else "down"


def counts(checks):
    return checks.aggregate(total=Count("id"), ok=Count("id", filter=Q(ok=True)))


def uptime(checks):
    data = counts(checks)
    return percent(data["ok"], data["total"])


def daily_bars(monitor_ids, days=BAR_DAYS, now=None):
    """``{monitor_id: [{"date", "total", "failed", "pct", "level"}, …]}``, oldest day first."""
    now = now or timezone.now()
    first = now.date() - datetime.timedelta(days=days - 1)
    start = datetime.datetime.combine(first, datetime.time.min, tzinfo=datetime.UTC)
    rows = (Check.objects.filter(monitor_id__in=monitor_ids, created_at__gte=start)
            .annotate(day=TruncDate("created_at", tzinfo=datetime.UTC))
            .values("monitor_id", "day").annotate(total=Count("id"), ok=Count("id", filter=Q(ok=True))))
    found = {(row["monitor_id"], row["day"]): row for row in rows}
    bars = {}
    for monitor_id in monitor_ids:
        series = []
        for offset in range(days):
            day = first + datetime.timedelta(days=offset)
            row = found.get((monitor_id, day), {"total": 0, "ok": 0})
            pct = percent(row["ok"], row["total"])
            series.append({"date": day, "total": row["total"], "failed": row["total"] - row["ok"],
                           "pct": pct, "level": level(pct)})
        bars[monitor_id] = series
    return bars


def uptime_by_monitor(monitor_ids, days, now=None):
    rows = (Check.objects.filter(monitor_id__in=monitor_ids, created_at__gte=since(days, now))
            .values("monitor_id").annotate(total=Count("id"), ok=Count("id", filter=Q(ok=True))))
    return {row["monitor_id"]: percent(row["ok"], row["total"]) for row in rows}


def annotate(monitors, now=None):
    """Add ``uptime_24h``, ``uptime_30d`` and ``bars`` to each monitor of a list."""
    ids = [m.pk for m in monitors]
    day, month, bars = uptime_by_monitor(ids, 1, now), uptime_by_monitor(ids, 30, now), daily_bars(ids, now=now)
    for monitor in monitors:
        monitor.uptime_24h = day.get(monitor.pk)
        monitor.uptime_30d = month.get(monitor.pk)
        monitor.bars = bars[monitor.pk]
    return monitors


def response_series(monitor, days, now=None):
    """Average response time per hour (last 24 h) or per day, from the first point with data."""
    now = now or timezone.now()
    hourly = days == 1
    if hourly:
        first = now.replace(minute=0, second=0, microsecond=0) - datetime.timedelta(hours=23)
        step, trunc = datetime.timedelta(hours=1), TruncHour("created_at", tzinfo=datetime.UTC)
        points = 24
    else:
        first = datetime.datetime.combine(now.date() - datetime.timedelta(days=days - 1), datetime.time.min,
                                          tzinfo=datetime.UTC)
        step, trunc = datetime.timedelta(days=1), TruncDate("created_at", tzinfo=datetime.UTC)
        points = days
    rows = {
        row["slot"]: row["avg"]
        for row in monitor.checks.filter(created_at__gte=first, response_ms__isnull=False)
        .annotate(slot=trunc).values("slot").annotate(avg=Avg("response_ms"))
    }
    series = []
    for i in range(points):
        moment = first + step * i
        value = rows.get(moment if hourly else moment.date())
        if value is None and not series:
            continue  # nothing before the monitor started
        point = {"date": moment.date().isoformat(), "response_ms": round(value or 0)}
        if hourly:
            point["hour"] = moment.hour
        series.append(point)
    return series


def downtime(monitor, days, now=None):
    """Incidents that overlap the period and the total time down within it."""
    now = now or timezone.now()
    start = since(days, now)
    incidents = list(Incident.objects.filter(monitor=monitor).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=start)))
    total = sum(((i.ended_at or now) - max(i.started_at, start) for i in incidents), datetime.timedelta())
    return incidents, total


def report(monitor, days, now=None):
    now = now or timezone.now()
    checks = monitor.checks.filter(created_at__gte=since(days, now))
    data = counts(checks)
    incidents, down_for = downtime(monitor, days, now)
    return {
        "days": days,
        "uptime": percent(data["ok"], data["total"]),
        "checks": data["total"],
        "failed": data["total"] - data["ok"],
        "avg_ms": checks.filter(response_ms__isnull=False).aggregate(avg=Avg("response_ms"))["avg"],
        "incidents": incidents,
        "downtime": down_for,
        "series": response_series(monitor, days, now),
        "bars": daily_bars([monitor.pk], DETAIL_BAR_DAYS, now)[monitor.pk],
    }
