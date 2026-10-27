"""Tools an AI assistant can call with a personal access token (``fdb_ai_…``).

The same tools are served over MCP (``/api/ai/mcp``) and plain HTTP
(``/api/ai/tools/<name>``). A token acts as its dashboard account: it reaches the
projects the account owns or that were shared with it (or only the token's
project), viewers and read-only tokens can only read, and every change shows up
in the project activity under the account's name.
"""

from dataclasses import dataclass, field

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from projects import activity, schema, services
from projects.forms import TableForm
from projects.models import Project, ProjectMember, ProjectTable, ProjectUser

from .auth import ApiError
from .views import MIN_PASSWORD_LENGTH, parse_filter


@dataclass
class Tool:
    name: str
    description: str
    properties: dict
    handler: object
    required: list = field(default_factory=list)
    write: bool = True
    destructive: bool = False

    def input_schema(self):
        return {"type": "object", "properties": self.properties, "required": self.required}

    def as_mcp(self):
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema(),
            "annotations": {"readOnlyHint": not self.write, "destructiveHint": self.destructive},
        }


@dataclass
class Context:
    token: object  # core.models.AccessToken

    @property
    def user(self):
        return self.token.user


TOOLS = {}

PROJECT = {"type": "string", "description": "Project ref (20 letters), “owner/slug” or the slug of one of your projects."}
TABLE = {"type": "string", "description": "Table name."}
COLUMN_TYPES = sorted(schema.COLUMN_TYPES)
ACCESS = {"type": "string", "enum": [a for a, _label in ProjectTable.ACCESS_CHOICES],
          "description": "public: anyone with the anon key reads and writes; public_read: anyone reads, signed-in users "
                         "write; authenticated: signed-in users only; owner: each user only sees their own rows; "
                         "private: service key only."}
COLUMN = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Lowercase letters, numbers and underscores."},
        "type": {"type": "string", "enum": COLUMN_TYPES},
        "required": {"type": "boolean", "description": "NOT NULL."},
        "unique": {"type": "boolean"},
        "default": {"type": "string", "description": "Literal default value, or now() for date/datetime, uuid() for uuid."},
    },
    "required": ["name", "type"],
}
USER_REF = {"type": ["string", "integer"], "description": "User id or email."}


def tool(name, description, properties=None, required=(), write=True, destructive=False):
    def decorator(handler):
        TOOLS[name] = Tool(name, description, properties or {}, handler, list(required), write, destructive)
        return handler

    return decorator


def available_tools(token):
    """Tools the token may call: read-only tokens don't see the ones that write."""
    return [t for t in TOOLS.values() if allowed(t, token)]


def allowed(t, token):
    if t.write and token.read_only:
        return False
    if t.name == "create_project" and token.project_id:
        return False
    if t.name == "create_account" and (token.project_id or not token.user.is_superuser):
        return False
    return True


def call(token, name, arguments):
    t = TOOLS.get(name)
    if t is None or not allowed(t, token):
        raise ApiError(_("Unknown tool: %(name)s.") % {"name": name}, 404)
    if not isinstance(arguments, dict):
        raise ApiError(_("The arguments must be a JSON object."))
    missing = [r for r in t.required if arguments.get(r) in (None, "")]
    if missing:
        raise ApiError(_("Missing argument: %(name)s.") % {"name": missing[0]})
    try:
        return t.handler(Context(token), **{k: v for k, v in arguments.items() if k in t.properties})
    except schema.SchemaError as exc:
        raise ApiError(str(exc))
    except DatabaseError as exc:
        raise ApiError(str(exc).strip().splitlines()[0])


# --- helpers -------------------------------------------------------------------

def get_project(ctx, ref, write=False):
    projects = Project.accessible_by(ctx.user).select_related("owner")
    if ctx.token.project_id:
        projects = projects.filter(pk=ctx.token.project_id)
    ref = str(ref or "").strip()
    owner, _sep, slug = ref.rpartition("/")
    if owner:
        project = projects.filter(owner__username=owner, slug=slug).first()
    else:
        project = projects.filter(ref=ref).first() or projects.filter(owner=ctx.user, slug=ref).first()
    if project is None:
        raise ApiError(_("Project “%(name)s” not found.") % {"name": ref}, 404)
    if write and project.role_for(ctx.user) == ProjectMember.VIEWER:
        raise ApiError(_("You only have read access to this project."), 403)
    return project


def get_table(project, name):
    table = project.tables.filter(name=str(name or "").strip()).first()
    if table is None:
        raise ApiError(_("Table “%(name)s” does not exist.") % {"name": name}, 404)
    return table


def get_app_user(project, ref):
    users = project.users.all()
    user = users.filter(pk=ref).first() if str(ref).isdigit() else users.filter(email=str(ref).strip().lower()).first()
    if user is None:
        raise ApiError(_("User “%(name)s” not found.") % {"name": ref}, 404)
    return user


