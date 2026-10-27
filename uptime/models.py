import datetime
from urllib.parse import urlsplit

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from projects.models import Project


def default_interval():
    return settings.FALCONDB_UPTIME_DEFAULT_INTERVAL


class Monitor(models.Model):
    """A URL of one of the project's websites, requested every ``interval`` minutes by the uptime worker."""

    INTERVAL_CHOICES = [
        (1, _("Every minute")),
        (5, _("Every 5 minutes")),
        (10, _("Every 10 minutes")),
        (15, _("Every 15 minutes")),
        (30, _("Every 30 minutes")),
        (60, _("Every hour")),
    ]
    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="monitors")
    url = models.URLField(_("URL"), max_length=500)
    interval = models.PositiveSmallIntegerField(_("check"), choices=INTERVAL_CHOICES,
                                                default=default_interval)
    enabled = models.BooleanField(_("enabled"), default=True)
    notify = models.BooleanField(_("email me when it goes down or comes back"), default=True)
    # Optional URL that receives a JSON POST on every incident (Slack, Discord, n8n…).
    webhook_url = models.URLField(_("webhook"), max_length=500, blank=True)

    status = models.CharField(max_length=10, default=UNKNOWN)
    status_since = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_response_ms = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    next_check_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["url"]
        constraints = [models.UniqueConstraint(fields=["project", "url"], name="unique_monitor_url_per_project")]

    def __str__(self):
        return self.url

    @property
    def label(self):
        """The URL without the scheme and the trailing slash: example.com/shop."""
        parts = urlsplit(self.url)
        return (parts.netloc + parts.path).rstrip("/") + (f"?{parts.query}" if parts.query else "")

    def get_absolute_url(self):
        return reverse("projects:uptime_monitor", args=[self.project.owner.username, self.project.slug, self.pk])

    def schedule_next(self, now=None):
        self.next_check_at = (now or timezone.now()) + datetime.timedelta(minutes=self.interval)


class Check(models.Model):
    """One request to a monitor's URL."""

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="checks")
    created_at = models.DateTimeField(default=timezone.now)
    ok = models.BooleanField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["monitor", "created_at"])]

    def __str__(self):
        return f"{self.monitor} {'up' if self.ok else 'down'} {self.created_at:%Y-%m-%d %H:%M}"


class Incident(models.Model):
    """A period during which a monitor was down. ``ended_at`` is empty while it lasts."""

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="incidents")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.monitor} {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration(self):
        return (self.ended_at or timezone.now()) - self.started_at
