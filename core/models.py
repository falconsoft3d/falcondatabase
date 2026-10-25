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
