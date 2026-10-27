import datetime
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from projects import services
from projects.models import ProjectMember

from . import checker, net, notify, stats
from .checker import Result
from .models import Check, Incident, Monitor


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = {"/": 200, "/error": 503, "/moved": 302}.get(self.path, 404)
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass


@override_settings(FALCONDB_UPTIME_ALLOW_PRIVATE=True)
class ProbeTests(TestCase):
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

    def test_up_down_and_redirects(self):
        up = checker.probe(f"{self.base}/", retry_delay=0)
        self.assertTrue(up.ok)
        self.assertEqual(up.status_code, 200)
        self.assertIsNotNone(up.response_ms)
        self.assertTrue(checker.probe(f"{self.base}/moved", retry_delay=0).ok)
        down = checker.probe(f"{self.base}/error", retry_delay=0)
        self.assertFalse(down.ok)
        self.assertEqual(down.status_code, 503)
        self.assertIn("503", down.error)

    def test_connection_refused_is_retried(self):
        with mock.patch("uptime.checker.request_once", wraps=checker.request_once) as request:
            result = checker.probe("http://127.0.0.1:9/", timeout=1, retry_delay=0)
        self.assertFalse(result.ok)
        self.assertEqual(request.call_count, 2)


class GuardTests(TestCase):
    def test_private_addresses_are_blocked(self):
        for url in ("http://127.0.0.1/", "http://localhost:5432/", "http://10.0.0.5/", "http://169.254.169.254/latest/"):
            with self.subTest(url=url), self.assertRaises(net.BlockedAddress):
                net.guard(url)
        with self.assertRaises(net.BlockedAddress):
            net.guard("ftp://example.com/")
        result = checker.probe("http://127.0.0.1/", retry_delay=0)
        self.assertFalse(result.ok)
        self.assertIn("private address", result.error)

    @override_settings(FALCONDB_UPTIME_ALLOW_PRIVATE=True)
    def test_private_addresses_can_be_allowed(self):
        net.guard("http://127.0.0.1/")


@override_settings(LANGUAGE_CODE="en")
class RecordTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")
        self.monitor = Monitor.objects.create(project=self.project, url="https://shop.example/")

    def test_incident_opens_and_closes_with_one_alert_each(self):
        start = timezone.now()
        self.assertIsNone(checker.record(self.monitor, Result(ok=True, status_code=200, response_ms=80), start))
        self.assertEqual(checker.record(self.monitor, Result(ok=False, error="Timeout after 10 s"),
                                        start + datetime.timedelta(minutes=5)), notify.DOWN)
        self.assertIsNone(checker.record(self.monitor, Result(ok=False, error="Timeout after 10 s"),
                                         start + datetime.timedelta(minutes=10)))
        self.assertEqual(checker.record(self.monitor, Result(ok=True, status_code=200, response_ms=90),
                                        start + datetime.timedelta(minutes=15)), notify.UP)

        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.status, Monitor.UP)
        self.assertEqual(Check.objects.filter(monitor=self.monitor).count(), 4)
        incident = Incident.objects.get(monitor=self.monitor)
        self.assertEqual(incident.duration, datetime.timedelta(minutes=10))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])
        self.assertIn("shop.example", mail.outbox[0].subject)
        self.assertIn("10 min", mail.outbox[1].body)

    def test_no_email_when_notifications_are_off(self):
        self.monitor.notify = False
        self.monitor.webhook_url = "https://hooks.example/x"
        with mock.patch("uptime.notify.post_webhook") as webhook:
            checker.record(self.monitor, Result(ok=False, error="HTTP 500"))
        self.assertEqual(mail.outbox, [])
        webhook.assert_called_once()

    def test_due_monitors_are_claimed_and_rescheduled(self):
        paused = Monitor.objects.create(project=self.project, url="https://paused.example/", enabled=False)
        now = timezone.now()
        with mock.patch("uptime.checker.probe", return_value=Result(ok=True, status_code=200, response_ms=10)) as probe:
            self.assertEqual(checker.run_due(now, parallel=1), 1)
            self.assertEqual(checker.run_due(now, parallel=1), 0)
        probe.assert_called_once_with("https://shop.example/")
        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.next_check_at, now + datetime.timedelta(minutes=5))
        self.assertEqual(paused.checks.count(), 0)

    def test_prune_and_command(self):
        Check.objects.create(monitor=self.monitor, ok=True, created_at=timezone.now() - datetime.timedelta(days=200))
        Check.objects.create(monitor=self.monitor, ok=True)
        out = StringIO()
        with mock.patch("uptime.checker.probe", return_value=Result(ok=True, status_code=200, response_ms=10)):
            call_command("uptime_worker", "--once", stdout=out)
        self.assertIn("Checked 1 monitor(s), deleted 1 old check(s).", out.getvalue())

    def test_stats(self):
        now = timezone.now().replace(hour=12)
        for minutes, ok in ((10, True), (20, False), (30, True), (40, True)):
            Check.objects.create(monitor=self.monitor, ok=ok, response_ms=100 + minutes,
                                 created_at=now - datetime.timedelta(minutes=minutes))
        Check.objects.create(monitor=self.monitor, ok=True, response_ms=50, created_at=now - datetime.timedelta(days=3))
        report = stats.report(self.monitor, 1, now)
        self.assertEqual(report["uptime"], 75.0)
        self.assertEqual(report["checks"], 4)
        self.assertEqual(report["series"][-1]["hour"], now.hour)
        bars = stats.daily_bars([self.monitor.pk], 7, now)[self.monitor.pk]
        self.assertEqual(len(bars), 7)
        self.assertEqual(bars[-1]["level"], "down")  # 75%
        self.assertEqual(bars[-4]["level"], "up")
        self.assertEqual(bars[0]["level"], "none")
        self.assertEqual(stats.level(99.5), "degraded")


