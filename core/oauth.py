"""OAuth 2.1 so MCP clients can connect with a button instead of a pasted token.

    GET  /.well-known/oauth-protected-resource[/api/ai/mcp]   resource metadata (RFC 9728)
    GET  /.well-known/oauth-authorization-server              server metadata (RFC 8414)
    POST /oauth/register    dynamic client registration (RFC 7591), public clients only
    GET  /oauth/authorize   sign in and choose what the app may reach (PKCE S256 required)
    POST /oauth/token       authorization_code and refresh_token grants
    POST /oauth/revoke      revoke an access or refresh token (RFC 7009)

Adding ``/api/ai/mcp`` as a custom connector in Claude walks through all of it:
the MCP endpoint answers 401 pointing at the metadata, Claude registers, opens
the authorize page and exchanges the code. Each approval becomes an
``AccessToken`` listed in Settings → AI access, so it is revoked the same way.
"""

import base64
import hashlib
import ipaddress
import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from .models import AccessToken, OAuthClient, OAuthCode

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
BLOCKED_SCHEMES = {"javascript", "data", "vbscript", "file", "blob", "about"}
MAX_REDIRECT_URIS = 10
# Registered clients that never got a token are removed after this long.
UNUSED_CLIENT_TTL = timedelta(days=1)


def base_url(request):
    """Public address of this server, as MCP clients must see it.

    OAuth only works over HTTPS except on this machine, so a domain name without an
    explicit port is announced as https:// even when the proxy in front (nginx…) does not
    tell Django that it terminated TLS. Local addresses and IPs keep what the request says.
    """
    url = request.build_absolute_uri("/").rstrip("/")
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.port is None and not is_local_or_ip(parts.hostname):
        url = "https" + url[len("http"):]
    return url


def is_local_or_ip(hostname):
    if not hostname or hostname in LOOPBACK_HOSTS or hostname.endswith((".localhost", ".local")):
        return True
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def mcp_url(request):
    return f"{base_url(request)}/api/ai/mcp"


def resource_metadata_url(request):
    return f"{base_url(request)}/.well-known/oauth-protected-resource/api/ai/mcp"


def oauth_json(payload, status=200):
    response = JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


def oauth_error(code, description, status=400):
    return oauth_json({"error": code, "error_description": description}, status)


# --- metadata ------------------------------------------------------------------

def protected_resource(request):
    return oauth_json({
        "resource": mcp_url(request),
        "authorization_servers": [base_url(request)],
        "bearer_methods_supported": ["header"],
        "resource_name": "falcondatabase",
    })


def authorization_server(request):
    base = base_url(request)
    return oauth_json({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
        "authorization_response_iss_parameter_supported": True,
    })


# --- registration --------------------------------------------------------------

def valid_redirect_uri(uri):
    """HTTPS anywhere, plain HTTP only to this machine, or an app's own scheme."""
    if not isinstance(uri, str) or len(uri) > 2000 or "#" in uri:
        return False
    parts = urlsplit(uri)
    if parts.scheme == "https":
        return bool(parts.netloc)
    if parts.scheme == "http":
        return parts.hostname in LOOPBACK_HOSTS or f"[{parts.hostname}]" in LOOPBACK_HOSTS
    return bool(parts.scheme) and parts.scheme not in BLOCKED_SCHEMES


@csrf_exempt
def register(request):
    if request.method != "POST":
        return oauth_error("invalid_request", _("Method %(method)s not allowed.") % {"method": request.method}, 405)
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None
    if not isinstance(payload, dict):
        return oauth_error("invalid_client_metadata", _("The request body is not valid JSON."))
    uris = payload.get("redirect_uris")
    if not isinstance(uris, list) or not 0 < len(uris) <= MAX_REDIRECT_URIS:
        return oauth_error("invalid_redirect_uri", _("Send between 1 and %(n)s redirect_uris.") % {"n": MAX_REDIRECT_URIS})
    if not all(valid_redirect_uri(u) for u in uris):
        return oauth_error("invalid_redirect_uri",
                           _("Redirect URIs must use HTTPS (or HTTP to localhost)."))
    name = str(payload.get("client_name") or "").strip()[:100] or _("AI assistant")

    OAuthClient.objects.filter(created_at__lt=timezone.now() - UNUSED_CLIENT_TTL, tokens__isnull=True).delete()
    client = OAuthClient.objects.create(client_id=secrets.token_urlsafe(24), name=name, redirect_uris=uris)
    return oauth_json({
        "client_id": client.client_id,
        "client_id_issued_at": int(client.created_at.timestamp()),
        "client_name": client.name,
        "redirect_uris": client.redirect_uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }, 201)


