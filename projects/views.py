import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import schema, services
from .forms import TYPE_CHOICES, ColumnForm, ProjectForm, ProjectUserForm, TableForm, columns_from_post
from .models import Project, ProjectTable, ProjectUser

ROWS_PER_PAGE = 50


def db_error_message(exc):
    return str(exc).strip().splitlines()[0]


def get_project(request, username, slug):
    return get_object_or_404(Project, owner=request.user, owner__username=username, slug=slug)


def get_table(project, name):
    return get_object_or_404(ProjectTable, project=project, name=name)


def base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


def project_context(request, project, tab, **extra):
    return {"project": project, "tab": tab, "base_url": base_url(request), **extra}


@login_required
def dashboard(request):
    projects = request.user.projects.annotate(table_count=Count("tables", distinct=True),
                                              user_count=Count("users", distinct=True))
    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(name__icontains=query)
    return render(request, "projects/dashboard.html", {"projects": projects, "query": query})


@login_required
def project_new(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = services.create_project(request.user, form.cleaned_data["name"], form.cleaned_data["description"])
        messages.success(request, _("Project “%(name)s” created. Now create your first table!") % {"name": project.name})
        return redirect(project)
    return render(request, "projects/new.html", {"form": form})


@login_required
def overview(request, username, slug):
    project = get_project(request, username, slug)
    tables = list(project.tables.all())
    for table in tables:
        table.rows = table.row_count()
    return render(request, "projects/overview.html", project_context(
        request, project, "overview", tables=tables, user_count=project.users.count(),
    ))


@login_required
def tables(request, username, slug):
    project = get_project(request, username, slug)
    table_list = list(project.tables.all())
    for table in table_list:
        table.rows = table.row_count()
        table.column_count = len(table.columns())
    return render(request, "projects/tables.html", project_context(request, project, "tables", tables=table_list))


@login_required
def table_new(request, username, slug):
    project = get_project(request, username, slug)
    form = TableForm(request.POST or None)
    columns = columns_from_post(request.POST) if request.method == "POST" else []
    if request.method == "POST" and form.is_valid():
        try:
            table = services.create_table(project, form.cleaned_data["name"], columns,
                                          access=form.cleaned_data["access"],
                                          description=form.cleaned_data["description"])
        except (schema.SchemaError, DatabaseError) as exc:
            form.add_error(None, db_error_message(exc))
        else:
            messages.success(request, _("Table “%(name)s” created.") % {"name": table.name})
            return redirect(project.url("table", table.name))
    return render(request, "projects/table_new.html", project_context(
        request, project, "tables", form=form, columns=columns, type_choices=TYPE_CHOICES,
    ))


@login_required
def table_data(request, username, slug, table_name):
    project = get_project(request, username, slug)
    table = get_table(project, table_name)
    columns = table.columns()
    editable = [c for c in columns if not c.is_system]
    form_values = {}

    if request.method == "POST":
        values = {}
        try:
            for column in editable:
                value = schema.parse_form_value(request.POST.get(column.name), column)
                if value is not None:
                    values[column.name] = value
            schema.insert_row(project.schema, table.name, values, columns)
        except (schema.SchemaError, DatabaseError) as exc:
            messages.error(request, db_error_message(exc))
            form_values = {c.name: request.POST.get(c.name, "") for c in editable}
        else:
            messages.success(request, _("Row inserted."))
            return redirect(project.url("table", table.name))

    total = table.row_count()
    paginator = Paginator(range(total), ROWS_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    order = request.GET.get("order", "id")
    descending = order.startswith("-")
    order_name = order.lstrip("-")
    if order_name not in {c.name for c in columns}:
        order_name, descending = "id", False
    rows, _total = schema.select_rows(
        project.schema, table.name, columns, order=[(order_name, descending)],
        limit=ROWS_PER_PAGE, offset=page.start_index() - 1 if total else 0,
    )
    return render(request, "projects/table_data.html", project_context(
        request, project, "tables", table=table, columns=columns, editable=editable, rows=rows, page=page,
        total=total, order_name=order_name, descending=descending, form_values=form_values,
        table_tab="data",
    ))


@login_required
def table_structure(request, username, slug, table_name):
    project = get_project(request, username, slug)
    table = get_table(project, table_name)
    column_form = ColumnForm()

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "add_column":
                column_form = ColumnForm(request.POST)
                if column_form.is_valid():
                    services.add_column(table, **column_form.as_column())
                    messages.success(request, _("Column added."))
                    return redirect(project.url("table_structure", table.name))
            elif action == "drop_column":
                services.drop_column(table, request.POST.get("column", ""))
                messages.success(request, _("Column removed."))
                return redirect(project.url("table_structure", table.name))
            elif action == "settings":
                access = request.POST.get("access")
                if access not in dict(ProjectTable.ACCESS_CHOICES):
                    raise schema.SchemaError(_("Unknown access policy."))
                table.description = request.POST.get("description", "")[:300]
                services.set_access(table, access)
                messages.success(request, _("Settings saved."))
                return redirect(project.url("table_structure", table.name))
            elif action == "delete_table":
                if request.POST.get("confirm") != table.name:
                    raise schema.SchemaError(_("Type the table name to confirm."))
                services.delete_table(table)
                messages.success(request, _("Table “%(name)s” deleted.") % {"name": table_name})
                return redirect(project.url("tables"))
        except (schema.SchemaError, DatabaseError) as exc:
            messages.error(request, db_error_message(exc))

    return render(request, "projects/table_structure.html", project_context(
        request, project, "tables", table=table, columns=table.columns(), column_form=column_form,
        access_choices=ProjectTable.ACCESS_CHOICES, table_tab="structure",
    ))


@login_required
def table_api(request, username, slug, table_name):
    project = get_project(request, username, slug)
    table = get_table(project, table_name)
    columns = table.columns()
    editable = [c for c in columns if not c.is_system]
    sample = {c.name: sample_value(c) for c in editable}
    filter_column = next((c.name for c in editable if c.type == "text"), editable[0].name if editable else "id")
    return render(request, "projects/table_api.html", project_context(
        request, project, "tables", table=table, columns=columns, table_tab="api", filter_column=filter_column,
        sample_json=json.dumps(sample, ensure_ascii=False),
    ))


def sample_value(column):
    return {
        "text": "texto", "integer": 1, "bigint": 1, "decimal": 9.99, "float": 1.5, "boolean": True,
        "date": "2026-01-31", "datetime": "2026-01-31T12:00:00Z", "json": {"clave": "valor"},
        "uuid": "00000000-0000-0000-0000-000000000000",
    }.get(column.type, "valor")


@login_required
def row_edit(request, username, slug, table_name, row_id):
    project = get_project(request, username, slug)
    table = get_table(project, table_name)
    columns = table.columns()
    row = schema.get_row(project.schema, table.name, row_id)
    if row is None:
        raise Http404(_("Row not found."))
    editable = [c for c in columns if not c.is_system]

    if request.method == "POST":
        try:
            values = {c.name: schema.parse_form_value(request.POST.get(c.name), c) for c in editable}
            schema.update_row(project.schema, table.name, row_id, values, columns)
        except (schema.SchemaError, DatabaseError) as exc:
            messages.error(request, db_error_message(exc))
        else:
            messages.success(request, _("Row %(id)s updated.") % {"id": row_id})
            return redirect(project.url("table", table.name))

    fields = [(c, schema.format_form_value(row.get(c.name), c)) for c in editable]
    return render(request, "projects/row_edit.html", project_context(
        request, project, "tables", table=table, row=row, fields=fields, system=[c for c in columns if c.is_system],
    ))


@login_required
@require_POST
def row_delete(request, username, slug, table_name, row_id):
    project = get_project(request, username, slug)
    table = get_table(project, table_name)
    schema.delete_row(project.schema, table.name, row_id)
    messages.success(request, _("Row %(id)s deleted.") % {"id": row_id})
    return redirect(request.POST.get("next") or project.url("table", table.name))


@login_required
def auth(request, username, slug):
    project = get_project(request, username, slug)
    user_form = ProjectUserForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "settings":
            project.auth_enabled = bool(request.POST.get("auth_enabled"))
            project.allow_signup = bool(request.POST.get("allow_signup"))
            project.save(update_fields=["auth_enabled", "allow_signup", "updated_at"])
            messages.success(request, _("Login settings saved."))
            return redirect(project.url("auth"))
        if action == "add_user":
            user_form = ProjectUserForm(request.POST)
            if user_form.is_valid():
                email = user_form.cleaned_data["email"].lower()
                if project.users.filter(email=email).exists():
                    user_form.add_error("email", _("A user with that email already exists."))
                else:
                    user = ProjectUser(project=project, email=email)
                    user.set_password(user_form.cleaned_data["password"])
                    user.save()
                    messages.success(request, _("User %(email)s created.") % {"email": email})
                    return redirect(project.url("auth"))
        if action in ("toggle_user", "delete_user"):
            user = get_object_or_404(ProjectUser, project=project, pk=request.POST.get("user"))
            if action == "toggle_user":
                user.is_active = not user.is_active
                user.save(update_fields=["is_active"])
                message = _("User %(email)s activated.") if user.is_active else _("User %(email)s deactivated.")
                messages.success(request, message % {"email": user.email})
            else:
                user.delete()
                messages.success(request, _("User %(email)s deleted.") % {"email": user.email})
            return redirect(project.url("auth"))

    return render(request, "projects/auth.html", project_context(
        request, project, "auth", users=project.users.all(), user_form=user_form,
    ))


@login_required
def api_docs(request, username, slug):
    project = get_project(request, username, slug)
    return render(request, "projects/api.html", project_context(
        request, project, "api", tables=project.tables.all(),
    ))


@login_required
def settings(request, username, slug):
    project = get_project(request, username, slug)
    form = ProjectForm(instance=project)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update":
            form = ProjectForm(request.POST, instance=project)
            if form.is_valid():
                form.save()
                messages.success(request, _("Project updated."))
                return redirect(project.url("settings"))
        elif action == "regenerate_keys":
            project.regenerate_keys()
            project.save(update_fields=["anon_key", "service_key", "updated_at"])
            messages.success(request, _("New API keys were generated. The previous ones no longer work."))
            return redirect(project.url("settings"))
        elif action == "delete":
            if request.POST.get("confirm") != f"{project.owner.username}/{project.slug}":
                messages.error(request, _("The confirmation text does not match."))
            else:
                with transaction.atomic():
                    services.delete_project(project)
                messages.success(request, _("Project “%(name)s” deleted.") % {"name": project.name})
                return redirect("dashboard")

    return render(request, "projects/settings.html", project_context(request, project, "settings", form=form))
