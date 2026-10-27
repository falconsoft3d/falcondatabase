import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import totp


class SiteSettings(models.Model):
    """Singleton with the settings the admin controls from the dashboard."""

    allow_signup = models.BooleanField(_("allow sign up"), default=True)
    # Project (owned by the admin) that receives the visits to this site's public pages.
    analytics_project = models.OneToOneField("projects.Project", on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name="+")

    def __str__(self):
        return "falcondatabase"

    @classmethod
    def load(cls):
        obj, _created = cls.objects.select_related("analytics_project").get_or_create(pk=1)
        return obj

    @property
    def tracker_ref(self):
        project = self.analytics_project
        return project.ref if project and project.analytics_enabled else None


def hash_recovery_code(code):
    return hashlib.sha256(code.replace("-", "").lower().encode()).hexdigest()


class TwoFactor(models.Model):
    """TOTP second factor of a dashboard user."""

    RECOVERY_CODES = 8

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factor")
    secret = models.CharField(max_length=64)
    # Last accepted time step; a code can't be reused within its window.
    last_counter = models.BigIntegerField(default=0)
    recovery_codes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"2FA {self.user}"

    def verify(self, code):
        """Check a TOTP or recovery code. Recovery codes are consumed when used."""
        counter = totp.matching_counter(self.secret, code)
        if counter is not None and counter > self.last_counter:
            self.last_counter = counter
            self.save(update_fields=["last_counter"])
            return True
        digest = hash_recovery_code(code.strip())
        if digest in self.recovery_codes:
            self.recovery_codes.remove(digest)
            self.save(update_fields=["recovery_codes"])
            return True
        return False

    def new_recovery_codes(self):
        """Replace the recovery codes and return them in clear text (shown only once)."""
        codes = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(self.RECOVERY_CODES)]
        self.recovery_codes = [hash_recovery_code(code) for code in codes]
        return codes


class Avatar(models.Model):
    """Profile picture, stored resized in the database (so backups include it)."""

    SIZE = 256

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avatar")
    image = models.BinaryField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"avatar {self.user}"

    @property
    def version(self):
        return int(self.updated_at.timestamp())


def hash_access_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class AccessToken(models.Model):
    """Personal token an AI assistant (or any script) uses to manage the owner's projects.

    Only the SHA-256 of the token is stored; the clear text is shown once when it is created.
    """

    PREFIX = "fdb_ai_"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_tokens")
    name = models.CharField(_("name"), max_length=100)
    # None: every project the user can access (and they may create new ones).
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, null=True, blank=True,
                                related_name="+")
    read_only = models.BooleanField(_("read only"), default=False)
    digest = models.CharField(max_length=64, unique=True)
    hint = models.CharField(max_length=8)  # last characters, to recognize it in the list
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} · {self.name}"

    @classmethod
    def issue(cls, user, name, project=None, read_only=False):
        """Create a token and return ``(token, clear_text)``."""
        raw = cls.PREFIX + secrets.token_hex(24)
        token = cls.objects.create(user=user, name=name, project=project, read_only=read_only,
                                   digest=hash_access_token(raw), hint=raw[-4:])
        return token, raw

    @classmethod
    def lookup(cls, raw):
        if not raw or not raw.startswith(cls.PREFIX):
            return None
        return (cls.objects.select_related("user", "project")
                .filter(digest=hash_access_token(raw), user__is_active=True).first())