# --- authorization -------------------------------------------------------------

class ClientRedirect(HttpResponseRedirect):
    """Redirect back to the client, whose callback may use its own URL scheme."""

    def __init__(self, uri, **params):
        self.allowed_schemes = [urlsplit(uri).scheme]
        super().__init__(uri + ("&" if "?" in uri else "?") + urlencode({k: v for k, v in params.items() if v}))


@login_required
def authorize(request):
    from projects.models import Project, ProjectMember

    params = request.GET
    client = OAuthClient.objects.filter(client_id=params.get("client_id", "")).first()
    redirect_uri = params.get("redirect_uri", "")
    if client is None or redirect_uri not in client.redirect_uris:
        # Never redirect to an address we cannot vouch for.
        return render(request, "core/oauth_authorize.html", {
            "error": _("This connection link is not valid. Start again from your assistant."),
        }, status=400)

    state, issuer = params.get("state", ""), base_url(request)
    if params.get("response_type") != "code":
        return ClientRedirect(redirect_uri, error="unsupported_response_type", state=state, iss=issuer)
    challenge = params.get("code_challenge", "")
    if params.get("code_challenge_method") != "S256" or not 43 <= len(challenge) <= 128:
        return ClientRedirect(redirect_uri, error="invalid_request", state=state, iss=issuer,
                              error_description="PKCE with S256 is required.")

    projects = Project.accessible_by(request.user).select_related("owner").order_by("name")
    if request.method == "POST":
        if request.POST.get("decision") != "allow":
            return ClientRedirect(redirect_uri, error="access_denied", state=state, iss=issuer)
        ref = request.POST.get("project", "")
        project = projects.filter(ref=ref).first() if ref else None
        read_only = request.POST.get("access") == "read" or (
            project is not None and project.role_for(request.user) == ProjectMember.VIEWER)
        code = OAuthCode.issue(client=client, user=request.user, project=project, read_only=read_only,
                               redirect_uri=redirect_uri, code_challenge=challenge)
        return ClientRedirect(redirect_uri, code=code, state=state, iss=issuer)

    return render(request, "core/oauth_authorize.html", {
        "client": client, "projects": projects, "redirect_host": urlsplit(redirect_uri).netloc or redirect_uri,
    })


# --- tokens --------------------------------------------------------------------

def read_form(request):
    """Token requests are form-encoded; accept JSON too for lenient clients."""
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}
    return request.POST


def pkce_matches(verifier, challenge):
    digest = hashlib.sha256(str(verifier).encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(expected, str(challenge))


def token_response(token, access, refresh):
    return oauth_json({
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": int(AccessToken.OAUTH_LIFETIME.total_seconds()),
        "refresh_token": refresh,
    })


@csrf_exempt
def token(request):
    if request.method != "POST":
        return oauth_error("invalid_request", _("Method %(method)s not allowed.") % {"method": request.method}, 405)
    data = read_form(request)
    grant = data.get("grant_type")

    if grant == "authorization_code":
        code = OAuthCode.consume(data.get("code"))
        if (code is None or code.client.client_id != data.get("client_id")
                or code.redirect_uri != data.get("redirect_uri")
                or not pkce_matches(data.get("code_verifier", ""), code.code_challenge)):
            return oauth_error("invalid_grant", _("The authorization code is invalid or expired."))
        return token_response(*AccessToken.issue_oauth(code.client, code.user, code.project, code.read_only))

    if grant == "refresh_token":
        found = AccessToken.lookup_refresh(data.get("refresh_token"))
        if found is None or found.client is None or found.client.client_id != data.get("client_id"):
            return oauth_error("invalid_grant", _("The refresh token is invalid or expired."))
        return token_response(found, *found.renew())

    return oauth_error("unsupported_grant_type", _("Use authorization_code or refresh_token."))


@csrf_exempt
def revoke(request):
    if request.method != "POST":
        return oauth_error("invalid_request", _("Method %(method)s not allowed.") % {"method": request.method}, 405)
    raw = str(read_form(request).get("token", ""))
    found = AccessToken.lookup(raw) or AccessToken.lookup_refresh(raw)
    if found is not None:
        found.delete()
    # RFC 7009: the answer is the same whether or not the token existed.
    return oauth_json({})
