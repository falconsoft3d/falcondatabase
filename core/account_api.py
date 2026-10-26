"""API for dashboard accounts (used by the Chrome extension).

    POST /api/account/token      {"username", "password", "code"?} -> {"token", "user", "expires_in"}
    GET  /api/account/me         current account
    GET  /api/account/analytics  ?days=1|7|14|30|90&p=<project slug> -> analytics of the account's projects (1 = today, by hour)

Requests send ``Authorization: Bearer <token>``. A token is a signature of the
user id and their session hash, so it stops working when the password changes.
"""

import secrets
from functools import wraps

from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from analytics import stats
from analytics.models import PageView
from api.auth import ApiError, get_bearer
from api.views import read_json, respond

from projects.models import Project

from .changelog import VERSION
from .models import Avatar, TwoFactor

TOKEN_SALT = "falcondb.account"
TOKEN_MAX_AGE = 30 * 24 * 3600


def issue_token(user):
    return signing.dumps({"u": user.pk, "h": user.get_session_auth_hash()}, salt=TOKEN_SALT)


def user_from_token(token):
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    user = get_user_model().objects.filter(pk=data.get("u"), is_active=True).first()
    if user is None or not secrets.compare_digest(str(data.get("h", "")), user.get_session_auth_hash()):
        return None
    return user


def user_dict(request, user):
    avatar = Avatar.objects.filter(user=user).values_list("updated_at", flat=True).first()
    return {
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_superuser,
        "avatar": request.build_absolute_uri(reverse("avatar", args=[user.pk])) if avatar else None,
        "dashboard": request.build_absolute_uri(reverse("dashboard")),
        "server_version": VERSION,
    }


def account_endpoint(*methods, auth=True):
    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return respond({"error": _("Method %(method)s not allowed.") % {"method": request.method}}, 405)
            try:
                if auth:
                    user = user_from_token(get_bearer(request))
                    if user is None:
                        raise ApiError(_("Invalid or expired token."), 401)
                    return view(request, user, *args, **kwargs)
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return respond({"error": exc.message}, exc.status)

        return wrapper

    return decorator


@account_endpoint("POST", auth=False)
def token(request):
    payload = read_json(request)
    if not isinstance(payload, dict):
        raise ApiError(_("Send an object with “username” and “password”."))
    user = authenticate(request, username=str(payload.get("username", "")).strip(),
                        password=str(payload.get("password", "")))
    if user is None:
        raise ApiError(_("Incorrect username or password."), 401)
    device = TwoFactor.objects.filter(user=user).first()
    if device:
        code = str(payload.get("code", "")).strip()
        if not code:
            return respond({"error": _("Enter the code from your authenticator app."), "two_factor_required": True}, 401)
        if not device.verify(code):
            return respond({"error": _("Invalid code. Try again."), "two_factor_required": True}, 401)
    return respond({"token": issue_token(user), "user": user_dict(request, user), "expires_in": TOKEN_MAX_AGE})


@account_endpoint("GET")
def me(request, user):
    return respond({"user": user_dict(request, user)})


@account_endpoint("GET")
def analytics(request, user):
    projects = list(Project.accessible_by(user).order_by("name"))
    ref = request.GET.get("p", "")
    selected = [p for p in projects if p.ref == ref] or projects
    days = stats.parse_period(request.GET.get("days"))
    report = stats.report(PageView.objects.filter(project__in=selected), days, by_project=True)
    return respond({
        "projects": [{"ref": p.ref, "slug": p.slug, "name": p.name, "analytics_enabled": p.analytics_enabled}
                     for p in projects],
        "selected": ref if len(selected) == 1 and ref else "",
        "report": report,
        "today": PageView.objects.filter(project__in=selected, created_at__date=report["end"]).count(),
        "links": {
            "analytics": request.build_absolute_uri(reverse("analytics")),
            "dashboard": request.build_absolute_uri(reverse("dashboard")),
        },
    })