def record(ctx, project, kind, target="", count=1):
    activity.record(project, kind, user=ctx.user, target=target, count=count)


def column_spec(raw):
    if not isinstance(raw, dict):
        raise ApiError(_("Each column must be an object with “name” and “type”."))
    return {
        "name": str(raw.get("name", "")).strip().lower(),
        "type_": raw.get("type") or "text",
        "required": bool(raw.get("required")),
        "unique": bool(raw.get("unique")),
        "default": str(raw["default"]) if raw.get("default") not in (None, "") else None,
    }


def table_info(table, with_rows=True):
    info = {
        "name": table.name,
        "description": table.description,
        "access": table.access,
        "columns": [{"name": c.name, "type": c.type, "nullable": c.nullable, "unique": c.unique, "default": c.default}
                    for c in table.columns()],
    }
    if with_rows:
        info["rows"] = table.row_count()
    return info


def check_password(password):
    if len(str(password)) < MIN_PASSWORD_LENGTH:
        raise ApiError(_("The password must have at least %(n)s characters.") % {"n": MIN_PASSWORD_LENGTH})


def user_dict(user):
    return {**user.as_dict(), "is_active": user.is_active}


# --- projects ------------------------------------------------------------------

@tool("list_projects", "List the projects this token can reach, with your role in each.", write=False)
def list_projects(ctx):
    projects = Project.accessible_by(ctx.user).select_related("owner").order_by("name")
    if ctx.token.project_id:
        projects = projects.filter(pk=ctx.token.project_id)
    return {"projects": [
        {"ref": p.ref, "name": p.name, "slug": f"{p.owner.username}/{p.slug}", "description": p.description,
         "role": p.role_for(ctx.user), "tables": p.tables.count()}
        for p in projects
    ]}


@tool("create_project", "Create a new project (its own PostgreSQL schema, API URL and keys).",
      {"name": {"type": "string"}, "description": {"type": "string"}}, required=["name"])
def create_project(ctx, name, description=""):
    name = str(name).strip()[:100]
    project = services.create_project(ctx.user, name, str(description or "")[:300])
    record(ctx, project, "project_created")
    return {"ref": project.ref, "name": project.name, "slug": f"{ctx.user.username}/{project.slug}"}


@tool("describe_project",
      "Show a project: its tables with columns and row counts, login settings, number of users, "
      "and the API URL and anon key a frontend needs.",
      {"project": PROJECT}, required=["project"], write=False)
def describe_project(ctx, project):
    project = get_project(ctx, project)
    return {
        "ref": project.ref,
        "name": project.name,
        "description": project.description,
        "role": project.role_for(ctx.user),
        "api_url": f"/api/v1/{project.ref}",
        "anon_key": project.anon_key,
        "auth_enabled": project.auth_enabled,
        "allow_signup": project.allow_signup,
        "users": project.users.count(),
        "tables": [table_info(t) for t in project.tables.all()],
    }


@tool("update_auth_settings", "Turn login on or off for the project's app users, and allow or block public sign up.",
      {"project": PROJECT, "auth_enabled": {"type": "boolean"}, "allow_signup": {"type": "boolean"}},
      required=["project"])
def update_auth_settings(ctx, project, auth_enabled=None, allow_signup=None):
    project = get_project(ctx, project, write=True)
    if auth_enabled is not None:
        project.auth_enabled = bool(auth_enabled)
    if allow_signup is not None:
        project.allow_signup = bool(allow_signup)
    project.save(update_fields=["auth_enabled", "allow_signup", "updated_at"])
    return {"auth_enabled": project.auth_enabled, "allow_signup": project.allow_signup}


# --- tables & columns ----------------------------------------------------------

@tool("create_table",
      "Create a real PostgreSQL table. Every table gets “id” and “created_at” automatically; "
      "tables with the owner policy also get “owner_id”.",
      {"project": PROJECT, "name": TABLE, "columns": {"type": "array", "items": COLUMN},
       "access": ACCESS, "description": {"type": "string"}},
      required=["project", "name"])
def create_table(ctx, project, name, columns=(), access=ProjectTable.PUBLIC_READ, description=""):
    project = get_project(ctx, project, write=True)
    form = TableForm({"name": str(name), "access": access or ProjectTable.PUBLIC_READ, "description": description or ""})
    if not form.is_valid():
        raise ApiError(" ".join(str(e) for errors in form.errors.values() for e in errors))
    if not isinstance(columns, (list, tuple)):
        raise ApiError(_("“columns” must be a list."))
    table = services.create_table(project, form.cleaned_data["name"], [column_spec(c) for c in columns],
                                  access=form.cleaned_data["access"], description=form.cleaned_data["description"])
    record(ctx, project, "table_created", table.name)
    return table_info(table)


