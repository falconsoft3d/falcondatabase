from django.conf import settings

from .models import SiteSettings

CONSENT_COOKIE = "falcondb_cookie_consent"


def site(request):
    return {
        "signup_enabled": SiteSettings.load().allow_signup,
        "contact_name": settings.FALCONDB_CONTACT_NAME,
        "contact_email": settings.FALCONDB_CONTACT_EMAIL,
        # "all", "essential" or None (banner not answered yet).
        "cookie_consent": request.COOKIES.get(CONSENT_COOKIE),
    }
