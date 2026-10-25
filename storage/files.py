"""Storage operations shared by the dashboard and the API."""

import mimetypes
import re
import shutil
import time

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils.translation import gettext as _

from api.auth import ApiError

from .models import Bucket, StoredFile

BUCKET_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
SEGMENT_RE = re.compile(r"^[\w.\- ()@+]{1,255}$")
RESERVED_BUCKETS = {"sign"}
SIGN_SALT = "falcondb.storage"
MAX_SIGNED_SECONDS = 7 * 24 * 3600


class StorageError(ApiError):
    """A rejected storage operation; the API turns it into a JSON error with ``status``."""


def clean_bucket_name(name):
    name = (name or "").strip().lower()
    if not BUCKET_RE.match(name) or name in RESERVED_BUCKETS:
        raise StorageError(_("Bucket names use 3 to 63 lowercase letters, numbers and hyphens."))
    return name


def clean_path(path):
    """Normalize ``a//b/./c.png`` -> ``a/b/c.png`` and reject anything unsafe."""
    parts = [part for part in str(path or "").replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts or len(parts) > 20 or any(p == ".." or not SEGMENT_RE.match(p) for p in parts):
        raise StorageError(_("Invalid file path. Use letters, numbers, spaces, dots, dashes and “/” for folders."))
    path = "/".join(parts)
    if len(path) > 512:
        raise StorageError(_("The file path is too long."))
    return path


def create_bucket(project, name, public=False):
    name = clean_bucket_name(name)
    if project.buckets.filter(name=name).exists():
        raise StorageError(_("A bucket named “%(name)s” already exists.") % {"name": name}, 409)
    return Bucket.objects.create(project=project, name=name, public=public)


def project_usage(project):
    return StoredFile.objects.filter(bucket__project=project).aggregate(total=Sum("size"))["total"] or 0


@transaction.atomic
def save(bucket, path, upload, owner=None, overwrite=True):
    """Store an uploaded file (a Django UploadedFile) at ``path`` in ``bucket``."""
    path = clean_path(path)
    max_bytes = settings.FALCONDB_STORAGE_MAX_FILE_MB * 1024 * 1024
    if upload.size > max_bytes:
        raise StorageError(_("The file is too large (maximum %(mb)s MB).") % {"mb": settings.FALCONDB_STORAGE_MAX_FILE_MB}, 413)
    existing = bucket.files.select_for_update().filter(path=path).first()
    if existing and not overwrite:
        raise StorageError(_("A file already exists at “%(path)s”.") % {"path": path}, 409)
    used = project_usage(bucket.project) - (existing.size if existing else 0)
    if used + upload.size > settings.FALCONDB_STORAGE_QUOTA_MB * 1024 * 1024:
        raise StorageError(_("The project storage quota (%(mb)s MB) is full.") % {"mb": settings.FALCONDB_STORAGE_QUOTA_MB}, 413)

    content_type = (getattr(upload, "content_type", "") or mimetypes.guess_type(path)[0] or "application/octet-stream")
    stored = existing or StoredFile(bucket=bucket, path=path)
    stored.size = upload.size
    stored.content_type = content_type[:127]
    stored.owner = owner if owner is not None else stored.owner
    target = stored.disk_path
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".uploading")
    with temporary.open("wb") as destination:
        for chunk in upload.chunks():
            destination.write(chunk)
    temporary.replace(target)
    stored.save()
    return stored


def delete(stored):
    stored.disk_path.unlink(missing_ok=True)
    stored.delete()


@transaction.atomic
def delete_bucket(bucket):
    for stored in bucket.files.all():
        stored.disk_path.unlink(missing_ok=True)
    bucket.delete()


def delete_project_files(project):
    shutil.rmtree(f"{settings.FALCONDB_STORAGE_ROOT}/{project.ref}", ignore_errors=True)


def public_url(stored):
    return reverse("storage_file", args=[stored.bucket.project.ref, stored.bucket.name, stored.path])


def signed_url(stored, seconds):
    seconds = max(1, min(int(seconds), MAX_SIGNED_SECONDS))
    token = signing.dumps({"f": stored.pk, "e": int(time.time()) + seconds}, salt=SIGN_SALT)
    return f"{public_url(stored)}?token={token}"


def token_allows(token, stored):
    try:
        data = signing.loads(token, salt=SIGN_SALT)
    except signing.BadSignature:
        return False
    return data.get("f") == stored.pk and data.get("e", 0) >= time.time()


def folder_listing(bucket, prefix, files=None):
    """Split the files under ``prefix`` into immediate sub-folders and files (like a file browser)."""
    prefix = (prefix.strip("/") + "/") if prefix.strip("/") else ""
    folders, items = {}, []
    for stored in (files if files is not None else bucket.files.all()):
        if not stored.path.startswith(prefix):
            continue
        rest = stored.path[len(prefix):]
        if "/" in rest:
            folder = rest.split("/", 1)[0]
            folders[folder] = folders.get(folder, 0) + stored.size
        else:
            items.append(stored)
    return prefix, sorted(folders.items()), items
