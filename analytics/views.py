import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from projects.models import Project
from projects.views import get_project, project_context

from . import stats, tracking
from .models import PageView

MAX_PAYLOAD = 4096


@cache_control(public=True, max_age=3600)
def script(request):
    """The tracking script websites embed (served through Django to get CORS headers)."""
    source = (settings.BASE_DIR / "static" / "js" / "a.js").read_text(encoding="utf-8")
    return HttpResponse(source, content_type="text/javascript; charset=utf-8")


@csrf_exempt
@require_POST
def collect(request, ref):
    """Receive a page view. Sent with sendBeacon as text/plain, so there is no CORS preflight."""
    project = Project.objects.filter(ref=ref, analytics_enabled=True).first()
    if project is None:
        return HttpResponse(status=404)
    try:
        payload = json.loads(request.body[:MAX_PAYLOAD] or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)
    if not isinstance(payload, dict):
        return HttpResponse(status=400)
    tracking.record(project, request, payload)
    return HttpResponse(status=202)


@login_required
def project_analytics(request, username, slug):
    project = get_project(request, username, slug)
    if request.method == "POST":
        project.analytics_enabled = bool(request.POST.get("analytics_enabled"))
        project.analytics_domains = ", ".join(
            d.strip().lower() for d in request.POST.get("analytics_domains", "").replace("\n", ",").split(",") if d.strip()
        )[:500]
        project.save(update_fields=["analytics_enabled", "analytics_domains", "updated_at"])
        messages.success(request, _("Analytics enabled.") if project.analytics_enabled else _("Analytics disabled."))
        return redirect(project.url("analytics"))

    days = stats.parse_period(request.GET.get("days"))
    report = stats.report(PageView.objects.filter(project=project), days)
    return render(request, "analytics/project.html", project_context(
        request, project, "analytics", report=report, periods=stats.PERIODS,
    ))


@login_required
def overview(request):
    """Analytics of the projects the user owns or that were shared with them (all, or those picked with ?p=<ref>)."""
    projects = list(Project.accessible_by(request.user).select_related("owner").order_by("name"))
    chosen = set(request.GET.getlist("p"))
    selected = [p for p in projects if p.ref in chosen] or projects
    days = stats.parse_period(request.GET.get("days"))
    report = stats.report(PageView.objects.filter(project__in=selected), days, by_project=True)
    return render(request, "analytics/overview.html", {
        # "chosen" is what the user ticked; nothing ticked means every project.
        "projects": projects, "chosen": {p.ref for p in selected} & chosen, "all_selected": not (chosen & {p.ref for p in projects}),
        "report": report, "periods": stats.PERIODS,
        "base_url": request.build_absolute_uri("/").rstrip("/"),
    })
