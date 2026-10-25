import shutil
import tempfile
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from projects import services

from . import files
from .models import StoredFile


class StorageTestCase(TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.settings_override = override_settings(FALCONDB_STORAGE_ROOT=self.root)
        self.settings_override.enable()
        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")
        self.project.storage_enabled = True
        self.project.auth_enabled = True
        self.project.save()
        self.public = files.create_bucket(self.project, "images", public=True)
        self.private = files.create_bucket(self.project, "docs")
        self.base = f"/api/v1/{self.project.ref}/storage"

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.root, ignore_errors=True)

    def upload_file(self, name="a.txt", content=b"hello", content_type="text/plain"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def headers(self, key=None, token=None):
        headers = {"apikey": key or self.project.anon_key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def signup(self, email):
        response = self.client.post(f"/api/v1/{self.project.ref}/auth/signup", {"email": email, "password": "secret1"},
                                    content_type="application/json", headers={"apikey": self.project.anon_key})
        return response.json()["token"]

    def api_upload(self, bucket, path, key=None, token=None, query="", **kwargs):
        return self.client.post(f"{self.base}/{bucket}/{path}{query}", {"file": self.upload_file(**kwargs)},
                                headers=self.headers(key, token))


class StorageApiTests(StorageTestCase):
    def test_upload_list_download_delete_with_service_key(self):
        response = self.api_upload("images", "photos/cat.png", key=self.project.service_key,
                                   name="cat.png", content=b"\x89PNG", content_type="image/png")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual((data["path"], data["size"], data["content_type"]), ("photos/cat.png", 4, "image/png"))
        self.assertTrue(data["public_url"].endswith(f"/storage/v1/{self.project.ref}/images/photos/cat.png"))

        listing = self.client.get(f"{self.base}/images?prefix=photos", headers=self.headers()).json()["data"]
        self.assertEqual([f["path"] for f in listing], ["photos/cat.png"])

        download = self.client.get(f"/storage/v1/{self.project.ref}/images/photos/cat.png")
        self.assertEqual(b"".join(download.streaming_content), b"\x89PNG")
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")

        self.assertEqual(self.client.delete(f"{self.base}/images/photos/cat.png",
                                            headers=self.headers(self.project.service_key)).status_code, 200)
        self.assertFalse(StoredFile.objects.exists())
        self.assertEqual(list(__import__("pathlib").Path(self.root).rglob("*.*")), [])

    def test_anonymous_cannot_upload(self):
        self.assertEqual(self.api_upload("images", "x.txt").status_code, 401)

    def test_private_files_and_signed_urls(self):
        ana, bob = self.signup("ana@x.com"), self.signup("bob@x.com")
        self.assertEqual(self.api_upload("docs", "ana/cv.pdf", token=ana).status_code, 201)
        url = f"/storage/v1/{self.project.ref}/docs/ana/cv.pdf"

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers(token=bob)).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers(token=ana)).status_code, 200)
        self.assertEqual(self.client.get(url, headers=self.headers(self.project.service_key)).status_code, 200)

        # Users only list and manage their own private files.
        self.assertEqual(len(self.client.get(f"{self.base}/docs", headers=self.headers(token=bob)).json()["data"]), 0)
        self.assertEqual(len(self.client.get(f"{self.base}/docs", headers=self.headers(token=ana)).json()["data"]), 1)
        self.assertEqual(self.client.get(f"{self.base}/docs").status_code, 401)
        self.assertEqual(self.client.delete(f"{self.base}/docs/ana/cv.pdf", headers=self.headers(token=bob)).status_code, 403)
        self.assertEqual(self.api_upload("docs", "ana/cv.pdf", token=bob, query="?upsert=true").status_code, 403)

        response = self.client.post(f"{self.base}/sign/docs/ana/cv.pdf", {"expires_in": 60},
                                    content_type="application/json", headers=self.headers(token=ana))
        signed = response.json()["data"]["signed_url"]
        self.assertEqual(self.client.get(signed).status_code, 200)
        with mock.patch("storage.files.time.time", return_value=time.time() + 120):
            self.assertEqual(self.client.get(signed).status_code, 403)
        self.assertEqual(self.client.post(f"{self.base}/sign/docs/ana/cv.pdf", headers=self.headers(token=bob)).status_code, 403)

    def test_upsert_limits_and_paths(self):
        key = self.project.service_key
        self.assertEqual(self.api_upload("images", "a.txt", key=key).status_code, 201)
        self.assertEqual(self.api_upload("images", "a.txt", key=key).status_code, 409)
        self.assertEqual(self.api_upload("images", "a.txt", key=key, query="?upsert=true", content=b"new").status_code, 201)
        self.assertEqual(StoredFile.objects.get(path="a.txt").size, 3)
        for bad in ["../etc/passwd", "a/../../b", "%00x"]:
            self.assertEqual(self.api_upload("images", bad, key=key).status_code, 400, bad)
        with override_settings(FALCONDB_STORAGE_MAX_FILE_MB=0):
            self.assertEqual(self.api_upload("images", "big.txt", key=key).status_code, 413)
        with override_settings(FALCONDB_STORAGE_QUOTA_MB=0):
            self.assertEqual(self.api_upload("images", "q.txt", key=key).status_code, 413)
        self.assertEqual(self.api_upload("nope", "a.txt", key=key).status_code, 404)

    def test_active_content_is_downloaded_not_rendered(self):
        self.api_upload("images", "x.html", key=self.project.service_key, name="x.html",
                        content=b"<script>alert(1)</script>", content_type="text/html")
        response = self.client.get(f"/storage/v1/{self.project.ref}/images/x.html")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("sandbox", response["Content-Security-Policy"])

    def test_disabled_storage(self):
        self.project.storage_enabled = False
        self.project.save()
        self.assertEqual(self.client.get(f"{self.base}", headers=self.headers()).status_code, 403)
        self.assertEqual(self.api_upload("images", "a.txt", key=self.project.service_key).status_code, 403)


