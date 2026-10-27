import secrets
import string

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from . import schema


def generate_ref():
    alphabet = string.ascii_lowercase
    return "".join(secrets.choice(alphabet) for _ in range(20))


def generate_anon_key():
    return f"fdb_anon_{secrets.token_hex(24)}"


def generate_service_key():
    return f"fdb_service_{secrets.token_hex(32)}"


class Project(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.CharField(_("description"), max_length=300, blank=True)
    ref = models.CharField(max_length=20, unique=True, default=generate_ref, editable=False)
    anon_key = models.CharField(max_length=64, unique=True, default=generate_anon_key)
    service_key = models.CharField(max_length=96, unique=True, default=generate_service_key)
    auth_enabled = models.BooleanField(_("login enabled"), default=False)
    allow_signup = models.BooleanField(_("allow public sign up"), default=True)
    analytics_enabled = models.BooleanField(_("analytics enabled"), default=False)
    # Optional comma separated host names allowed to send analytics (empty = any).
    analytics_domains = models.CharField(_("allowed domains"), max_length=500, blank=True)
    # Portal: a standalone app at /app/<portal_slug>/ where the project's users manage its tables.
    portal_enabled = models.BooleanField(_("portal enabled"), default=False)
    portal_slug = models.SlugField(_("portal address"), max_length=50, null=True, blank=True)
    portal_public = models.BooleanField(_("public portal"), default=False)
    storage_enabled = models.BooleanField(_("storage enabled"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="unique_project_slug_per_owner"),
            models.UniqueConstraint(fields=["owner", "portal_slug"], name="unique_portal_slug_per_owner"),
        ]

    def __str__(self):
        return f"{self.owner.username}/{self.slug}"

    @property
    def schema(self):
        return schema.schema_name(self.ref)

    def get_absolute_url(self):
        return reverse("projects:overview", args=[self.owner.username, self.slug])

    def url(self, name, *args):
        return reverse(f"projects:{name}", args=[self.owner.username, self.slug, *args])

    @staticmethod
    def unique_slug(owner, name):
        base = slugify(name) or "proyecto"
        slug, n = base, 2
        while Project.objects.filter(owner=owner, slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    def role_for(self, user):
        """"owner", "editor", "viewer" or None."""
        if not user.is_authenticated:
            return None
        if self.owner_id == user.pk:
            return "owner"
        return self.members.filter(user=user).values_list("role", flat=True).first()

    @staticmethod
    def accessible_by(user):
        """Projects the user owns or that were shared with them."""
        return Project.objects.filter(Q(owner=user) | Q(members__user=user)).distinct()

    def portal_url(self):
        return reverse("portal:home", args=[self.owner.username, self.portal_slug]) if self.portal_slug else ""

    def monitors_down(self):
        """Number of enabled uptime monitors that are down."""
        return self.monitors.filter(enabled=True, status="down").count()

    def analytics_hosts(self):
        return [d.strip().lower() for d in self.analytics_domains.split(",") if d.strip()]

    def regenerate_keys(self):
        self.anon_key = generate_anon_key()
        self.service_key = generate_service_key()


class ProjectTable(models.Model):
    """Metadata of a real table that lives in the project schema."""

    PUBLIC = "public"
    PUBLIC_READ = "public_read"
    AUTHENTICATED = "authenticated"
    OWNER = "owner"
    PRIVATE = "private"
    ACCESS_CHOICES = [
        (PUBLIC, _("Public — anyone with the anon key can read and write")),
        (PUBLIC_READ, _("Public read — anyone reads, only signed-in users write")),
        (AUTHENTICATED, _("Signed-in users — only authenticated users read and write")),
        (OWNER, _("Owner — each user only sees and edits their own rows")),
        (PRIVATE, _("Private — service key only")),
    ]
    ACCESS_LABELS = {
        PUBLIC: _("public"),
        PUBLIC_READ: _("public read"),
        AUTHENTICATED: _("signed-in"),
        OWNER: _("by owner"),
        PRIVATE: _("private"),
    }

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tables")
    name = models.CharField(max_length=63)
    description = models.CharField(_("description"), max_length=300, blank=True)
    access = models.CharField(_("access"), max_length=20, choices=ACCESS_CHOICES, default=PUBLIC_READ)

    PORTAL_HIDDEN = "hidden"
    PORTAL_VIEW = "view"
    PORTAL_EDIT = "edit"
    PORTAL_CHOICES = [(PORTAL_HIDDEN, _("Hidden")), (PORTAL_VIEW, _("View only")), (PORTAL_EDIT, _("View and edit"))]
    portal_mode = models.CharField(_("in the portal"), max_length=10, choices=PORTAL_CHOICES, default=PORTAL_VIEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="unique_table_name_per_project")]

    def __str__(self):
        return f"{self.project}/{self.name}"

    @property
    def access_label(self):
        return self.ACCESS_LABELS[self.access]

    def columns(self):
        return schema.get_columns(self.project.schema, self.name)

    def row_count(self):
        return schema.count_rows(self.project.schema, self.name)


class ProjectUser(models.Model):
    """An end user of an application built on top of a project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="users")
    email = models.EmailField()
    password = models.CharField(max_length=128)
    data = models.JSONField(_("data"), default=dict, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["project", "email"], name="unique_user_email_per_project")]

    def __str__(self):
        return self.email

    def set_password(self, raw):
        self.password = make_password(raw)

    def check_password(self, raw):
        return check_password(raw, self.password)

    def as_dict(self):
        return {
            "id": self.pk,
            "email": self.email,
            "data": self.data,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }


class ProjectMember(models.Model):
    """A dashboard account the owner shared the project with."""

    EDITOR = "editor"
    VIEWER = "viewer"
    ROLE_CHOICES = [(EDITOR, _("Editor")), (VIEWER, _("Viewer"))]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(_("role"), max_length=10, choices=ROLE_CHOICES, default=EDITOR)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="unique_member_per_project")]

    def __str__(self):
        return f"{self.user} in {self.project} ({self.role})"


class ActivityEvent(models.Model):
    """Something that changed in a project: feeds the contribution graph and the activity list."""

    KINDS = [
        ("project_created", _("created the project")),
        ("project_imported", _("imported the project")),
        ("table_created", _("created table")),
        ("table_deleted", _("deleted table")),
        ("column_added", _("added a column to")),
        ("column_removed", _("removed a column from")),
        ("column_renamed", _("renamed a column in")),
        ("table_renamed", _("renamed table")),
        ("rows_inserted", _("inserted rows in")),
        ("row_updated", _("updated a row in")),
        ("row_deleted", _("deleted a row from")),
        ("bucket_created", _("created bucket")),
        ("file_uploaded", _("uploaded files to")),
        ("file_deleted", _("deleted a file from")),
        ("member_added", _("shared the project with")),
        ("app_user_added", _("added app user")),
        ("app_user_signed_up", _("signed up")),
        ("app_user_updated", _("updated app user")),
        ("app_user_deleted", _("deleted app user")),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activity")
    kind = models.CharField(max_length=30, choices=KINDS)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    actor = models.CharField(max_length=255, blank=True)  # app user email or "API" when there is no account
    target = models.CharField(max_length=255, blank=True)  # table, bucket, member…
    count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "created_at"])]

    def __str__(self):
        return f"{self.project} {self.kind} {self.target}"

    @property
    def actor_name(self):
        return self.user.username if self.user_id else (self.actor or "API")
