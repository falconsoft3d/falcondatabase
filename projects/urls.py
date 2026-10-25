from django.urls import path

from . import views

app_name = "projects"

P = "<str:username>/<slug:slug>"
T = f"{P}/tables/<str:table_name>"

urlpatterns = [
    path(f"{P}/", views.overview, name="overview"),
    path(f"{P}/tables/", views.tables, name="tables"),
    path(f"{P}/tables/new/", views.table_new, name="table_new"),
    path(f"{T}/", views.table_data, name="table"),
    path(f"{T}/structure/", views.table_structure, name="table_structure"),
    path(f"{T}/api/", views.table_api, name="table_api"),
    path(f"{T}/rows/<int:row_id>/", views.row_edit, name="row_edit"),
    path(f"{T}/rows/<int:row_id>/delete/", views.row_delete, name="row_delete"),
    path(f"{P}/auth/", views.auth, name="auth"),
    path(f"{P}/api/", views.api_docs, name="api"),
    path(f"{P}/settings/", views.settings, name="settings"),
]
