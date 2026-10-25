"""Export a project to JSON and import it back as a new project.

The file holds the project settings and every table with its columns, defaults,
constraints and access rule. Rows are included only when asked. The users of
the project's apps are never exported (they include password hashes).

    {
      "format": "falcondatabase", "version": 1, "exported_at": "...",
      "project": {"name": "...", "description": "...", "auth_enabled": true, ...},
      "tables": [{"name": "products", "access": "public_read", "description": "",
                  "columns": [{"name": "price", "type": "decimal", "required": false,
                               "unique": false, "default": "0"}],
                  "rows": [{"id": 1, "created_at": "...", "price": "9.99"}]}]
    }
"""

import re

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from . import schema, services
from .models import ProjectTable

FORMAT = "falcondatabase"
VERSION = 1
BATCH = 1000
PROJECT_FIELDS = ("description", "auth_enabled", "allow_signup", "analytics_enabled", "analytics_domains",
                  "portal_enabled", "portal_public", "storage_enabled")
LITERAL_DEFAULT_RE = re.compile(r"^'(?P<value>(?:[^']|'')*)'(?:::[\w\s]+)?$")
PLAIN_DEFAULT_RE = re.compile(r"^-?[\w.]+$")


class TransferError(Exception):
    pass


def default_for_export(column):
    """Turn a PostgreSQL default expression back into what the dashboard accepts."""
    expression = column.default
    if not expression or expression == "identity":
        return None
    if expression == "now()":
        return "now()"
    if expression == "gen_random_uuid()":
        return "uuid()"
    literal = LITERAL_DEFAULT_RE.match(expression)
    if literal:
        return literal["value"].replace("''", "'")
    if PLAIN_DEFAULT_RE.match(expression):  # numbers, true/false
        return expression
    return None


def export_project(project, include_data=False):
    tables = []
    for table in project.tables.all():
        columns = table.columns()
        entry = {
            "name": table.name,
            "description": table.description,
            "access": table.access,
            "portal_mode": table.portal_mode,
            "columns": [
                {"name": c.name, "type": c.type, "required": not c.nullable, "unique": c.unique,
                 "default": default_for_export(c)}
                for c in columns if not c.is_system
            ],
        }
        if include_data:
            entry["rows"] = list(iter_rows(project, table, columns))
        tables.append(entry)
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": timezone.now().isoformat(),
        "project": {"name": project.name, **{field: getattr(project, field) for field in PROJECT_FIELDS}},
        "tables": tables,
        # Bucket definitions only: stored files are not part of the export.
        "buckets": [{"name": b.name, "public": b.public} for b in project.buckets.all()],
    }


def iter_rows(project, table, columns):
    offset = 0
    while True:
        rows, _total = schema.select_rows(project.schema, table.name, columns, order=[("id", False)],
                                          limit=BATCH, offset=offset)
        for row in rows:
            row.pop(schema.OWNER_COLUMN, None)  # app users are not exported
            yield row
        if len(rows) < BATCH:
            return
        offset += BATCH


def _require(condition, message):
    if not condition:
        raise TransferError(message)


def validate(data):
    _require(isinstance(data, dict) and data.get("format") == FORMAT, _("This is not a falcondatabase export file."))
    _require(data.get("version") == VERSION, _("Unsupported file version: %(version)s.") % {"version": data.get("version")})
    _require(isinstance(data.get("project"), dict), _("The file has no project information."))
    tables = data.get("tables", [])
    _require(isinstance(tables, list), _("“tables” must be a list."))
    access_values = dict(ProjectTable.ACCESS_CHOICES)
    for table in tables:
        _require(isinstance(table, dict) and isinstance(table.get("columns", []), list),
                 _("Every table needs a name and a list of columns."))
        _require(table.get("access", ProjectTable.PUBLIC_READ) in access_values,
                 _("Unknown access rule in table “%(name)s”.") % {"name": table.get("name")})
        _require(isinstance(table.get("rows", []), list),
                 _("The rows of table “%(name)s” must be a list.") % {"name": table.get("name")})


@transaction.atomic
def import_project(owner, data, name=None):
    """Create a new project from an export. Everything is rolled back on any error."""
    validate(data)
    info = data["project"]
    project = services.create_project(owner, (name or info.get("name") or "imported")[:100],
                                      str(info.get("description", ""))[:300])
    project.auth_enabled = bool(info.get("auth_enabled", False))
    project.allow_signup = bool(info.get("allow_signup", True))
    project.analytics_enabled = bool(info.get("analytics_enabled", False))
    project.analytics_domains = str(info.get("analytics_domains", ""))[:500]
    # The portal address must be unique, so an imported portal starts disabled until one is chosen.
    project.portal_public = bool(info.get("portal_public", False))
    project.storage_enabled = bool(info.get("storage_enabled", False))
    project.save()

    from storage.files import StorageError, create_bucket

    for bucket in data.get("buckets", []) or []:
        _require(isinstance(bucket, dict), _("Every bucket must be an object."))
        try:
            create_bucket(project, str(bucket.get("name", "")), bool(bucket.get("public")))
        except StorageError as exc:
            raise TransferError(exc.message)

    for entry in data.get("tables", []):
        columns = [
            {"name": str(c.get("name", "")), "type_": str(c.get("type", "")), "required": bool(c.get("required")),
             "unique": bool(c.get("unique")), "default": None if c.get("default") is None else str(c["default"])}
            for c in entry.get("columns", [])
        ]
        table = services.create_table(project, str(entry.get("name", "")), columns,
                                      access=entry.get("access", ProjectTable.PUBLIC_READ),
                                      description=str(entry.get("description", ""))[:300])
        if entry.get("portal_mode") in dict(ProjectTable.PORTAL_CHOICES):
            table.portal_mode = entry["portal_mode"]
            table.save(update_fields=["portal_mode"])
        rows = entry.get("rows", [])
        if rows:
            table_columns = table.columns()
            for row in rows:
                _require(isinstance(row, dict), _("Every row must be an object."))
                row = {key: value for key, value in row.items() if key != schema.OWNER_COLUMN}
                schema.insert_row(project.schema, table.name, row, table_columns)
            schema.sync_identity(project.schema, table.name)
    return project