@tool("update_table", "Change a table's description or access policy, or rename it.",
      {"project": PROJECT, "table": TABLE, "description": {"type": "string"}, "access": ACCESS,
       "new_name": {"type": "string", "description": "New table name."}},
      required=["project", "table"])
def update_table(ctx, project, table, description=None, access=None, new_name=None):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    with transaction.atomic():
        if new_name and new_name != table.name:
            old_name = table.name
            services.rename_table(table, str(new_name).strip().lower())
            record(ctx, project, "table_renamed", f"{old_name} → {table.name}")
        if description is not None:
            table.description = str(description)[:300]
            table.save(update_fields=["description", "updated_at"])
        if access is not None:
            if access not in dict(ProjectTable.ACCESS_CHOICES):
                raise ApiError(_("Unknown access policy."))
            services.set_access(table, access)
    return table_info(table, with_rows=False)


@tool("delete_table", "Delete a table and all its rows. This cannot be undone.",
      {"project": PROJECT, "table": TABLE}, required=["project", "table"], destructive=True)
def delete_table(ctx, project, table):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    name = table.name
    services.delete_table(table)
    record(ctx, project, "table_deleted", name)
    return {"deleted": name}


@tool("add_column", "Add a column to a table.",
      {"project": PROJECT, "table": TABLE, **COLUMN["properties"]}, required=["project", "table", "name", "type"])
def add_column(ctx, project, table, **column):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    services.add_column(table, **column_spec(column))
    record(ctx, project, "column_added", table.name)
    return table_info(table, with_rows=False)


@tool("rename_column", "Rename a column of a table.",
      {"project": PROJECT, "table": TABLE, "column": {"type": "string"}, "new_name": {"type": "string"}},
      required=["project", "table", "column", "new_name"])
def rename_column(ctx, project, table, column, new_name):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    services.rename_column(table, str(column), str(new_name).strip().lower())
    record(ctx, project, "column_renamed", table.name)
    return table_info(table, with_rows=False)


@tool("drop_column", "Remove a column and its data from a table. This cannot be undone.",
      {"project": PROJECT, "table": TABLE, "column": {"type": "string"}},
      required=["project", "table", "column"], destructive=True)
def drop_column(ctx, project, table, column):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    services.drop_column(table, str(column))
    record(ctx, project, "column_removed", table.name)
    return table_info(table, with_rows=False)


# --- rows ----------------------------------------------------------------------

@tool("query_rows",
      "Read rows of a table. Filters use the REST syntax: {\"age\": \"gt.18\", \"status\": \"active\", "
      "\"id\": \"in.(1,2,3)\"} with operators eq, neq, gt, gte, lt, lte, like, ilike, is, in.",
      {"project": PROJECT, "table": TABLE,
       "filters": {"type": "object", "description": "Column → value or “operator.value”."},
       "search": {"type": "string", "description": "Text to look for in any column."},
       "select": {"type": "array", "items": {"type": "string"}, "description": "Columns to return (default all)."},
       "order": {"type": "string", "description": "For example “created_at.desc,name”."},
       "limit": {"type": "integer", "description": "Default 50."}, "offset": {"type": "integer"}},
      required=["project", "table"], write=False)
def query_rows(ctx, project, table, filters=None, search=None, select=None, order="", limit=50, offset=0):
    project = get_project(ctx, project)
    table = get_table(project, table)
    if filters is not None and not isinstance(filters, dict):
        raise ApiError(_("“filters” must be an object."))
    parsed = [parse_filter(k, v) if isinstance(v, str) else (k, "eq", v) for k, v in (filters or {}).items()]
    order_by = []
    for part in filter(None, str(order or "").split(",")):
        name, _sep, direction = part.strip().partition(".")
        order_by.append((name, direction.lower() == "desc"))
    try:
        limit, offset = max(0, min(int(limit or 50), settings.FALCONDB_MAX_PAGE_SIZE)), max(0, int(offset or 0))
    except (TypeError, ValueError):
        raise ApiError(_("“limit” and “offset” must be integers."))
    rows, total = schema.select_rows(project.schema, table.name, table.columns(), filters=parsed, order=order_by,
                                     limit=limit, offset=offset, fields=list(select or []), search=search or None)
    return {"data": rows, "count": total}


@tool("insert_rows", "Insert one or more rows (all or none). Returns the created rows.",
      {"project": PROJECT, "table": TABLE, "rows": {"type": "array", "items": {"type": "object"}}},
      required=["project", "table", "rows"])
