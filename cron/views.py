import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from projects.views import get_project, project_context

from . import runner
from .forms import CronJobForm
from .models import CronJob

STALE_AFTER = datetime.timedelta(minutes=5)  # overdue jobs mean the worker is not running


def worker_stale(jobs):
    cutoff = timezone.now() - STALE_AFTER
    return any(job.enabled and job.next_run_at < cutoff for job in jobs)


@login_required
def project_cron(request, username, slug):
    project = get_project(request, username, slug)
    form = CronJobForm(project=project)
    if request.method == "POST":
        form = CronJobForm(request.POST, project=project)
        if form.is_valid():
            job = form.save()
            messages.success(request, _("Cron job added. The first call runs within a minute."))
            return redirect(job)

    jobs = list(project.cron_jobs.all())
    return render(request, "cron/project.html", project_context(
        request, project, "cron", form=form, jobs=jobs, worker_stale=worker_stale(jobs),
    ))


@login_required
def job_detail(request, username, slug, job_id):
    project = get_project(request, username, slug)
    job = get_object_or_404(CronJob, project=project, pk=job_id)
    job.project = project
    form = CronJobForm(instance=job, project=project)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "run":
            result = runner.run(job)
            if result.ok:
                messages.success(request, _("Done: HTTP %(code)s in %(ms)s ms.") % {"code": result.status_code, "ms": result.response_ms})
            else:
                messages.error(request, _("Failed: %(error)s") % {"error": result.error})
            return redirect(job)
        if action == "delete":
            job.delete()
            messages.success(request, _("Cron job deleted."))
            return redirect(project.url("cron"))
        if action == "update":
            was_enabled = job.enabled
            form = CronJobForm(request.POST, instance=job, project=project)
            if form.is_valid():
                job = form.save(commit=False)
                if job.enabled and not was_enabled:
                    job.next_run_at = timezone.now()
                elif "interval" in form.changed_data:
                    job.schedule_next(job.last_run_at or timezone.now())
                job.save()
                messages.success(request, _("Cron job saved."))
                return redirect(job)
            job.refresh_from_db()  # the page shows the saved job, not the rejected changes

    return render(request, "cron/job.html", project_context(
        request, project, "cron", job=job, form=form, runs=job.runs.all()[:30], worker_stale=worker_stale([job]),
    ))
