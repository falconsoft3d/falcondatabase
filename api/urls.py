from django.urls import re_path

from . import ai, views

REF = r"(?P<ref>[a-z]{20})"
TABLE = r"(?P<table_name>[a-z_][a-z0-9_]{0,62})"

urlpatterns = [
    re_path(r"^ai/mcp/?$", ai.mcp, name="ai-mcp"),
    re_path(r"^ai/tools/?$", ai.tools, name="ai-tools"),
    re_path(r"^ai/tools/(?P<name>[a-z_]{1,40})/?$", ai.call_tool, name="ai-call"),
    re_path(rf"^v1/{REF}/?$", views.index, name="api-index"),
    re_path(rf"^v1/{REF}/tables/{TABLE}/?$", views.table_rows, name="api-rows"),
    re_path(rf"^v1/{REF}/tables/{TABLE}/(?P<row_id>[0-9]+)/?$", views.table_row, name="api-row"),
    re_path(rf"^v1/{REF}/auth/signup/?$", views.auth_signup, name="api-signup"),
    re_path(rf"^v1/{REF}/auth/login/?$", views.auth_login, name="api-login"),
    re_path(rf"^v1/{REF}/auth/user/?$", views.auth_user, name="api-user"),
]
