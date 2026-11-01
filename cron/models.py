import datetime
from urllib.parse import urlsplit

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from projects.models import Project


class CronJob(models.Model):
    """A URL of one of the project's apps, called every ``interval`` minutes by the cron worker."""

    INTERVAL_CHOICES = [
        (1, _("Every minute")),
        (5, _("Every 5 minutes")),
        (10, _("Every 10 minutes")),
        (15, _("Every 15 minutes")),
        (30, _("Every 30 minutes")),
        (60, _("Every hour")),
        (1440, _("Every day")),
    ]
    GET = "GET"
    POST = "POST"
    METHOD_CHOICES = [(GET, "GET"), (POST, "POST")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="cron_jobs")
    name = models.CharField(_("name"), max_length=100)
    url = models.URLField(_("URL"), max_length=500)
    method = models.CharField(_("method"), max_length=4, choices=METHOD_CHOICES, default=GET)
    interval = models.PositiveIntegerField(_("run"), choices=INTERVAL_CHOICES, default=1)
    # Optional header sent with every call, usually to prove the call comes from here.
    header_name = models.CharField(_("header"), max_length=100, blank=True)
    header_value = models.CharField(max_length=1000, blank=True)
    enabled = models.BooleanField(_("enabled"), default=True)

    last_run_at = models.DateTimeField(null=True, blank=True)
    last_ok = models.BooleanField(null=True, blank=True)
    last_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_response_ms = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    next_run_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def host(self):
        return urlsplit(self.url).netloc

    def get_absolute_url(self):
        return reverse("projects:cron_job", args=[self.project.owner.username, self.project.slug, self.pk])

    def schedule_next(self, now=None):
        self.next_run_at = (now or timezone.now()) + datetime.timedelta(minutes=self.interval)


class CronRun(models.Model):
    """One call to a job's URL."""

    job = models.ForeignKey(CronJob, on_delete=models.CASCADE, related_name="runs")
    created_at = models.DateTimeField(default=timezone.now)
    ok = models.BooleanField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["job", "created_at"])]

    def __str__(self):
        return f"{self.job} {'ok' if self.ok else 'failed'} {self.created_at:%Y-%m-%d %H:%M}"
