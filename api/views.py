"""REST API consumed by external frontends.

    GET    /api/v1/<ref>                       tables and columns
    GET    /api/v1/<ref>/tables/<table>        list rows (filters, order, limit...)
    POST   /api/v1/<ref>/tables/<table>        insert one row or a list of rows
    GET    /api/v1/<ref>/tables/<table>/<id>   one row
    PATCH  /api/v1/<ref>/tables/<table>/<id>   update a row
    DELETE /api/v1/<ref>/tables/<table>/<id>   delete a row
    POST   /api/v1/<ref>/auth/signup           register an end user
    POST   /api/v1/<ref>/auth/login            get a token
    GET    /api/v1/<ref>/auth/user             current user (PATCH updates ``data``)
"""

import json
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from projects import activity, schema
from projects.models import Project, ProjectUser

from .auth import ApiError, access_filters, issue_token, resolve_client, visible_to

RESERVED_PARAMS = {"select", "order", "limit", "offset", "apikey"}
MIN_PASSWORD_LENGTH = 6


class ApiJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        # numeric columns: frontends expect JSON numbers, not strings.
        if isinstance(o, Decimal) and o.is_finite():
            return float(o)
        return super().default(o)


def respond(payload, status=200):
    return JsonResponse(payload, status=status, encoder=ApiJSONEncoder, json_dumps_params={"ensure_ascii": False})


def error(message, status):
    return respond({"error": message}, status)


def endpoint(*methods):
    """Shared plumbing: method check, project lookup, client resolution and errors."""

    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, ref, *args, **kwargs):
            if request.method not in methods:
                return error(_("Method %(method)s not allowed.") % {"method": request.method}, 405)
            project = Project.objects.filter(ref=ref).first()
            if project is None:
                return error(_("Project not found."), 404)
            try:
                client = resolve_client(request, project)
                return view(request, project, client, *args, **kwargs)
            except ApiError as exc:
                return error(exc.message, exc.status)
            except schema.SchemaError as exc:
                return error(str(exc), 400)
            except DatabaseError as exc:
                return error(str(exc).strip().splitlines()[0], 400)

        return wrapper

    return decorator


def actor_name(client):
    """Who made an API change, for the project's activity list."""
    if client.role == "user":
        return client.user.email
    return "API (service key)" if client.is_service else "API"


