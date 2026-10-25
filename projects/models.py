import secrets
import string

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.urls import reverse
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["owner", "slug"], name="unique_project_slug_per_owner")]

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