def insert_rows(ctx, project, table, rows):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ApiError(_("“rows” must be a list of objects."))
    columns = table.columns()
    with transaction.atomic():
        created = [schema.insert_row(project.schema, table.name, row, columns) for row in rows]
    if created:
        record(ctx, project, "rows_inserted", table.name, len(created))
    return {"data": created}


@tool("update_row", "Update the given columns of one row, by id.",
      {"project": PROJECT, "table": TABLE, "id": {"type": "integer"}, "values": {"type": "object"}},
      required=["project", "table", "id", "values"])
def update_row(ctx, project, table, id, values):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    if not isinstance(values, dict):
        raise ApiError(_("“values” must be an object."))
    row = schema.update_row(project.schema, table.name, int(id), values, table.columns())
    if row is None:
        raise ApiError(_("Row not found."), 404)
    record(ctx, project, "row_updated", table.name)
    return {"data": row}


@tool("delete_rows", "Delete rows by id. This cannot be undone.",
      {"project": PROJECT, "table": TABLE, "ids": {"type": "array", "items": {"type": "integer"}}},
      required=["project", "table", "ids"], destructive=True)
def delete_rows(ctx, project, table, ids):
    project = get_project(ctx, project, write=True)
    table = get_table(project, table)
    if not isinstance(ids, list):
        ids = [ids]
    with transaction.atomic():
        deleted = [int(i) for i in ids if schema.delete_row(project.schema, table.name, int(i))]
    if deleted:
        record(ctx, project, "row_deleted", table.name, len(deleted))
    return {"deleted": deleted}


# --- app users -----------------------------------------------------------------

@tool("list_users", "List the users of the project's app (the people who sign in to your frontend).",
      {"project": PROJECT}, required=["project"], write=False)
def list_users(ctx, project):
    project = get_project(ctx, project)
    return {"users": [user_dict(u) for u in project.users.all()]}


@tool("create_user", "Create a user of the project's app, with email and password and optional extra data.",
      {"project": PROJECT, "email": {"type": "string"}, "password": {"type": "string"},
       "data": {"type": "object", "description": "Free profile fields, e.g. {\"name\": \"Ana\"}."}},
      required=["project", "email", "password"])
def create_user(ctx, project, email, password, data=None):
    project = get_project(ctx, project, write=True)
    email = str(email).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError(_("The email is not valid."))
    check_password(password)
    if project.users.filter(email=email).exists():
        raise ApiError(_("A user with that email already exists."), 409)
    if data is not None and not isinstance(data, dict):
        raise ApiError(_("“data” must be an object."))
    user = ProjectUser(project=project, email=email, data=data or {})
    user.set_password(str(password))
    user.save()
    record(ctx, project, "app_user_added", email)
    return {"user": user_dict(user)}


@tool("update_user", "Change an app user's password, data (merged) or active state.",
      {"project": PROJECT, "user": USER_REF, "password": {"type": "string"}, "data": {"type": "object"},
       "is_active": {"type": "boolean"}},
      required=["project", "user"])
def update_user(ctx, project, user, password=None, data=None, is_active=None):
    project = get_project(ctx, project, write=True)
    user = get_app_user(project, user)
    if password:
        check_password(password)
        user.set_password(str(password))
    if data is not None:
        if not isinstance(data, dict):
            raise ApiError(_("“data” must be an object."))
        user.data = {**user.data, **data}
    if is_active is not None:
        user.is_active = bool(is_active)
    user.save()
    record(ctx, project, "app_user_updated", user.email)
    return {"user": user_dict(user)}


@tool("delete_user", "Delete an app user.", {"project": PROJECT, "user": USER_REF},
      required=["project", "user"], destructive=True)
def delete_user(ctx, project, user):
    project = get_project(ctx, project, write=True)
    user = get_app_user(project, user)
    email = user.email
    user.delete()
    record(ctx, project, "app_user_deleted", email)
    return {"deleted": email}


# --- platform accounts (admin only) --------------------------------------------

@tool("create_account", "Admin only: create a falcondatabase account (dashboard user).",
      {"username": {"type": "string"}, "email": {"type": "string"}, "password": {"type": "string"}},
      required=["username", "email", "password"])
def create_account(ctx, username, email, password):
    from core.forms import SignupForm

    form = SignupForm({"username": str(username).strip(), "email": str(email).strip(),
                       "password1": str(password), "password2": str(password)})
    if not form.is_valid():
        raise ApiError(" ".join(str(e) for errors in form.errors.values() for e in errors))
    account = form.save()
    return {"username": account.username, "email": account.email, "date_joined": account.date_joined}


def touch(token):
    """Remember when a token was last used (at most once a minute)."""
    now = timezone.now()
    if token.last_used_at is None or (now - token.last_used_at).total_seconds() > 60:
        type(token).objects.filter(pk=token.pk).update(last_used_at=now)
        token.last_used_at = now