def read_json(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(_("The request body is not valid JSON."))


def get_table(project, client, name):
    table = project.tables.filter(name=name).first()
    if table is None or not visible_to(table, client):
        raise ApiError(_("Table “%(name)s” does not exist.") % {"name": name}, 404)
    return table


def parse_filter(name, raw):
    """``age=gt.18`` -> ("age", "gt", "18"); a value without operator means ``eq``."""
    op, sep, value = raw.partition(".")
    if not sep or op not in (*schema.FILTER_OPERATORS, "is", "in"):
        return name, "eq", raw
    if op == "in":
        value = [v.strip() for v in value.strip("()").split(",") if v.strip()]
    return name, op, value


def parse_order(raw):
    order = []
    for part in filter(None, raw.split(",")):
        name, _sep, direction = part.strip().partition(".")
        order.append((name, direction.lower() == "desc"))
    return order


def parse_int(raw, default, name):
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(_("“%(name)s” must be an integer.") % {"name": name})
    if value < 0:
        raise ApiError(_("“%(name)s” cannot be negative.") % {"name": name})
    return value


def clean_values(values, client):
    if not isinstance(values, dict):
        raise ApiError(_("Each row must be a JSON object."))
    values = dict(values)
    if not client.is_service:
        # Only the service key may write the system-managed columns.
        for column in schema.RESERVED_COLUMNS:
            values.pop(column, None)
    return values


@endpoint("GET")
def index(request, project, client):
    tables = [
        {
            "name": table.name,
            "description": table.description,
            "access": table.access,
            "columns": [
                {"name": c.name, "type": c.type, "nullable": c.nullable, "unique": c.unique, "default": c.default}
                for c in table.columns()
            ],
        }
        for table in project.tables.all()
        if visible_to(table, client)
    ]
    return respond({"project": project.name, "ref": project.ref, "auth_enabled": project.auth_enabled, "tables": tables})


@endpoint("GET", "POST")
def table_rows(request, project, client, table_name):
    table = get_table(project, client, table_name)
    columns = table.columns()

    if request.method == "GET":
        extra = access_filters(table, client, "read")
        params = request.GET
        filters = [parse_filter(k, v) for k in params if k not in RESERVED_PARAMS for v in params.getlist(k)]
        fields = [f.strip() for f in params.get("select", "").split(",") if f.strip() and f.strip() != "*"]
        limit = min(parse_int(params.get("limit"), 100, "limit"), settings.FALCONDB_MAX_PAGE_SIZE)
        rows, total = schema.select_rows(
            project.schema,
            table.name,
            columns,
            filters=filters + extra,
            order=parse_order(params.get("order", "")),
            limit=limit,
            offset=parse_int(params.get("offset"), 0, "offset"),
            fields=fields,
        )
        return respond({"data": rows, "count": total})

    access_filters(table, client, "write")
    payload = read_json(request)
    many = isinstance(payload, list)
    items = [clean_values(item, client) for item in (payload if many else [payload])]
    if client.role == "user" and table.access == table.OWNER:
        for item in items:
            item[schema.OWNER_COLUMN] = client.user.pk
    with transaction.atomic():
        created = [schema.insert_row(project.schema, table.name, item, columns) for item in items]
    activity.record(project, "rows_inserted", actor=actor_name(client), target=table.name, count=len(created))
    return respond({"data": created if many else created[0]}, 201)


@endpoint("GET", "PATCH", "PUT", "DELETE")
def table_row(request, project, client, table_name, row_id):
    table = get_table(project, client, table_name)
    row_id = int(row_id)

    if request.method == "GET":
        row = schema.get_row(project.schema, table.name, row_id, access_filters(table, client, "read"))
    elif request.method == "DELETE":
        if not schema.delete_row(project.schema, table.name, row_id, access_filters(table, client, "write")):
            raise ApiError(_("Row not found."), 404)
        activity.record(project, "row_deleted", actor=actor_name(client), target=table.name)
        return respond({"data": {"id": row_id}})
    else:
        extra = access_filters(table, client, "write")
        values = clean_values(read_json(request), client)
        row = schema.update_row(project.schema, table.name, row_id, values, filters=extra)
        if row is not None:
            activity.record(project, "row_updated", actor=actor_name(client), target=table.name)

    if row is None:
        raise ApiError(_("Row not found."), 404)
    return respond({"data": row})


def require_auth_enabled(project):
    if not project.auth_enabled:
        raise ApiError(_("Login is not enabled for this project."), 403)


def read_credentials(request):
    payload = read_json(request)
    if not isinstance(payload, dict):
        raise ApiError(_("Send an object with “email” and “password”."))
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        raise ApiError(_("“email” and “password” are required."))
    return email, password, payload


def session(user):
    return {"user": user.as_dict(), "token": issue_token(user), "expires_in": settings.FALCONDB_TOKEN_MAX_AGE}


@endpoint("POST")
def auth_signup(request, project, client):
    require_auth_enabled(project)
    if not project.allow_signup and not client.is_service:
        raise ApiError(_("Public sign up is disabled for this project."), 403)
    email, password, payload = read_credentials(request)
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError(_("The email is not valid."))
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ApiError(_("The password must have at least %(n)s characters.") % {"n": MIN_PASSWORD_LENGTH})
    if project.users.filter(email=email).exists():
        raise ApiError(_("A user with that email already exists."), 409)
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ApiError(_("“data” must be an object."))
    user = ProjectUser(project=project, email=email, data=data, last_login=timezone.now())
    user.set_password(password)
    user.save()
    activity.record(project, "app_user_signed_up", actor=email)
    return respond(session(user), 201)


@endpoint("POST")
def auth_login(request, project, client):
    require_auth_enabled(project)
    email, password, _payload = read_credentials(request)
    user = project.users.filter(email=email, is_active=True).first()
    if user is None or not user.check_password(password):
        raise ApiError(_("Incorrect email or password."), 401)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    return respond(session(user))


@endpoint("GET", "PATCH")
def auth_user(request, project, client):
    require_auth_enabled(project)
    if client.role != "user":
        raise ApiError(_("Send the user token in “Authorization: Bearer <token>”."), 401)
    user = client.user
    if request.method == "PATCH":
        payload = read_json(request)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ApiError(_("Send a “data” object with the fields to save."))
        user.data = {**user.data, **data}
        user.save(update_fields=["data"])
    return respond({"user": user.as_dict()})
