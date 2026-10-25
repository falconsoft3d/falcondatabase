import secrets
import time

import segno
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_POST

from blog import posts as blog_posts

from . import avatars, changelog, totp
from .forms import SignupForm
from .models import Avatar, SiteSettings, TwoFactor

# Session keys of the two-step login and of the 2FA setup.
PENDING_LOGIN = "falcondb_2fa_pending"
SETUP_SECRET = "falcondb_2fa_setup"
VERIFY_TIMEOUT = 300
VERIFY_MAX_TRIES = 5


def home(request):
    latest_posts = blog_posts.posts_for(get_language())[:3]
    return render(request, "core/home.html", {"latest_posts": latest_posts})


EXTENSION_DIR = settings.BASE_DIR / "extension"


def extension_page(request):
    return render(request, "core/extension.html")


def extension_zip(request):
    """The Chrome extension, pre-configured for this server (URL and host permission)."""
    import io
    import json
    import zipfile
    from urllib.parse import urlsplit

    server = request.build_absolute_uri("/").rstrip("/")
    parts = urlsplit(server)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXTENSION_DIR.rglob("*")):
            if path.is_dir() or path.name.startswith("."):
                continue
            name = path.relative_to(EXTENSION_DIR).as_posix()
            if name == "config.js":
                content = f"// Pre-configured for {server}\nexport const DEFAULT_SERVER = {json.dumps(server)};\n"
            elif name == "manifest.json":
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest["host_permissions"] = [f"{parts.scheme}://{parts.hostname}/*"]
                content = json.dumps(manifest, indent=2)
            else:
                archive.write(path, f"falcondatabase-extension/{name}")
                continue
            archive.writestr(f"falcondatabase-extension/{name}", content)
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="falcondatabase-extension.zip"'
    return response


def csrf_failure(request, reason=""):
    """403 page for a rejected form that explains why (Django's default hides it)."""
    return render(request, "403_csrf.html", {
        "reason": reason,
        "origin": request.headers.get("Origin", ""),
        "is_secure": request.is_secure(),
    }, status=403)


def changelog_page(request):
    return render(request, "core/changelog.html", {"releases": changelog.releases(get_language())})


def cookies(request):
    return render(request, "core/cookies.html")


def docs(request):
    base_url = request.build_absolute_uri("/").rstrip("/")
    return render(request, "core/docs.html", {"base_url": base_url, "ref": "PROJECT_REF", "anon_key": "ANON_KEY"})


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if not SiteSettings.load().allow_signup:
        messages.info(request, _("Sign up is disabled. Ask the administrator for an account."))
        return redirect("login")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="core.backends.UsernameOrEmailBackend")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


class LoginView(auth_views.LoginView):
    """Password login; users with 2FA continue to ``login_verify``."""

    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not TwoFactor.objects.filter(user=user).exists():
            return super().form_valid(form)
        self.request.session[PENDING_LOGIN] = {
            "user": user.pk,
            "backend": user.backend,
            "next": self.get_success_url(),
            "started": time.time(),
            "tries": 0,
        }
        return redirect("login_verify")


def login_verify(request):
    pending = request.session.get(PENDING_LOGIN)
    if not pending or time.time() - pending["started"] > VERIFY_TIMEOUT:
        request.session.pop(PENDING_LOGIN, None)
        messages.error(request, _("The verification expired. Sign in again."))
        return redirect("login")
    device = TwoFactor.objects.select_related("user").filter(user_id=pending["user"], user__is_active=True).first()
    if device is None:
        request.session.pop(PENDING_LOGIN)
        return redirect("login")

    error = None
    if request.method == "POST":
        if device.verify(request.POST.get("code", "")):
            request.session.pop(PENDING_LOGIN)
            login(request, device.user, backend=pending["backend"])
            if len(device.recovery_codes) <= 2:
                messages.info(request, _("You have few recovery codes left. Generate new ones in Settings."))
            return redirect(pending["next"])
        pending["tries"] += 1
        if pending["tries"] >= VERIFY_MAX_TRIES:
            request.session.pop(PENDING_LOGIN)
            messages.error(request, _("Too many failed attempts. Sign in again."))
            return redirect("login")
        request.session[PENDING_LOGIN] = pending
        error = _("Invalid code. Try again.")
    return render(request, "registration/login_verify.html", {"error": error})


