import datetime
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from projects import services
from projects.models import ProjectMember
from uptime.checker import Result

from . import runner
from .models import CronJob, CronRun


class Handler(BaseHTTPRequestHandler):
    calls = []

    def respond(self):
        Handler.calls.append((self.command, self.path, self.headers.get("Authorization")))
        status = {"/": 202, "/error": 503, "/moved": 308}.get(self.path, 404)
        self.send_response(status)
        if status == 308:
            self.send_header("Location", "/target")
        self.end_headers()

    do_GET = do_POST = respond

    def log_message(self, *args):
        pass


def make_job(project, **fields):
    return CronJob.objects.create(**{"project": project, "name": "Job", "url": "https://app.example/", **fields})


@override_settings(FALCONDB_UPTIME_ALLOW_PRIVATE=True)
class RunnerTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def setUp(self):
        Handler.calls = []
        owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(owner, "Shop")

    def test_sends_the_method_and_the_secret_header(self):
        job = make_job(self.project, url=f"{self.base}/", method=CronJob.POST,
                       header_name="Authorization", header_value="Bearer secret")
        result = runner.run(job)
        self.assertEqual((result.ok, result.status_code), (True, 202))
        self.assertEqual(Handler.calls, [("POST", "/", "Bearer secret")])
        job.refresh_from_db()
        self.assertTrue(job.last_ok)
        self.assertEqual(job.runs.count(), 1)

    def test_a_failed_call_is_recorded_and_not_repeated(self):
        job = make_job(self.project, url=f"{self.base}/error")
        result = runner.run(job)
        self.assertFalse(result.ok)
        self.assertEqual(len(Handler.calls), 1)
        job.refresh_from_db()
        self.assertEqual((job.last_ok, job.last_status_code), (False, 503))

    def test_redirects_are_not_followed(self):
        job = make_job(self.project, url=f"{self.base}/moved", header_name="Authorization", header_value="Bearer secret")
        result = runner.call(job)
        self.assertFalse(result.ok)
        self.assertIn("/target", result.error)
        self.assertEqual([path for _method, path, _auth in Handler.calls], ["/moved"])

    @override_settings(FALCONDB_UPTIME_ALLOW_PRIVATE=False)
    def test_private_addresses_are_refused(self):
        result = runner.call(make_job(self.project, url=f"{self.base}/"))
        self.assertFalse(result.ok)
        self.assertIn("private address", result.error)
        self.assertEqual(Handler.calls, [])

    def test_only_due_and_enabled_jobs_run_once(self):
        make_job(self.project, url=f"{self.base}/")
        make_job(self.project, url=f"{self.base}/paused", enabled=False)
        make_job(self.project, url=f"{self.base}/later", next_run_at=timezone.now() + datetime.timedelta(hours=1))
        self.assertEqual(runner.run_due(), 1)
        self.assertEqual(runner.run_due(), 0)
        self.assertEqual([path for _method, path, _auth in Handler.calls], ["/"])

    def test_every_due_job_runs_when_they_go_one_at_a_time(self):
        make_job(self.project, url=f"{self.base}/")
        make_job(self.project, url=f"{self.base}/error")
        with mock.patch("cron.runner.MAX_PARALLEL", 1):
            self.assertEqual(runner.run_due(), 2)
        self.assertEqual(CronRun.objects.count(), 2)

    def test_daily_jobs_wait_a_day(self):
        job = make_job(self.project, interval=1440)
        now = timezone.now()
        job.schedule_next(now)
        self.assertEqual(job.next_run_at, now + datetime.timedelta(days=1))

    def test_prune_and_worker_once(self):
        job = make_job(self.project, url=f"{self.base}/")
        CronRun.objects.create(job=job, ok=True, created_at=timezone.now() - datetime.timedelta(days=31))
        out = StringIO()
        call_command("cron_worker", once=True, stdout=out)
        self.assertIn("Called 1 job(s), deleted 1 old run(s).", out.getvalue())
        self.assertEqual(CronRun.objects.count(), 1)


