"""Engine that manages the real PostgreSQL tables of each project.

Every project owns a PostgreSQL schema (``proj_<ref>``). Tables created from
the dashboard are real tables inside that schema, so they can be queried with
plain SQL as well as through the REST API.

All identifiers are validated against ``IDENTIFIER_RE`` and composed with
``psycopg.sql`` so user input never reaches a query unquoted.
"""

import json
import re
from dataclasses import dataclass

from django.db import connection, transaction
from django.utils.translation import gettext as _
from psycopg import sql
from psycopg.types.json import Jsonb

IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
JSON_OIDS = {114, 3802}  # json, jsonb

# Columns that every table gets automatically.
SYSTEM_COLUMNS = ("id", "created_at")
# Column added to tables using the "owner" access policy.
OWNER_COLUMN = "owner_id"
RESERVED_COLUMNS = set(SYSTEM_COLUMNS) | {OWNER_COLUMN}

# Friendly type name -> PostgreSQL type.
COLUMN_TYPES = {
    "text": "text",
    "integer": "integer",
    "bigint": "bigint",
    "decimal": "numeric",
    "float": "double precision",
    "boolean": "boolean",
    "date": "date",
    "datetime": "timestamp with time zone",
    "json": "jsonb",
    "uuid": "uuid",
}
PG_TO_FRIENDLY = {pg: friendly for friendly, pg in COLUMN_TYPES.items()}

# Special defaults a user can type instead of a literal value.
DEFAULT_EXPRESSIONS = {
    "now()": ({"date", "datetime"}, sql.SQL("now()")),
    "uuid()": ({"uuid"}, sql.SQL("gen_random_uuid()")),
}


class SchemaError(Exception):
    """Raised when a schema operation receives invalid input."""


@dataclass
class Column:
    name: str
    type: str
    pg_type: str
    nullable: bool
    default: str | None
    unique: bool
    primary_key: bool

    @property
    def is_system(self):
        return self.name in RESERVED_COLUMNS

    @property
    def input_type(self):
        """HTML input type used by the dashboard forms."""
        return {
            "integer": "number",
            "bigint": "number",
            "decimal": "number",
            "float": "number",
            "date": "date",
            "datetime": "datetime-local",
        }.get(self.type, "text")


def validate_identifier(name, kind=None):
    name = (name or "").strip()
    if not IDENTIFIER_RE.match(name):
        raise SchemaError(
            _("%(kind)s “%(name)s” is not valid: use lowercase letters, numbers and underscores, "
              "starting with a letter (max. 63 characters).") % {"kind": kind or _("Name"), "name": name}
        )
    return name


def schema_name(ref):
    return f"proj_{ref}"


def _table_ident(schema, table):
    return sql.Identifier(schema, table)


def _execute(query, params=None):
    # The savepoint keeps a failing statement from breaking an outer transaction.
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(_render(query), params)
        if cursor.description is None:
            return None
        names = [col.name for col in cursor.description]
        # Django's psycopg setup returns json/jsonb as text; decode it here.
        json_cols = {i for i, col in enumerate(cursor.description) if col.type_code in JSON_OIDS}
        return [
            {name: json.loads(v) if i in json_cols and v is not None else v for i, (name, v) in enumerate(zip(names, row))}
            for row in cursor.fetchall()
        ]


def _render(query):
    """Turn a psycopg ``sql.Composable`` into the string Django expects."""
    if isinstance(query, str):
        return query
    connection.ensure_connection()
    return query.as_string(connection.connection)


# --- schemas -----------------------------------------------------------------

def create_schema(schema):
    _execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))


def drop_schema(schema):
    _execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


# --- tables & columns --------------------------------------------------------

def column_definition(name, type_, required=False, unique=False, default=None):
    name = validate_identifier(name, _("Column name"))
    if name in RESERVED_COLUMNS:
        raise SchemaError(_("“%(name)s” is a reserved system column.") % {"name": name})
    if type_ not in COLUMN_TYPES:
        raise SchemaError(_("Unknown column type: %(type)s.") % {"type": type_})
    pg_type = COLUMN_TYPES[type_]
    parts = [sql.Identifier(name), sql.SQL(pg_type)]
    default = (default or "").strip()
    if default:
        if default in DEFAULT_EXPRESSIONS:
            allowed, expression = DEFAULT_EXPRESSIONS[default]
            if type_ not in allowed:
                raise SchemaError(_("The default %(default)s does not apply to type %(type)s.") % {"default": default, "type": type_})
            parts += [sql.SQL("DEFAULT"), expression]
        else:
            parts += [sql.SQL("DEFAULT"), sql.SQL("{}::{}").format(sql.Literal(default), sql.SQL(pg_type))]
    if required:
        parts.append(sql.SQL("NOT NULL"))
    if unique:
        parts.append(sql.SQL("UNIQUE"))
    return sql.SQL(" ").join(parts)


