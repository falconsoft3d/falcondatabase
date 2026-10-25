"""Storage endpoints.

    GET    /storage/v1/<ref>/<bucket>/<path>                 download (public bucket, ?token= or keys)
    GET    /api/v1/<ref>/storage                              list buckets
    GET    /api/v1/<ref>/storage/<bucket>?prefix=             list files
    POST   /api/v1/<ref>/storage/<bucket>/<path>[?upsert=true] upload (multipart field "file")
    DELETE /api/v1/<ref>/storage/<bucket>/<path>             delete
    POST   /api/v1/<ref>/storage/sign/<bucket>/<path>         signed URL {"expires_in": seconds}
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from api.auth import ApiError, resolve_client
from api.views import actor_name, endpoint, read_json, respond
from projects import activity
from projects.models import Project
from projects.views import get_project, project_context

from . import files
from .models import Bucket, StoredFile

# Types a browser could execute: always downloaded, never rendered inline.
ACTIVE_TYPES = ("text/html", "application/xhtml+xml", "image/svg+xml", "text/javascript", "application/javascript",
                "text/xml", "application/xml")


def serve(stored, download=False):
    active = stored.content_type.split(";")[0].strip().lower() in ACTIVE_TYPES
    try:
        handle = stored.disk_path.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle, content_type=stored.content_type, as_attachment=download or active,
                            filename=stored.name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self' data:; media-src 'self'"
    return response


def file_dict(request, stored):
    url = request.build_absolute_uri(files.public_url(stored)) if stored.bucket.public else None
    return {"name": stored.name, "path": stored.path, "size": stored.size, "content_type": stored.content_type,
            "created_at": stored.created_at, "updated_at": stored.updated_at, "public_url": url}


def require_storage(project):
    if not project.storage_enabled:
        raise ApiError(_("Storage is not enabled for this project."), 403)


def get_bucket(project, name):
    bucket = project.buckets.filter(name=name).first()
    if bucket is None:
        raise ApiError(_("Bucket “%(name)s” does not exist.") % {"name": name}, 404)
    return bucket


def is_owner(client, stored):
    return client.role == "user" and stored.owner_id == client.user.pk


# --- public download ---------------------------------------------------------

def download(request, ref, bucket_name, path):
    project = Project.objects.filter(ref=ref, storage_enabled=True).first()
    if project is None:
        raise Http404
    stored = StoredFile.objects.select_related("bucket__project").filter(
        bucket__project=project, bucket__name=bucket_name, path=path).first()
    if stored is None:
        raise Http404
    allowed = stored.bucket.public or files.token_allows(request.GET.get("token", ""), stored)
    if not allowed and (request.headers.get("apikey") or request.headers.get("Authorization")):
        try:
            client = resolve_client(request, project)
        except ApiError as exc:
            return respond({"error": exc.message}, exc.status)
        allowed = client.is_service or is_owner(client, stored)
    if not allowed:
        return respond({"error": _("This file is private. Use a signed URL or the service key.")}, 403)
    return serve(stored, download=request.GET.get("download") == "1")


# --- REST API --------------------------------------------------------------------

@endpoint("GET")
def api_buckets(request, project, client):
    require_storage(project)
    return respond({"data": [{"name": b.name, "public": b.public} for b in project.buckets.all()]})


@endpoint("GET")
def api_list(request, project, client, bucket_name):
    require_storage(project)
    bucket = get_bucket(project, bucket_name)
    stored = bucket.files.all()
    if not client.is_service and not bucket.public:
        if client.role != "user":
            raise ApiError(_("You need to sign in for this operation."), 401)
        stored = stored.filter(owner=client.user)
    prefix = request.GET.get("prefix", "").strip("/")
    if prefix:
        stored = stored.filter(path__startswith=prefix + "/")
    return respond({"data": [file_dict(request, f) for f in stored[:1000]]})


@endpoint("POST", "PUT", "DELETE")
def api_object(request, project, client, bucket_name, path):
    require_storage(project)
    bucket = get_bucket(project, bucket_name)
    if request.method == "DELETE":
        stored = bucket.files.filter(path=files.clean_path(path)).first()
        if stored is None:
            raise ApiError(_("File not found."), 404)
        if not (client.is_service or is_owner(client, stored)):
            raise ApiError(_("Only the service key or the user who uploaded the file can delete it."), 403)
        files.delete(stored)
        activity.record(project, "file_deleted", actor=actor_name(client), target=bucket.name)
        return respond({"data": {"path": stored.path}})

    if not (client.is_service or client.role == "user"):
        raise ApiError(_("You need to sign in for this operation."), 401)
    upload = request.FILES.get("file")
    if upload is None:
        raise ApiError(_("Send the file as multipart/form-data in a field named “file”."))
    existing = bucket.files.filter(path=files.clean_path(path)).first()
    if existing and not (client.is_service or is_owner(client, existing)):
        raise ApiError(_("Only the service key or the user who uploaded the file can replace it."), 403)
    overwrite = request.method == "PUT" or request.GET.get("upsert") == "true"
    stored = files.save(bucket, path, upload, owner=client.user if client.role == "user" else None,
                        overwrite=overwrite)
    activity.record(project, "file_uploaded", actor=actor_name(client), target=bucket.name)
    return respond({"data": file_dict(request, stored)}, 201)


@endpoint("POST")
def api_sign(request, project, client, bucket_name, path):
    require_storage(project)
    bucket = get_bucket(project, bucket_name)
    stored = bucket.files.filter(path=files.clean_path(path)).first()
    if stored is None:
        raise ApiError(_("File not found."), 404)
    if not (client.is_service or is_owner(client, stored)):
        raise ApiError(_("Only the service key or the user who uploaded the file can share it."), 403)
    payload = read_json(request) if request.body else {}
    seconds = payload.get("expires_in", 3600) if isinstance(payload, dict) else 3600
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        raise ApiError(_("“expires_in” must be a number of seconds."))
    return respond({"data": {"signed_url": request.build_absolute_uri(files.signed_url(stored, seconds)),
                             "expires_in": max(1, min(seconds, files.MAX_SIGNED_SECONDS))}})


# --- dashboard -------------------------------------------------------------------

@login_required
def dashboard(request, username, slug):
    project = get_project(request, username, slug)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "settings":
                project.storage_enabled = bool(request.POST.get("storage_enabled"))
                project.save(update_fields=["storage_enabled", "updated_at"])
                messages.success(request, _("Storage settings saved."))
            elif action == "create_bucket":
                bucket = files.create_bucket(project, request.POST.get("name"), bool(request.POST.get("public")))
                activity.record(project, "bucket_created", user=request.user, target=bucket.name)
                messages.success(request, _("Bucket “%(name)s” created.") % {"name": bucket.name})
                return redirect(project.url("bucket", bucket.name))
        except files.StorageError as exc:
            messages.error(request, exc.message)
        return redirect(project.url("storage"))
    buckets = list(project.buckets.all())
    for bucket in buckets:
        bucket.count = bucket.files.count()
        bucket.bytes = sum(bucket.files.values_list("size", flat=True))
    from django.conf import settings

    return render(request, "storage/dashboard.html", project_context(
        request, project, "storage", buckets=buckets, used=files.project_usage(project),
        quota=settings.FALCONDB_STORAGE_QUOTA_MB * 1024 * 1024, max_file_mb=settings.FALCONDB_STORAGE_MAX_FILE_MB,
    ))


@login_required
def bucket_browser(request, username, slug, bucket_name):
    project = get_project(request, username, slug)
    bucket = get_object_or_404(Bucket, project=project, name=bucket_name)
    prefix = request.GET.get("prefix", "") or request.POST.get("prefix", "")

    if request.method == "POST":
        action = request.POST.get("action")
        back = project.url("bucket", bucket.name) + (f"?prefix={prefix}" if prefix.strip("/") else "")
        try:
            if action == "upload":
                folder = "/".join(p for p in [prefix.strip("/"), request.POST.get("folder", "").strip("/")] if p)
                uploads = request.FILES.getlist("files")
                for upload in uploads:
                    files.save(bucket, f"{folder}/{upload.name}" if folder else upload.name, upload)
                activity.record(project, "file_uploaded", user=request.user, target=bucket.name, count=len(uploads))
                messages.success(request, _("%(count)s file(s) uploaded.") % {"count": len(uploads)})
            elif action == "delete_file":
                stored = get_object_or_404(StoredFile, bucket=bucket, pk=request.POST.get("file"))
                files.delete(stored)
                activity.record(project, "file_deleted", user=request.user, target=bucket.name)
                messages.success(request, _("File deleted."))
            elif action == "settings":
                bucket.public = bool(request.POST.get("public"))
                bucket.save(update_fields=["public"])
                messages.success(request, _("Bucket updated."))
            elif action == "delete_bucket":
                if request.POST.get("confirm") != bucket.name:
                    raise files.StorageError(_("Type the bucket name to confirm."))
                files.delete_bucket(bucket)
                messages.success(request, _("Bucket deleted."))
                return redirect(project.url("storage"))
        except files.StorageError as exc:
            messages.error(request, exc.message)
        return redirect(back)

    prefix, folders, items = files.folder_listing(bucket, prefix)
    crumbs, acc = [], []
    for part in prefix.strip("/").split("/") if prefix else []:
        acc.append(part)
        crumbs.append((part, "/".join(acc)))
    for stored in items:
        stored.url = request.build_absolute_uri(files.public_url(stored)) if bucket.public else None
    return render(request, "storage/bucket.html", project_context(
        request, project, "storage", bucket=bucket, prefix=prefix, folders=folders, items=items, crumbs=crumbs,
    ))


@login_required
def owner_download(request, username, slug, bucket_name, file_id):
    project = get_project(request, username, slug)
    stored = get_object_or_404(StoredFile, bucket__project=project, bucket__name=bucket_name, pk=file_id)
    return serve(stored, download=request.GET.get("download") == "1")


@login_required
def owner_sign(request, username, slug, bucket_name, file_id):
    """Create a 1-hour signed link from the dashboard."""
    project = get_project(request, username, slug)
    stored = get_object_or_404(StoredFile, bucket__project=project, bucket__name=bucket_name, pk=file_id)
    url = request.build_absolute_uri(files.signed_url(stored, 3600))
    messages.info(request, _("Signed link valid for 1 hour: %(url)s") % {"url": url})
    parent = stored.path.rsplit("/", 1)[0] if "/" in stored.path else ""
    return redirect(project.url("bucket", bucket_name) + (f"?prefix={parent}" if parent else ""))
