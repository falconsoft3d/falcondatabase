"""Who is calling the API and what they are allowed to do."""

import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.utils.translation import gettext as _

from projects.models import ProjectTable, ProjectUser
from projects.schema import OWNER_COLUMN

TOKEN_SALT = "falcondb.auth"


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class Client:
    role: str  # "service", "user" or "anon"
    user: ProjectUser | None = None

    @property
    def is_service(self):
        return self.role == "service"


def issue_token(user):
    return signing.dumps({"p": user.project.ref, "u": user.pk}, salt=TOKEN_SALT)


def user_from_token(project, token):
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=settings.FALCONDB_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    if data.get("p") != project.ref:
        return None
    return ProjectUser.objects.filter(pk=data.get("u"), project=project, is_active=True).first()


def get_api_key(request):
    return request.headers.get("apikey") or request.headers.get("X-Api-Key") or request.GET.get("apikey") or ""


def get_bearer(request):
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def resolve_client(request, project):
    key = get_api_key(request)
    if not key:
        raise ApiError(_("Missing API key. Send it in the “apikey” header."), 401)
    if secrets.compare_digest(key, project.service_key):
        return Client("service")
    if not secrets.compare_digest(key, project.anon_key):
        raise ApiError(_("Invalid API key."), 401)
    token = get_bearer(request)
    if not token:
        return Client("anon")
    if not project.auth_enabled:
        raise ApiError(_("Login is not enabled for this project."), 401)
    user = user_from_token(project, token)
    if user is None:
        raise ApiError(_("Invalid or expired token."), 401)
    return Client("user", user)


def require_user(client):
    if client.role != "user":
        raise ApiError(_("You need to sign in for this operation."), 401)


def access_filters(table, client, action):
    """Check the table policy and return the extra row filters to apply.

    ``action`` is "read" or "write".
    """
    if client.is_service:
        return []
    access = table.access
    if access == ProjectTable.PRIVATE:
        raise ApiError(_("This table is private: it can only be accessed with the service key."), 403)
    if access == ProjectTable.PUBLIC:
        return []
    if access == ProjectTable.PUBLIC_READ:
        if action == "write":
            require_user(client)
        return []
    require_user(client)
    if access == ProjectTable.OWNER:
        return [(OWNER_COLUMN, "eq", client.user.pk)]
    return []


def visible_to(table, client):
    return client.is_service or table.access != ProjectTable.PRIVATE
