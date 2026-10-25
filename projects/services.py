"""Operations that touch both Django models and the project schema.

PostgreSQL DDL is transactional, so each operation runs inside
``transaction.atomic`` and the metadata never drifts from the real tables.
"""

from django.db import transaction
from django.utils.translation import gettext as _

from . import schema
from .models import Project, ProjectTable


@transaction.atomic
def create_project(owner, name, description=""):
    project = Project.objects.create(
        owner=owner,
        name=name,
        slug=Project.unique_slug(owner, name),
        description=description,
    )
    schema.create_schema(project.schema)
    return project


@transaction.atomic
def delete_project(project):
    schema.drop_schema(project.schema)
    project.delete()


@transaction.atomic
def create_table(project, name, columns, access=ProjectTable.PUBLIC_READ, description=""):
    name = schema.validate_identifier(name, _("Table name"))
    if project.tables.filter(name=name).exists():
        raise schema.SchemaError(_("A table named “%(name)s” already exists.") % {"name": name})
    schema.create_table(project.schema, name, columns, with_owner=access == ProjectTable.OWNER)
    project.save(update_fields=["updated_at"])
    return ProjectTable.objects.create(project=project, name=name, access=access, description=description)


@transaction.atomic
def delete_table(table):
    schema.drop_table(table.project.schema, table.name)
    table.delete()


@transaction.atomic
def set_access(table, access):
    if access == ProjectTable.OWNER:
        schema.ensure_owner_column(table.project.schema, table.name)
    table.access = access
    table.save(update_fields=["access", "updated_at"])


@transaction.atomic
def add_column(table, **column):
    schema.add_column(table.project.schema, table.name, **column)
    table.save(update_fields=["updated_at"])


@transaction.atomic
def drop_column(table, column):
    schema.drop_column(table.project.schema, table.name, column)
    table.save(update_fields=["updated_at"])