@override_settings(LANGUAGE_CODE="en")
class ViewTests(TestCase):
    SECRET = "Bearer very-secret-value"

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("ana", "ana@example.com", "pass12345")
        self.viewer = User.objects.create_user("leo", "leo@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")
        ProjectMember.objects.create(project=self.project, user=self.viewer, role=ProjectMember.VIEWER)
        self.url = reverse("projects:cron", args=["ana", self.project.slug])
        self.client.force_login(self.owner)

    def create(self, **fields):
        data = {"name": "Books", "url": "app.example/api/cron", "interval": "1", "method": "GET", "enabled": "on",
                "header_name": "Authorization", "header_value": self.SECRET, **fields}
        return self.client.post(self.url, data)

    def update(self, job, **fields):
        data = {"action": "update", "name": job.name, "url": job.url, "interval": job.interval, "method": job.method,
                "header_name": job.header_name, "enabled": "on", **fields}
        return self.client.post(job.get_absolute_url(), data)

    def test_create_edit_and_delete(self):
        response = self.create()
        job = CronJob.objects.get(project=self.project)
        self.assertRedirects(response, job.get_absolute_url())
        self.assertEqual((job.url, job.header_name, job.header_value),
                         ("https://app.example/api/cron", "Authorization", self.SECRET))
        self.assertContains(self.client.get(self.url), "Books")

        self.update(job, name="Daily", interval="1440")
        job.refresh_from_db()
        self.assertEqual((job.name, job.interval), ("Daily", 1440))

        self.client.post(job.get_absolute_url(), {"action": "delete"})
        self.assertFalse(CronJob.objects.exists())

    def test_the_secret_is_never_sent_to_the_browser(self):
        self.create()
        job = CronJob.objects.get()
        self.assertNotContains(self.client.get(job.get_absolute_url()), "very-secret-value")
        self.assertNotContains(self.update(job, url="https://other.example/"), "very-secret-value")

    def test_an_empty_value_keeps_the_saved_secret(self):
        self.create()
        job = CronJob.objects.get()
        self.update(job, name="Renamed")
        job.refresh_from_db()
        self.assertEqual((job.name, job.header_value), ("Renamed", self.SECRET))

    def test_a_new_host_needs_the_secret_again(self):
        self.create()
        job = CronJob.objects.get()
        self.assertContains(self.update(job, url="https://evil.example/"), "address changed")
        job.refresh_from_db()
        self.assertEqual(job.url, "https://app.example/api/cron")

        self.update(job, url="https://new.example/", header_value="Bearer new")
        job.refresh_from_db()
        self.assertEqual((job.url, job.header_value), ("https://new.example/", "Bearer new"))

    def test_the_header_can_be_removed(self):
        self.create()
        job = CronJob.objects.get()
        self.update(job, clear_header="on")
        job.refresh_from_db()
        self.assertEqual((job.header_name, job.header_value), ("", ""))

    def test_invalid_input(self):
        self.assertContains(self.create(header_name="Bad Header"), "letters, numbers and hyphens")
        self.assertContains(self.create(header_value="a\nb"), "line breaks")
        self.assertContains(self.create(header_value=""), "Enter the value")
        self.assertContains(self.create(url="ftp://app.example/"), "http://")
        self.assertFalse(CronJob.objects.exists())

    @override_settings(FALCONDB_CRON_MAX_JOBS=1)
    def test_jobs_per_project_are_limited(self):
        make_job(self.project)
        self.assertContains(self.create(), "up to 1 cron jobs")

    def test_run_now(self):
        job = make_job(self.project)
        with mock.patch("cron.runner.call", return_value=Result(ok=False, error="HTTP 502 Bad Gateway")):
            response = self.client.post(job.get_absolute_url(), {"action": "run"}, follow=True)
        self.assertContains(response, "HTTP 502 Bad Gateway")
        self.assertEqual(job.runs.count(), 1)

    def test_viewer_is_read_only_and_strangers_see_nothing(self):
        job = make_job(self.project, header_name="Authorization", header_value=self.SECRET)
        self.client.force_login(self.viewer)
        page = self.client.get(job.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "very-secret-value")
        self.assertEqual(self.client.post(job.get_absolute_url(), {"action": "run"}).status_code, 403)

        self.client.force_login(get_user_model().objects.create_user("eva", "eva@example.com", "pass12345"))
        self.assertEqual(self.client.get(job.get_absolute_url()).status_code, 404)
