from django.urls import path, re_path

from . import views

REF = r"(?P<ref>[a-z]{20})"
BUCKET = r"(?P<bucket_name>[a-z0-9][a-z0-9-]{1,61}[a-z0-9])"

urlpatterns = [
    path("storage/v1/<str:ref>/<slug:bucket_name>/<path:path>", views.download, name="storage_file"),
    re_path(rf"^api/v1/{REF}/storage/?$", views.api_buckets, name="api-storage-buckets"),
    re_path(rf"^api/v1/{REF}/storage/sign/{BUCKET}/(?P<path>.+)$", views.api_sign, name="api-storage-sign"),
    re_path(rf"^api/v1/{REF}/storage/{BUCKET}/?$", views.api_list, name="api-storage-list"),
    re_path(rf"^api/v1/{REF}/storage/{BUCKET}/(?P<path>.+)$", views.api_object, name="api-storage-object"),
]
