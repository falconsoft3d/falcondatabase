from django.db import models
from django.utils import timezone

from projects.models import Project


class PageView(models.Model):
    """One page load on a website that embeds the project's tracking script.

    No IP address or cookie is stored: ``visitor`` is a hash that changes every
    day, and ``session`` groups the visitor's page views within 30 minutes.
    Source, medium and campaign belong to the session and are copied from its
    first page view.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="pageviews")
    created_at = models.DateTimeField(default=timezone.now)
    visitor = models.CharField(max_length=32)
    session = models.CharField(max_length=32)
    hostname = models.CharField(max_length=255)
    path = models.CharField(max_length=512)
    referrer = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=100)
    medium = models.CharField(max_length=50)
    campaign = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, blank=True)
    device = models.CharField(max_length=10)
    browser = models.CharField(max_length=30)
    os = models.CharField(max_length=30)

    class Meta:
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["project", "visitor", "created_at"]),
        ]

    def __str__(self):
        return f"{self.hostname}{self.path}"
