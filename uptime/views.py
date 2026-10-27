import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from projects.models import Project, ProjectMember
from projects.views import get_project, project_context

from . import checker, notify, stats
from .forms import MonitorForm
from .models import Monitor

STALE_AFTER = datetime.timedelta(minutes=5)  # overdue checks mean the worker is not running


def worker_stale(monitors):
    cutoff = timezone.now() - STALE_AFTER
    return any(m.enabled and m.next_check_at < cutoff for m in monitors)


def unmonitored_hosts(project):
    """Analytics domains of the project that have no monitor yet."""
    monitored = {m.label.split("/")[0] for m in project.monitors.all()}
    return [host for host in project.analytics_hosts() if host not in monitored]


def add_hosts(project, hosts):
    room = settings.FALCONDB_UPTIME_MAX_MONITORS - project.monitors.count()
    created = 0
    for host in hosts[:max(room, 0)]:
        _monitor, new = Monitor.objects.get_or_create(project=project, url=f"https://{host}/")
        created += new
    return created


def common_context():
    return {"email_configured": notify.configured(), "periods": stats.PERIODS}


@login_required
def overview(request):
    """Every monitor of the projects the user owns or that were shared with them."""
    projects = list(Project.accessible_by(request.user).select_related("owner").order_by("name"))
    editor_of = set(ProjectMember.objects.filter(user=request.user, role=ProjectMember.EDITOR)
                    .values_list("project_id", flat=True))
    editable = [p for p in projects if p.owner_id == request.user.pk or p.pk in editor_of]

    if request.method == "POST" and request.POST.get("action") == "add_domains":
        created = sum(add_hosts(p, unmonitored_hosts(p)) for p in editable)
        messages.success(request, _("%(count)s monitors added. The first check runs within a minute.") % {"count": created})
        return redirect("uptime")

    monitors = stats.annotate(list(Monitor.objects.filter(project__in=projects)
                                   .select_related("project__owner").order_by("project__name", "url")))
    suggestions = [(p, hosts) for p in editable if (hosts := unmonitored_hosts(p))]
    return render(request, "uptime/overview.html", {
        **common_context(),
        "monitors": monitors, "projects": projects, "suggestions": suggestions,
        "up": sum(m.enabled and m.status == Monitor.UP for m in monitors),
        "down": sum(m.enabled and m.status == Monitor.DOWN for m in monitors),
        "paused": sum(not m.enabled for m in monitors),
        "worker_stale": worker_stale(monitors),
    })


@login_required
def project_uptime(request, username, slug):
    project = get_project(request, username, slug)
    form = MonitorForm(project=project)
    if request.method == "POST":
        if request.POST.get("action") == "add_domains":
            created = add_hosts(project, unmonitored_hosts(project))
            messages.success(request, _("%(count)s monitors added. The first check runs within a minute.") % {"count": created})
            return redirect(project.url("uptime"))
        form = MonitorForm(request.POST, project=project)
        if form.is_valid():
            monitor = form.save()
            messages.success(request, _("Monitor added. The first check runs within a minute."))
            return redirect(monitor)

    monitors = stats.annotate(list(project.monitors.all()))
    for monitor in monitors:
        monitor.project = project
    return render(request, "uptime/project.html", project_context(
        request, project, "uptime", **common_context(), form=form, monitors=monitors,
        suggestions=unmonitored_hosts(project), worker_stale=worker_stale(monitors),
    ))


@login_required
def monitor_detail(request, username, slug, monitor_id):
    project = get_project(request, username, slug)
    monitor = get_object_or_404(Monitor, project=project, pk=monitor_id)
    monitor.project = project
    form = MonitorForm(instance=monitor, project=project)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "check":
            result = checker.check(monitor)
            if result.ok:
                messages.success(request, _("Up: HTTP %(code)s in %(ms)s ms.") % {"code": result.status_code, "ms": result.response_ms})
            else:
                messages.error(request, _("Down: %(error)s") % {"error": result.error})
            return redirect(monitor)
        if action == "delete":
            monitor.delete()
            messages.success(request, _("Monitor deleted."))
            return redirect(project.url("uptime"))
        if action == "update":
            old_url, was_enabled = monitor.url, monitor.enabled
            form = MonitorForm(request.POST, instance=monitor, project=project)
            if form.is_valid():
                monitor = form.save(commit=False)
                if monitor.url != old_url:
                    monitor.status, monitor.status_since, monitor.last_error = Monitor.UNKNOWN, None, ""
                    monitor.incidents.filter(ended_at__isnull=True).update(ended_at=timezone.now())
                if monitor.url != old_url or (monitor.enabled and not was_enabled):
                    monitor.next_check_at = timezone.now()
                elif "interval" in form.changed_data:
                    monitor.schedule_next(monitor.last_checked_at or timezone.now())
                monitor.save()
                messages.success(request, _("Monitor saved."))
                return redirect(monitor)

    days = stats.parse_period(request.GET.get("days"))
    return render(request, "uptime/monitor.html", project_context(
        request, project, "uptime", **common_context(), monitor=monitor, form=form,
        report=stats.report(monitor, days), recent=monitor.checks.all()[:20],
        worker_stale=worker_stale([monitor]),
    ))