def create_table(schema, table, columns, with_owner=False):
    """Create a table. ``columns`` is a list of dicts for ``column_definition``."""
    table = validate_identifier(table, _("Table name"))
    names = [c["name"] for c in columns]
    if len(names) != len(set(names)):
        raise SchemaError(_("There are columns with duplicate names."))
    definitions = [
        sql.SQL("id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"),
        sql.SQL("created_at timestamp with time zone NOT NULL DEFAULT now()"),
    ]
    definitions += [column_definition(**c) for c in columns]
    if with_owner:
        definitions.append(sql.SQL("{} bigint").format(sql.Identifier(OWNER_COLUMN)))
    _execute(
        sql.SQL("CREATE TABLE {} ({})").format(_table_ident(schema, table), sql.SQL(", ").join(definitions))
    )
    return table


def drop_table(schema, table):
    _execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(_table_ident(schema, table)))


def add_column(schema, table, **column):
    _execute(
        sql.SQL("ALTER TABLE {} ADD COLUMN {}").format(_table_ident(schema, table), column_definition(**column))
    )


def drop_column(schema, table, column):
    if column in RESERVED_COLUMNS:
        raise SchemaError(_("“%(name)s” is a system column and cannot be removed.") % {"name": column})
    _execute(
        sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(_table_ident(schema, table), sql.Identifier(column))
    )


def ensure_owner_column(schema, table):
    _execute(
        sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} bigint").format(
            _table_ident(schema, table), sql.Identifier(OWNER_COLUMN)
        )
    )