@override_settings(LANGUAGE_CODE="en")
class ViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("ana", "ana@example.com", "pass12345")
        self.viewer = User.objects.create_user("leo", "leo@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")
        self.project.analytics_domains = "shop.example, blog.example"
        self.project.save()
        ProjectMember.objects.create(project=self.project, user=self.viewer, role=ProjectMember.VIEWER)
        self.url = reverse("projects:uptime", args=["ana", self.project.slug])

    def test_create_edit_and_delete(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url), "shop.example")
        response = self.client.post(self.url, {"url": "status.example", "interval": "10", "notify": "on", "enabled": "on"})
        monitor = Monitor.objects.get(project=self.project)
        self.assertRedirects(response, monitor.get_absolute_url())
        self.assertEqual((monitor.url, monitor.interval, monitor.notify), ("https://status.example/", 10, True))

        duplicate = self.client.post(self.url, {"url": "https://status.example/", "interval": "5"})
        self.assertContains(duplicate, "already monitored")

        Check.objects.create(monitor=monitor, ok=True, response_ms=120)
        page = self.client.get(monitor.get_absolute_url() + "?days=7")
        self.assertContains(page, "status.example")
        self.assertContains(page, "analytics-series")

        self.client.post(monitor.get_absolute_url(), {"action": "update", "url": "https://status.example/", "interval": "60"})
        monitor.refresh_from_db()
        self.assertEqual((monitor.interval, monitor.notify, monitor.enabled), (60, False, False))

        self.client.post(monitor.get_absolute_url(), {"action": "delete"})
        self.assertFalse(Monitor.objects.exists())

    def test_add_analytics_domains(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("uptime"), {"action": "add_domains"})
        self.assertEqual(sorted(self.project.monitors.values_list("url", flat=True)),
                         ["https://blog.example/", "https://shop.example/"])
        overview = self.client.get(reverse("uptime"))
        self.assertContains(overview, "blog.example")
        self.assertNotContains(overview, "without a monitor")

    def test_viewer_is_read_only_and_strangers_see_nothing(self):
        monitor = Monitor.objects.create(project=self.project, url="https://shop.example/")
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(monitor.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.post(monitor.get_absolute_url(), {"action": "delete"}).status_code, 403)
        self.assertNotContains(self.client.get(reverse("uptime")), "without a monitor")

        stranger = get_user_model().objects.create_user("eva", "eva@example.com", "pass12345")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(monitor.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("uptime")), "shop.example")

    def test_check_all_now(self):
        Monitor.objects.create(project=self.project, url="https://shop.example/")
        Monitor.objects.create(project=self.project, url="https://blog.example/")
        Monitor.objects.create(project=self.project, url="https://old.example/", enabled=False)
        results = {"https://shop.example/": Result(ok=True, status_code=200, response_ms=50),
                   "https://blog.example/": Result(ok=False, error="HTTP 500")}
        self.client.force_login(self.owner)
        with mock.patch("uptime.checker.MAX_PARALLEL", 1), mock.patch("uptime.checker.probe", side_effect=results.get):
            response = self.client.post(reverse("uptime"), {"action": "check_all"}, follow=True)
        self.assertContains(response, "2 monitors checked: 1 up, 1 down.")
        self.assertEqual(Check.objects.count(), 2)
        self.assertGreater(Monitor.objects.get(url="https://shop.example/").next_check_at, timezone.now())

        self.client.force_login(self.viewer)  # viewers can't trigger checks
        self.assertNotContains(self.client.get(reverse("uptime")), "check_all")
        self.client.post(reverse("uptime"), {"action": "check_all"})
        self.assertEqual(Check.objects.count(), 2)

    def test_check_now(self):
        monitor = Monitor.objects.create(project=self.project, url="https://shop.example/")
        self.client.force_login(self.owner)
        with mock.patch("uptime.checker.probe", return_value=Result(ok=False, error="HTTP 502 Bad Gateway")):
            response = self.client.post(monitor.get_absolute_url(), {"action": "check"}, follow=True)
        self.assertContains(response, "HTTP 502 Bad Gateway")
        self.assertEqual(len(mail.outbox), 1)
