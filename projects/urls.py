from django.urls import path

from analytics import views as analytics_views
from storage import views as storage_views
from uptime import views as uptime_views

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
    path(f"{P}/ai/", views.ai_access, name="ai"),
    path(f"{P}/analytics/", analytics_views.project_analytics, name="analytics"),
    path(f"{P}/uptime/", uptime_views.project_uptime, name="uptime"),
    path(f"{P}/uptime/<int:monitor_id>/", uptime_views.monitor_detail, name="uptime_monitor"),
    path(f"{P}/portal/", views.portal_settings, name="portal"),
    path(f"{P}/storage/", storage_views.dashboard, name="storage"),
    path(f"{P}/storage/<slug:bucket_name>/", storage_views.bucket_browser, name="bucket"),
    path(f"{P}/storage/<slug:bucket_name>/files/<int:file_id>/", storage_views.owner_download, name="bucket_file"),
    path(f"{P}/storage/<slug:bucket_name>/files/<int:file_id>/sign/", storage_views.owner_sign, name="bucket_file_sign"),
    path(f"{P}/settings/", views.settings, name="settings"),
    path(f"{P}/export/", views.project_export, name="export"),
    path(f"{P}/leave/", views.leave_project, name="leave"),
]
