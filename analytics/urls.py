from django.urls import path

from . import views

urlpatterns = [
    path("a.js", views.script, name="analytics_script"),
    path("api/v1/<str:ref>/collect", views.collect, name="analytics_collect"),
    path("analytics/", views.overview, name="analytics"),
]
