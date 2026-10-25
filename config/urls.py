from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import account_api
from core import views as core_views
from projects import views as project_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("docs/", core_views.docs, name="docs"),
    path("cookies/", core_views.cookies, name="cookies"),
    path("changelog/", core_views.changelog_page, name="changelog"),
    path("blog/", include("blog.urls")),
    path("sdk/falcondb.js", core_views.sdk, name="sdk"),
    path("healthz", core_views.healthz, name="healthz"),
    path("signup/", core_views.signup, name="signup"),
    path("login/", core_views.LoginView.as_view(), name="login"),
    path("login/verify/", core_views.login_verify, name="login_verify"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("settings/", core_views.account, name="account"),
    path("avatars/<int:user_id>/", core_views.avatar_image, name="avatar"),
    path("settings/2fa/", core_views.two_factor_setup, name="two_factor_setup"),
    path("settings/2fa/manage/", core_views.two_factor_manage, name="two_factor_manage"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("users/", core_views.users, name="users"),
    path("dashboard/", project_views.dashboard, name="dashboard"),
    path("new/", project_views.project_new, name="project_new"),
    path("new/import/", project_views.project_import, name="project_import"),
    path("admin/", admin.site.urls),
    path("", include("analytics.urls")),
    path("", include("storage.urls")),
    path("api/account/token", account_api.token, name="account_token"),
    path("api/account/me", account_api.me, name="account_me"),
    path("api/account/analytics", account_api.analytics, name="account_analytics"),
    path("extension/", core_views.extension_page, name="extension"),
    path("extension/falcondatabase-extension.zip", core_views.extension_zip, name="extension_zip"),
    path("api/", include("api.urls")),
    path("app/", include("portal.urls")),
    # Must stay last: /<username>/<project>/...
    path("", include("projects.urls")),
]