def get_columns(schema, table):
    validate_identifier(schema)
    validate_identifier(table)
    rows = _execute(
        """
        SELECT a.attname AS name,
               format_type(a.atttypid, NULL) AS pg_type,
               NOT a.attnotnull AS nullable,
               pg_get_expr(d.adbin, d.adrelid) AS "default",
               a.attidentity <> '' AS is_identity,
               EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid = a.attrelid AND i.indisunique
                       AND i.indnatts = 1 AND i.indkey[0] = a.attnum) AS is_unique,
               EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid = a.attrelid AND i.indisprimary
                       AND a.attnum = ANY(i.indkey)) AS is_pk
        FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = to_regclass(%s) AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        # Both names were validated against IDENTIFIER_RE, so quoting is safe.
        [f'"{schema}"."{table}"'],
    )
    return [
        Column(
            name=r["name"],
            type=PG_TO_FRIENDLY.get(r["pg_type"], r["pg_type"]),
            pg_type=r["pg_type"],
            nullable=r["nullable"],
            default="identity" if r["is_identity"] else r["default"],
            unique=r["is_unique"],
            primary_key=r["is_pk"],
        )
        for r in rows
    ]


# --- rows --------------------------------------------------------------------

FILTER_OPERATORS = {
    "eq": "=",
    "neq": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "ilike": "ILIKE",
}


def _adapt(value, column):
    if column.type == "json" and value is not None:
        return Jsonb(value)
    return value


def _where(filters, columns_by_name):
    """Build a WHERE clause from ``[(column, operator, value), ...]``."""
    clauses, params = [], []
    for name, op, value in filters:
        if name not in columns_by_name:
            raise SchemaError(_("Column “%(name)s” does not exist.") % {"name": name})
        ident = sql.Identifier(name)
        if op in FILTER_OPERATORS:
            text_ops = op in ("like", "ilike")
            target = sql.SQL("{}::text").format(ident) if text_ops else ident
            clauses.append(sql.SQL("{} {} %s").format(target, sql.SQL(FILTER_OPERATORS[op])))
            params.append(value)
        elif op == "is":
            keyword = {"null": "NULL", "true": "TRUE", "false": "FALSE"}.get(str(value).lower())
            if keyword is None:
                raise SchemaError(_("The “is” operator accepts null, true or false."))
            clauses.append(sql.SQL("{} IS {}").format(ident, sql.SQL(keyword)))
        elif op == "in":
            values = list(value)
            if not values:
                clauses.append(sql.SQL("FALSE"))
                continue
            placeholders = sql.SQL(", ").join(sql.SQL("%s") for _ in values)
            clauses.append(sql.SQL("{} IN ({})").format(ident, placeholders))
            params.extend(values)
        else:
            raise SchemaError(_("Unknown operator: %(op)s.") % {"op": op})
    if not clauses:
        return sql.SQL(""), params
    return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses), params


def select_rows(schema, table, columns, filters=(), order=None, limit=50, offset=0, fields=None, search=None):
    """Return ``(rows, total_count)``.

    ``search`` keeps rows where any non-system column contains the text (case-insensitive).
    """
    by_name = {c.name: c for c in columns}
    where, params = _where(filters, by_name)
    searchable = [c.name for c in columns if not c.is_system]
    if search and searchable:
        matches = sql.SQL(" OR ").join(sql.SQL("{}::text ILIKE %s").format(sql.Identifier(n)) for n in searchable)
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where = (where + sql.SQL(" AND ") if filters else sql.SQL(" WHERE ")) + sql.SQL("({})").format(matches)
        params = params + [pattern] * len(searchable)
    if fields:
        missing = [f for f in fields if f not in by_name]
        if missing:
            raise SchemaError(_("Column “%(name)s” does not exist.") % {"name": missing[0]})
        projection = sql.SQL(", ").join(sql.Identifier(f) for f in fields)
    else:
        projection = sql.SQL("*")
    order_sql = sql.SQL(" ORDER BY id")
    if order:
        parts = []
        for name, descending in order:
            if name not in by_name:
                raise SchemaError(_("Column “%(name)s” does not exist.") % {"name": name})
            parts.append(sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL("DESC" if descending else "ASC")))
        order_sql = sql.SQL(" ORDER BY ") + sql.SQL(", ").join(parts)
    ident = _table_ident(schema, table)
    rows = _execute(
        sql.SQL("SELECT {} FROM {}").format(projection, ident) + where + order_sql + sql.SQL(" LIMIT %s OFFSET %s"),
        params + [limit, offset],
    )
    total = _execute(sql.SQL("SELECT count(*) AS n FROM {}").format(ident) + where, params)[0]["n"]
    return rows, total


def get_row(schema, table, row_id, filters=()):
    columns = get_columns(schema, table)
    rows, _total = select_rows(schema, table, columns, [("id", "eq", row_id), *filters], limit=1)
    return rows[0] if rows else None


def sync_identity(schema, table):
    """After inserting explicit ids, make the next generated id follow the largest one."""
    ident = _table_ident(schema, table)
    _execute(
        sql.SQL("SELECT setval(pg_get_serial_sequence({}, 'id'), coalesce(max(id), 0) + 1, false) FROM {}").format(
            sql.Literal(f'"{schema}"."{table}"'), ident
        )
    )


def storage_bytes(schemas):
    """Total disk size of the tables (with indexes and TOAST) in the given schemas."""
    if not schemas:
        return 0
    rows = _execute(
        "SELECT coalesce(sum(pg_total_relation_size(c.oid)), 0) AS size FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'r' AND n.nspname = ANY(%s)",
        [list(schemas)],
    )
    return int(rows[0]["size"])


def count_rows(schema, table):
    return _execute(sql.SQL("SELECT count(*) AS n FROM {}").format(_table_ident(schema, table)))[0]["n"]


def _check_values(values, by_name):
    for name in values:
        if name not in by_name:
            raise SchemaError(_("Column “%(name)s” does not exist.") % {"name": name})


def insert_row(schema, table, values, columns=None):
    columns = columns or get_columns(schema, table)
    by_name = {c.name: c for c in columns}
    _check_values(values, by_name)
    ident = _table_ident(schema, table)
    if values:
        names = list(values)
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            ident,
            sql.SQL(", ").join(sql.Identifier(n) for n in names),
            sql.SQL(", ").join(sql.SQL("%s") for _ in names),
        )
        params = [_adapt(values[n], by_name[n]) for n in names]
    else:
        query = sql.SQL("INSERT INTO {} DEFAULT VALUES RETURNING *").format(ident)
        params = []
    return _execute(query, params)[0]


def update_row(schema, table, row_id, values, columns=None, filters=()):
    columns = columns or get_columns(schema, table)
    by_name = {c.name: c for c in columns}
    _check_values(values, by_name)
    if not values:
        raise SchemaError(_("There are no values to update."))
    assignments = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(n)) for n in values)
    where, params = _where([("id", "eq", row_id), *filters], by_name)
    rows = _execute(
        sql.SQL("UPDATE {} SET {}").format(_table_ident(schema, table), assignments) + where + sql.SQL(" RETURNING *"),
        [_adapt(v, by_name[n]) for n, v in values.items()] + params,
    )
    return rows[0] if rows else None


def delete_row(schema, table, row_id, filters=()):
    columns = get_columns(schema, table)
    where, params = _where([("id", "eq", row_id), *filters], {c.name: c for c in columns})
    rows = _execute(
        sql.SQL("DELETE FROM {}").format(_table_ident(schema, table)) + where + sql.SQL(" RETURNING id"), params
    )
    return bool(rows)


# --- form helpers ------------------------------------------------------------

def parse_form_value(raw, column):
    """Convert a string coming from an HTML form into a Python value.

    Empty strings become ``None`` so the database applies NULL or the default.
    """
    if raw is None or raw == "":
        return None
    if column.type == "boolean":
        return {"true": True, "false": False}.get(raw.lower())
    if column.type == "json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SchemaError(_("“%(name)s” does not contain valid JSON: %(error)s.") % {"name": column.name, "error": exc.msg}) from exc
    return raw


def format_form_value(value, column):
    """Convert a database value into the string shown in an HTML input."""
    if value is None:
        return ""
    if column.type == "json":
        return json.dumps(value, ensure_ascii=False, indent=2)
    if column.type == "boolean":
        return "true" if value else "false"
    if column.type == "datetime":
        return value.strftime("%Y-%m-%dT%H:%M")
    return str(value)
