import datetime
import json
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from projects import services

from . import stats, tracking
from .models import PageView

CHROME_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0 Safari/537.36")
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


class ClassificationTests(TestCase):
    def test_sources(self):
        q = {}
        self.assertEqual(tracking.classify_source("", "shop.com", q)[:2], ("Direct", "direct"))
        self.assertEqual(tracking.classify_source("https://www.google.es/", "shop.com", q)[:2], ("Google", "organic"))
        self.assertEqual(tracking.classify_source("https://l.facebook.com/x", "shop.com", q)[:2], ("Facebook", "social"))
        self.assertEqual(tracking.classify_source("https://news.ycombinator.com/", "shop.com", q)[:2],
                         ("news.ycombinator.com", "referral"))
        self.assertEqual(tracking.classify_source("https://shop.com/a", "shop.com", q)[:2], ("Direct", "direct"))
        utm = {"utm_source": ["newsletter"], "utm_medium": ["Email"], "utm_campaign": ["launch"]}
        self.assertEqual(tracking.classify_source("", "shop.com", utm)[:3], ("newsletter", "email", "launch"))

    def test_user_agents(self):
        self.assertEqual((tracking.device_for(CHROME_MAC), tracking.browser_for(CHROME_MAC), tracking.os_for(CHROME_MAC)),
                         ("desktop", "Chrome", "macOS"))
        self.assertEqual((tracking.device_for(SAFARI_IPHONE), tracking.browser_for(SAFARI_IPHONE),
                          tracking.os_for(SAFARI_IPHONE)), ("mobile", "Safari", "iOS"))
        self.assertTrue(tracking.is_bot("Googlebot/2.1"))
        self.assertTrue(tracking.is_bot(""))

    def test_country(self):
        factory = RequestFactory()
        self.assertEqual(tracking.country_for(factory.get("/", HTTP_CF_IPCOUNTRY="cl"), "Europe/Madrid"), "CL")
        self.assertEqual(tracking.country_for(factory.get("/"), "Europe/Madrid"), "ES")
        self.assertEqual(tracking.country_for(factory.get("/"), "Asia/Calcutta"), "IN")  # old alias
        self.assertEqual(tracking.country_for(factory.get("/", HTTP_ACCEPT_LANGUAGE="es-MX,es;q=0.9"), "UTC"), "MX")
        self.assertEqual(tracking.country_for(factory.get("/"), ""), "")


class CollectTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")
        self.project.analytics_enabled = True
        self.project.save()
        self.url = reverse("analytics_collect", args=[self.project.ref])

    def hit(self, url="https://shop.com/", referrer="", ua=CHROME_MAC, **extra):
        body = json.dumps({"u": url, "r": referrer, "tz": "Europe/Madrid"})
        return self.client.post(self.url, body, content_type="text/plain", headers={"User-Agent": ua}, **extra)

    def test_records_pageviews_and_sessions(self):
        self.assertEqual(self.hit("https://shop.com/?utm_source=x&utm_medium=cpc", "https://google.com").status_code, 202)
        self.hit("https://shop.com/pricing?ref=1", "https://shop.com/")
        views = list(PageView.objects.order_by("id"))
        self.assertEqual(len(views), 2)
        self.assertEqual(views[0].session, views[1].session)
        self.assertEqual((views[1].source, views[1].medium), ("x", "cpc"))  # inherited from the session
        self.assertEqual((views[1].path, views[1].country, views[1].device), ("/pricing", "ES", "desktop"))
        self.assertNotIn("ref=1", views[1].path)

    def test_new_session_after_30_minutes(self):
        self.hit()
        PageView.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=31))
        self.hit()
        self.assertEqual(PageView.objects.values("session").distinct().count(), 2)

    def test_ignored_hits(self):
        self.hit(ua="Googlebot/2.1 (+http://www.google.com/bot.html)")
        self.hit(url="javascript:alert(1)")
        self.assertEqual(self.client.post(self.url, "not json", content_type="text/plain").status_code, 400)
        self.project.analytics_domains = "shop.com"
        self.project.save()
        self.hit(url="https://evil.com/")
        self.hit(url="https://blog.shop.com/")
        self.assertEqual(list(PageView.objects.values_list("hostname", flat=True)), ["blog.shop.com"])

    def test_disabled_project(self):
        self.project.analytics_enabled = False
        self.project.save()
        self.assertEqual(self.hit().status_code, 404)

    def test_script_has_cors(self):
        response = self.client.get(reverse("analytics_script"), headers={"Origin": "https://shop.com"})
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertIn(b"sendBeacon", response.content)


class StatsTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(owner, "Shop")

    def add(self, session, visitor, path="/", days_ago=0, **fields):
        defaults = dict(hostname="shop.com", source="Direct", medium="direct", device="desktop",
                        browser="Chrome", os="macOS", country="ES")
        return PageView.objects.create(project=self.project, session=session, visitor=visitor, path=path,
                                       created_at=timezone.now() - datetime.timedelta(days=days_ago),
                                       **{**defaults, **fields})

    def test_report(self):
        self.add("s1", "v1", "/")
        self.add("s1", "v1", "/pricing")
        self.add("s2", "v2", "/", medium="organic", source="Google", country="US")
        self.add("s3", "v3", "/", days_ago=8)  # previous period for a 7-day window
        report = stats.report(PageView.objects.all(), 7)
        totals = report["totals"]
        self.assertEqual((totals["visitors"], totals["sessions"], totals["pageviews"]), (2, 2, 3))
        self.assertEqual(totals["bounce_rate"], 50)
        self.assertEqual(totals["views_per_session"], 1.5)
        kpis = {k["key"]: k for k in report["kpis"]}
        self.assertEqual(kpis["sessions"]["change"], 100)  # 2 vs 1
        self.assertEqual(len(report["series"]), 7)
        self.assertEqual(report["series"][-1]["pageviews"], 3)
        self.assertEqual(report["pages"][0]["path"], "/")
        self.assertEqual({r["medium"] for r in report["mediums"]}, {"direct", "organic"})
        self.assertEqual(report["countries"][0]["width"], 100)

    def test_today_is_hourly_and_compares_with_yesterday(self):
        self.add("s1", "v1", "/")
        self.add("s2", "v2", "/")
        self.add("s0", "v0", "/", days_ago=1)
        report = stats.report(PageView.objects.all(), 1)
        now = timezone.now()
        self.assertEqual(len(report["series"]), now.hour + 1)
        self.assertEqual(report["series"][-1]["hour"], now.hour)
        self.assertEqual(report["series"][-1]["pageviews"], 2)
        self.assertEqual(sum(p["pageviews"] for p in report["series"]), 2)
        kpis = {k["key"]: k for k in report["kpis"]}
        self.assertEqual(kpis["sessions"]["change"], 100)  # 2 today vs 1 yesterday

    def test_parse_period(self):
        self.assertEqual(stats.parse_period("1"), 1)
        self.assertEqual(stats.parse_period("30"), 30)
        self.assertEqual(stats.parse_period("5"), stats.DEFAULT_PERIOD)
        self.assertEqual(stats.parse_period(None), stats.DEFAULT_PERIOD)


class DashboardTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.shop = services.create_project(self.owner, "Shop")
        self.blog = services.create_project(self.owner, "Blog")
        call_command("seed_analytics", self.shop.ref, days=10, sessions=5, seed=1, stdout=StringIO())
        call_command("seed_analytics", f"ana/{self.blog.slug}", days=10, sessions=3, seed=2,
                     host="blog.example.com", stdout=StringIO())
        self.client.force_login(self.owner)

    def test_enable_from_tab(self):
        other = services.create_project(self.owner, "New")
        self.client.post(other.url("analytics"), {"analytics_enabled": "on", "analytics_domains": "a.com,\nB.com"})
        other.refresh_from_db()
        self.assertTrue(other.analytics_enabled)
        self.assertEqual(other.analytics_domains, "a.com, b.com")
        response = self.client.get(other.url("analytics"))
        self.assertContains(response, f'data-project="{other.ref}"')

    def test_project_tab(self):
        response = self.client.get(self.shop.url("analytics") + "?days=30")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["report"]["days"], 30)
        self.assertGreater(response.context["report"]["totals"]["pageviews"], 0)
        self.assertContains(response, 'id="analytics-series"')

    def test_overview_all_or_selected(self):
        everything = self.client.get(reverse("analytics")).context["report"]
        only_blog = self.client.get(reverse("analytics") + f"?p={self.blog.ref}").context["report"]
        self.assertGreater(everything["totals"]["pageviews"], only_blog["totals"]["pageviews"])
        self.assertEqual({r["project__name"] for r in only_blog["projects"]}, {"Blog"})

    def test_only_owner(self):
        other = get_user_model().objects.create_user("bob", "bob@example.com", "pass12345")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.shop.url("analytics")).status_code, 404)
        self.assertEqual(self.client.get(reverse("analytics")).context["report"]["totals"]["pageviews"], 0)


class OverviewSelectionTests(TestCase):
    def test_single_project_stays_checked(self):
        owner = get_user_model().objects.create_user("solo", "solo@example.com", "pass12345")
        project = services.create_project(owner, "Demo")
        self.client.force_login(owner)
        response = self.client.get(reverse("analytics") + f"?days=7&p={project.ref}")
        self.assertEqual(response.context["chosen"], {project.ref})
        self.assertFalse(response.context["all_selected"])
        self.assertContains(response, f'value="{project.ref}" checked')
        everything = self.client.get(reverse("analytics"))
        self.assertTrue(everything.context["all_selected"])
        self.assertNotContains(everything, f'value="{project.ref}" checked')


class SiteAnalyticsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("boss", "boss@example.com", "pass12345",
                                                          is_superuser=True, is_staff=True)

    def test_admin_enables_site_tracking(self):
        from core.models import SiteSettings

        home = self.client.get(reverse("home"))
        self.assertNotContains(home, 'src="/a.js"')

        self.client.force_login(self.admin)
        self.client.post(reverse("users"), {"action": "site_analytics", "enabled": "on"})
        site = SiteSettings.load()
        project = site.analytics_project
        self.assertEqual((project.owner, project.analytics_enabled, project.analytics_domains), (self.admin, True, "testserver"))

        self.client.logout()
        home = self.client.get(reverse("home"))
        self.assertContains(home, f'data-project="{project.ref}" src="/a.js"')
        self.assertContains(self.client.get(reverse("blog:index")), 'src="/a.js"')

        # Dashboards are never measured.
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("dashboard")), 'src="/a.js"')
        self.assertIn(project.slug, [p.slug for p in self.client.get(reverse("analytics")).context["projects"]])

        self.client.post(reverse("users"), {"action": "site_analytics"})
        project.refresh_from_db()
        self.assertFalse(project.analytics_enabled)
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("home")), 'src="/a.js"')

    def test_only_admin(self):
        user = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.client.force_login(user)
        self.assertEqual(self.client.post(reverse("users"), {"action": "site_analytics", "enabled": "on"}).status_code, 403)
