from django.urls import path

from . import views

app_name = "portal"

S = "<str:username>/<slug:slug>"
T = f"{S}/t/<str:table_name>"

urlpatterns = [
    path(f"{S}/", views.home, name="home"),
    path(f"{S}/login/", views.login, name="login"),
    path(f"{S}/signup/", views.signup, name="signup"),
    path(f"{S}/logout/", views.logout, name="logout"),
    path(f"{T}/", views.table_rows, name="table"),
    path(f"{T}/new/", views.row_new, name="row_new"),
    path(f"{T}/<int:row_id>/", views.row_detail, name="row"),
    path(f"{T}/<int:row_id>/delete/", views.row_delete, name="row_delete"),
]
