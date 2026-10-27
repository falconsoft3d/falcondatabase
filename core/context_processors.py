from django.conf import settings

from .changelog import VERSION
from .models import SiteSettings

CONSENT_COOKIE = "falcondb_cookie_consent"
# Public pages measured by the site analytics (dashboards and portals never are).
TRACKED_PAGES = {"home", "docs", "cookies", "changelog", "extension", "ai", "login", "signup", "blog:index", "blog:detail"}


def site(request):
    settings_row = SiteSettings.load()
    match = getattr(request, "resolver_match", None)
    tracked = match is not None and match.view_name in TRACKED_PAGES
    return {
        "signup_enabled": settings_row.allow_signup,
        "site_tracker_ref": settings_row.tracker_ref if tracked else None,
        "contact_name": settings.FALCONDB_CONTACT_NAME,
        "contact_email": settings.FALCONDB_CONTACT_EMAIL,
        # "all", "essential" or None (banner not answered yet).
        "cookie_consent": request.COOKIES.get(CONSENT_COOKIE),
        "app_version": VERSION,
    }
