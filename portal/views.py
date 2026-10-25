"""Project portals: a standalone app at /app/<slug>/ where a project's users manage its tables.

Portal users are the project's app users (Authentication tab). Their session is
kept apart from dashboard accounts. Each table is hidden, view-only or editable
in the portal; tables with the Owner access rule only show the user's own rows.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from projects import activity, schema
from projects.models import Project, ProjectTable, ProjectUser

SESSION_KEY = "falcondb_portal"
ROWS_PER_PAGE = 25
MIN_PASSWORD_LENGTH = 6


def current_user(request, project):
    user_id = request.session.get(SESSION_KEY, {}).get(project.ref)
    if not user_id:
        return None
    return ProjectUser.objects.filter(pk=user_id, project=project, is_active=True).first()


def sign_in(request, project, user):
    request.session.cycle_key()
    sessions = request.session.get(SESSION_KEY, {})
    sessions[project.ref] = user.pk
    request.session[SESSION_KEY] = sessions
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])


def portal_view(view):
    """Resolve the portal and its signed-in user, and pass both to the view."""

    @wraps(view)
    def wrapper(request, username, slug, *args, **kwargs):
        project = get_object_or_404(Project, owner__username=username, portal_slug=slug, portal_enabled=True)
        user = current_user(request, project)
        return view(request, project, user, *args, **kwargs)

    return wrapper


def visible_tables(project):
    return project.tables.exclude(portal_mode=ProjectTable.PORTAL_HIDDEN).order_by("name")


def get_table(project, name):
    table = project.tables.filter(name=name).exclude(portal_mode=ProjectTable.PORTAL_HIDDEN).first()
    if table is None:
        raise Http404
    return table


def can_view(project, table, user):
    if user:
        return True
    return project.portal_public and table.access != ProjectTable.OWNER


def can_edit(table, user):
    return bool(user) and table.portal_mode == ProjectTable.PORTAL_EDIT


def row_filters(table, user):
    if table.access == ProjectTable.OWNER:
        return [(schema.OWNER_COLUMN, "eq", user.pk)] if user else [("id", "eq", -1)]
    return []


def portal_args(project, *extra):
    return [project.owner.username, project.portal_slug, *extra]


def login_redirect(project, request):
    return redirect(f"{reverse('portal:login', args=portal_args(project))}?next={request.get_full_path()}")


def context(project, user, **extra):
    return {"project": project, "portal_user": user, "tables": visible_tables(project), **extra}


def editable_columns(table):
    return [c for c in table.columns() if not c.is_system]


def values_from_post(request, columns, skip_empty):
    values = {}
    for column in columns:
        value = schema.parse_form_value(request.POST.get(column.name), column)
        if value is not None or not skip_empty:
            values[column.name] = value
    return values


@portal_view
def home(request, project, user):
    tables = list(visible_tables(project))
    if not user and not project.portal_public:
        return login_redirect(project, request)
    for table in tables:
        table.allowed = can_view(project, table, user)
    return render(request, "portal/home.html", context(project, user, table_list=tables))


@portal_view
def login(request, project, user):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = ""
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        candidate = project.users.filter(email=email, is_active=True).first()
        if candidate and check_password(request.POST.get("password", ""), candidate.password):
            sign_in(request, project, candidate)
            return redirect(next_url or reverse("portal:home", args=portal_args(project)))
        error = _("Incorrect email or password.")
    return render(request, "portal/login.html", context(project, user, error=error, next=next_url, mode="login"))


@portal_view
def signup(request, project, user):
    if not project.allow_signup:
        raise Http404
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        if "@" not in email:
            error = _("The email is not valid.")
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = _("The password must have at least %(n)s characters.") % {"n": MIN_PASSWORD_LENGTH}
        elif project.users.filter(email=email).exists():
            error = _("A user with that email already exists.")
        else:
            new_user = ProjectUser(project=project, email=email)
            new_user.set_password(password)
            new_user.save()
            activity.record(project, "app_user_signed_up", actor=email)
            sign_in(request, project, new_user)
            return redirect("portal:home", *portal_args(project))
    return render(request, "portal/login.html", context(project, user, error=error, mode="signup"))


@require_POST
@portal_view
def logout(request, project, user):
    sessions = request.session.get(SESSION_KEY, {})
    sessions.pop(project.ref, None)
    request.session[SESSION_KEY] = sessions
    return redirect("portal:login", *portal_args(project))


@portal_view
def table_rows(request, project, user, table_name):
    table = get_table(project, table_name)
    if not can_view(project, table, user):
        return login_redirect(project, request)
    all_columns = table.columns()
    columns = [c for c in all_columns if c.name != schema.OWNER_COLUMN]  # shown in the grid
    query = request.GET.get("q", "").strip()
    order = request.GET.get("order", "-id")
    order_name = order.lstrip("-")
    if order_name not in {c.name for c in columns}:
        order, order_name = "-id", "id"
    filters = row_filters(table, user)
    _rows, total = schema.select_rows(project.schema, table.name, all_columns, filters, limit=1, search=query)
    page = Paginator(range(total), ROWS_PER_PAGE).get_page(request.GET.get("page"))
    rows, _total = schema.select_rows(
        project.schema, table.name, all_columns, filters, order=[(order_name, order.startswith("-"))],
        limit=ROWS_PER_PAGE, offset=page.start_index() - 1 if total else 0, search=query,
    )
    return render(request, "portal/table.html", context(
        project, user, table=table, columns=columns, rows=rows, page=page, total=total, query=query,
        order=order, order_name=order_name, descending=order.startswith("-"), editable=can_edit(table, user),
    ))


@portal_view
def row_new(request, project, user, table_name):
    table = get_table(project, table_name)
    if not can_edit(table, user):
        return login_redirect(project, request) if not user else redirect("portal:table", *portal_args(project, table.name))
    columns = editable_columns(table)
    values = {}
    if request.method == "POST":
        try:
            data = values_from_post(request, columns, skip_empty=True)
            if table.access == ProjectTable.OWNER:
                data[schema.OWNER_COLUMN] = user.pk
            schema.insert_row(project.schema, table.name, data)
            activity.record(project, "rows_inserted", actor=user.email, target=table.name)
        except (schema.SchemaError, DatabaseError) as exc:
            messages.error(request, str(exc).strip().splitlines()[0])
            values = {c.name: request.POST.get(c.name, "") for c in columns}
        else:
            messages.success(request, _("Saved."))
            return redirect("portal:table", *portal_args(project, table.name))
    fields = [(c, values.get(c.name, "")) for c in columns]
    return render(request, "portal/form.html", context(project, user, table=table, fields=fields, row=None))


@portal_view
def row_detail(request, project, user, table_name, row_id):
    table = get_table(project, table_name)
    if not can_view(project, table, user):
        return login_redirect(project, request)
    filters = row_filters(table, user)
    row = schema.get_row(project.schema, table.name, row_id, filters)
    if row is None:
        raise Http404
    columns = editable_columns(table)
    editable = can_edit(table, user)
    if request.method == "POST" and editable:
        try:
            schema.update_row(project.schema, table.name, row_id, values_from_post(request, columns, skip_empty=False),
                              filters=filters)
            activity.record(project, "row_updated", actor=user.email, target=table.name)
        except (schema.SchemaError, DatabaseError) as exc:
            messages.error(request, str(exc).strip().splitlines()[0])
        else:
            messages.success(request, _("Saved."))
            return redirect("portal:table", *portal_args(project, table.name))
    fields = [(c, schema.format_form_value(row.get(c.name), c)) for c in columns]
    template = "portal/form.html" if editable else "portal/detail.html"
    return render(request, template, context(project, user, table=table, fields=fields, row=row))


@require_POST
@portal_view
def row_delete(request, project, user, table_name, row_id):
    table = get_table(project, table_name)
    if not can_edit(table, user):
        raise Http404
    if schema.delete_row(project.schema, table.name, row_id, row_filters(table, user)):
        activity.record(project, "row_deleted", actor=user.email, target=table.name)
        messages.success(request, _("Deleted."))
    return redirect("portal:table", *portal_args(project, table.name))