class StorageDashboardTests(StorageTestCase):
    def test_owner_manages_buckets_and_files(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.project.url("storage"), {"action": "create_bucket", "name": "backups"})
        self.assertRedirects(response, self.project.url("bucket", "backups"))
        url = self.project.url("bucket", "backups")
        self.client.post(url, {"action": "upload", "folder": "2026/10", "files": [self.upload_file("a.txt"),
                                                                                  self.upload_file("b.txt")]})
        self.assertEqual(sorted(StoredFile.objects.values_list("path", flat=True)), ["2026/10/a.txt", "2026/10/b.txt"])
        root = self.client.get(url)
        self.assertEqual(root.context["folders"], [("2026", 10)])
        inner = self.client.get(url + "?prefix=2026/10")
        self.assertEqual([f.name for f in inner.context["items"]], ["a.txt", "b.txt"])

        stored = StoredFile.objects.get(path="2026/10/a.txt")
        download = self.client.get(self.project.url("bucket_file", "backups", stored.pk))
        self.assertEqual(b"".join(download.streaming_content), b"hello")
        self.client.post(url, {"action": "delete_bucket", "confirm": "backups"})
        self.assertFalse(StoredFile.objects.exists())

    def test_other_users_cannot_browse(self):
        other = get_user_model().objects.create_user("bob", "bob@example.com", "pass12345")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.project.url("storage")).status_code, 404)

    def test_export_includes_buckets(self):
        from projects import transfer

        exported = transfer.export_project(self.project)
        self.assertEqual(exported["buckets"], [{"name": "docs", "public": False}, {"name": "images", "public": True}])
        copy = transfer.import_project(self.owner, exported, "Copy")
        self.assertEqual(sorted(copy.buckets.values_list("name", flat=True)), ["docs", "images"])
        self.assertTrue(copy.storage_enabled)
