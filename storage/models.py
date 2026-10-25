import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from projects.models import Project, ProjectUser


def new_key():
    return uuid.uuid4().hex


class Bucket(models.Model):
    """A folder of files of a project. Public buckets are readable by anyone with the URL."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="buckets")
    name = models.SlugField(_("name"), max_length=63)
    public = models.BooleanField(_("public"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="unique_bucket_name_per_project")]

    def __str__(self):
        return f"{self.project}/{self.name}"


class StoredFile(models.Model):
    """A file in a bucket. The bytes live on disk under a random key, never under the user's path."""

    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE, related_name="files")
    path = models.CharField(max_length=512)
    key = models.CharField(max_length=32, default=new_key, editable=False, unique=True)
    size = models.BigIntegerField()
    content_type = models.CharField(max_length=127)
    owner = models.ForeignKey(ProjectUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="files")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["path"]
        constraints = [models.UniqueConstraint(fields=["bucket", "path"], name="unique_file_path_per_bucket")]

    def __str__(self):
        return f"{self.bucket.name}/{self.path}"

    @property
    def name(self):
        return self.path.rsplit("/", 1)[-1]

    @property
    def disk_path(self):
        return Path(settings.FALCONDB_STORAGE_ROOT) / self.bucket.project.ref / self.key
