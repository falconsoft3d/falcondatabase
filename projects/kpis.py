"""The ten headline numbers of the dashboard, for one account (last 30 days where it applies)."""

import datetime

from django.utils import timezone

from analytics import stats
from analytics.models import PageView

from . import schema
from .models import ProjectTable, ProjectUser

PERIOD_DAYS = 30


def kpi(key, value, kind="number"):
    return {"key": key, "value": value, "kind": kind, "compare": False}


def compared(key, value, before, higher_is_better=True, kind="number"):
    """A KPI shown with its change against the previous period."""
    return {**kpi(key, value, kind), "compare": True, "change": stats.change(value, before),
            "higher_is_better": higher_is_better}


def account_kpis(user):
    projects = list(user.projects.all())
    tables = list(ProjectTable.objects.filter(project__owner=user).select_related("project"))
    rows = sum(schema.count_rows(table.project.schema, table.name) for table in tables)
    storage = schema.storage_bytes([project.schema for project in projects])

    now = timezone.now()
    period = datetime.timedelta(days=PERIOD_DAYS)
    app_users = ProjectUser.objects.filter(project__owner=user)
    new_users = app_users.filter(created_at__gte=now - period).count()
    new_before = app_users.filter(created_at__gte=now - 2 * period, created_at__lt=now - period).count()
    active_users = app_users.filter(last_login__gte=now - period).count()

    start, _end, previous_start = stats.window(PERIOD_DAYS, now)
    views = PageView.objects.filter(project__owner=user)
    current = stats.totals(views.filter(created_at__gte=start))
    previous = stats.totals(views.filter(created_at__gte=previous_start, created_at__lt=start))

    return [
        kpi("projects", len(projects)),
        kpi("tables", len(tables)),
        kpi("rows", rows),
        kpi("storage", storage, kind="bytes"),
        kpi("app_users", app_users.count()),
        compared("new_users", new_users, new_before),
        kpi("active_users", active_users),
        compared("visitors", current["visitors"], previous["visitors"]),
        compared("pageviews", current["pageviews"], previous["pageviews"]),
        compared("bounce_rate", current["bounce_rate"], previous["bounce_rate"], higher_is_better=False, kind="percent"),
    ]
