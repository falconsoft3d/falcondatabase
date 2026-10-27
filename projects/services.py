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
    from storage.files import delete_project_files

    schema.drop_schema(project.schema)
    project.delete()
    transaction.on_commit(lambda: delete_project_files(project))


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


@transaction.atomic
def rename_table(table, new_name):
    new_name = schema.validate_identifier(new_name, _("Table name"))
    if table.project.tables.filter(name=new_name).exclude(pk=table.pk).exists():
        raise schema.SchemaError(_("A table named “%(name)s” already exists.") % {"name": new_name})
    schema.rename_table(table.project.schema, table.name, new_name)
    table.name = new_name
    table.save(update_fields=["name", "updated_at"])


@transaction.atomic
def rename_column(table, column, new_name):
    schema.rename_column(table.project.schema, table.name, column, new_name)
    table.save(update_fields=["updated_at"])