@login_required
def account(request):
    """Profile settings: picture, language, theme, password and two-step authentication."""
    action = request.POST.get("action")
    if action == "avatar":
        try:
            if "avatar" not in request.FILES:
                raise avatars.AvatarError(_("Choose an image."))
            avatars.save(request.user, request.FILES["avatar"])
        except avatars.AvatarError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Profile picture updated."))
        return redirect("account")
    if action == "avatar_delete":
        Avatar.objects.filter(user=request.user).delete()
        messages.success(request, _("Profile picture removed."))
        return redirect("account")

    form = PasswordChangeForm(request.user, request.POST or None)
    # Django autofocuses this field, which scrolls the settings page to the bottom.
    form.fields["old_password"].widget.attrs.pop("autofocus", None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # Keep the current session valid after the password hash changes.
        update_session_auth_hash(request, user)
        messages.success(request, _("Your password was changed."))
        return redirect("account")
    two_factor = TwoFactor.objects.filter(user=request.user).first()
    return render(request, "core/account.html", {
        "form": form, "two_factor": two_factor, "has_avatar": Avatar.objects.filter(user=request.user).exists(),
    })


def qr_svg(data):
    return mark_safe(segno.make(data, error="m").svg_inline(scale=5, border=2, dark="#0d1117", light="#ffffff"))


@login_required
def two_factor_setup(request):
    if TwoFactor.objects.filter(user=request.user).exists():
        return redirect("account")
    secret = request.session.get(SETUP_SECRET) or totp.generate_secret()
    request.session[SETUP_SECRET] = secret

    error = None
    if request.method == "POST":
        counter = totp.matching_counter(secret, request.POST.get("code", ""))
        if counter is None:
            error = _("Invalid code. Check the time on your phone and try again.")
        else:
            device = TwoFactor(user=request.user, secret=secret, last_counter=counter)
            codes = device.new_recovery_codes()
            device.save()
            request.session.pop(SETUP_SECRET)
            messages.success(request, _("Two-step authentication is enabled."))
            return render(request, "core/recovery_codes.html", {"codes": codes})

    uri = totp.provisioning_uri(secret, request.user.email or request.user.username)
    return render(request, "core/two_factor_setup.html", {
        "qr": qr_svg(uri), "secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "error": error,
    })


@login_required
@require_POST
def two_factor_manage(request):
    """Disable 2FA or regenerate recovery codes; both require the password."""
    device = get_object_or_404(TwoFactor, user=request.user)
    if not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, _("Incorrect password."))
        return redirect("account")
    if request.POST.get("action") == "disable":
        device.delete()
        messages.success(request, _("Two-step authentication is disabled."))
        return redirect("account")
    codes = device.new_recovery_codes()
    device.save(update_fields=["recovery_codes"])
    return render(request, "core/recovery_codes.html", {"codes": codes})


@login_required
def users(request):
    """Platform users. Only the admin (the single superuser) can see or manage them."""
    if not request.user.is_superuser:
        raise PermissionDenied
    site = SiteSettings.load()
    form = SignupForm()
    password_reset = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reset_password":
            user = get_object_or_404(get_user_model(), pk=request.POST.get("user"))
            # Shown once in this response only (never stored in messages or cookies).
            temporary = secrets.token_urlsafe(9)
            user.set_password(temporary)
            user.save(update_fields=["password"])  # also signs the user out everywhere
            if user == request.user:
                update_session_auth_hash(request, user)
            password_reset = {"username": user.username, "password": temporary}
        elif action == "signup":
            site.allow_signup = bool(request.POST.get("allow_signup"))
            site.save()
            messages.success(request, _("Sign up enabled.") if site.allow_signup else _("Sign up disabled."))
            return redirect("users")
        elif action == "site_analytics":
            enable = bool(request.POST.get("enabled"))
            project = site.analytics_project
            if enable and project is None:
                from projects import services

                project = services.create_project(request.user, "falcondatabase site",
                                                  _("Visits to the public pages of this site"))
                site.analytics_project = project
                site.save(update_fields=["analytics_project"])
            if project is not None:
                project.analytics_enabled = enable
                project.analytics_domains = request.get_host().split(":")[0] if enable else project.analytics_domains
                project.save(update_fields=["analytics_enabled", "analytics_domains", "updated_at"])
            messages.success(request, _("Site analytics enabled.") if enable else _("Site analytics disabled."))
            return redirect("users")
        elif action == "reset_2fa":
            user = get_object_or_404(get_user_model(), pk=request.POST.get("user"))
            TwoFactor.objects.filter(user=user).delete()
            messages.success(request, _("Two-step authentication removed for %(username)s.") % {"username": user.username})
            return redirect("users")
        elif action == "create":
            form = SignupForm(request.POST)
            if form.is_valid():
                user = form.save()
                messages.success(request, _("User “%(username)s” created.") % {"username": user.username})
                return redirect("users")

    user_list = (get_user_model().objects.annotate(project_count=Count("projects"))
                 .select_related("two_factor").order_by("-date_joined"))
    return render(request, "core/users.html", {
        "form": form, "users": user_list, "site": site, "password_reset": password_reset,
    })


@login_required
def avatar_image(request, user_id):
    avatar = get_object_or_404(Avatar, user_id=user_id)
    response = HttpResponse(bytes(avatar.image), content_type="image/webp")
    # The URL carries ?v=<timestamp>, so a new picture gets a new URL.
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    return response


def healthz(request):
    """Liveness check for Docker and load balancers: the app answers and the database is reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
    return JsonResponse({"status": "ok", "version": changelog.VERSION})


@cache_control(public=True, max_age=300)
def sdk(request):
    """Serve the JS client through Django so cross-origin ``import`` gets CORS headers."""
    source = (settings.BASE_DIR / "static" / "js" / "falcondb.js").read_text(encoding="utf-8")
    return HttpResponse(source, content_type="text/javascript; charset=utf-8")
