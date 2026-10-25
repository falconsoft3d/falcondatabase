import base64
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import totp
from .models import SiteSettings, TwoFactor


def make_user(username, password="pass12345", **extra):
    return get_user_model().objects.create_user(username, f"{username}@example.com", password, **extra)


class TotpTests(TestCase):
    # RFC 6238, appendix B (SHA-1), truncated to 6 digits.
    SECRET = base64.b32encode(b"12345678901234567890").decode()

    def test_rfc_vectors(self):
        for now, code in [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037")]:
            self.assertEqual(totp.matching_counter(self.SECRET, code, now=now, window=0), now // 30)

    def test_rejects_wrong_or_old_codes(self):
        self.assertIsNone(totp.matching_counter(self.SECRET, "000000", now=59))
        self.assertIsNone(totp.matching_counter(self.SECRET, "abc", now=59))
        self.assertIsNone(totp.matching_counter(self.SECRET, "287082", now=59 + 30 * 3))


class AdminUsersTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", is_superuser=True, is_staff=True)
        self.regular = make_user("ana")

    def test_only_admin_sees_users(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse("users")).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("users"))
        self.assertContains(response, "ana@example.com")

    def test_admin_creates_regular_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("users"), {
            "action": "create", "username": "luis", "email": "luis@example.com",
            "password1": "un-pass-largo-123", "password2": "un-pass-largo-123",
        })
        self.assertRedirects(response, reverse("users"))
        luis = get_user_model().objects.get(username="luis")
        self.assertFalse(luis.is_superuser)

    def test_admin_disables_signup(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("users"), {"action": "signup"})
        self.assertFalse(SiteSettings.load().allow_signup)

        self.client.logout()
        response = self.client.get(reverse("signup"))
        self.assertRedirects(response, reverse("login"))
        response = self.client.post(reverse("signup"), {
            "username": "x", "email": "x@example.com", "password1": "un-pass-largo-123", "password2": "un-pass-largo-123",
        })
        self.assertFalse(get_user_model().objects.filter(username="x").exists())
        self.assertNotContains(self.client.get(reverse("home")), reverse("signup"))

        # The admin can still create accounts.
        self.client.force_login(self.admin)
        self.client.post(reverse("users"), {
            "action": "create", "username": "eva", "email": "eva@example.com",
            "password1": "un-pass-largo-123", "password2": "un-pass-largo-123",
        })
        self.assertTrue(get_user_model().objects.filter(username="eva").exists())

    def test_setadmin_keeps_a_single_admin(self):
        call_command("setadmin", "ana", stdout=StringIO())
        admins = list(get_user_model().objects.filter(is_superuser=True).values_list("username", flat=True))
        self.assertEqual(admins, ["ana"])

    def test_admin_resets_two_factor(self):
        TwoFactor.objects.create(user=self.regular, secret=totp.generate_secret())
        self.client.force_login(self.admin)
        self.client.post(reverse("users"), {"action": "reset_2fa", "user": self.regular.pk})
        self.assertFalse(TwoFactor.objects.filter(user=self.regular).exists())


class TwoFactorTests(TestCase):
    def setUp(self):
        self.user = make_user("ana")

    def code_for(self, secret, offset=0):
        return totp._code(secret, totp.current_counter() + offset)

    def enable(self):
        self.client.force_login(self.user)
        self.client.get(reverse("two_factor_setup"))
        secret = self.client.session["falcondb_2fa_setup"]
        response = self.client.post(reverse("two_factor_setup"), {"code": "000000"})
        self.assertFalse(TwoFactor.objects.filter(user=self.user).exists())
        response = self.client.post(reverse("two_factor_setup"), {"code": self.code_for(secret)})
        self.assertEqual(len(response.context["codes"]), TwoFactor.RECOVERY_CODES)
        self.client.logout()
        return secret, response.context["codes"]

    def login_password(self):
        return self.client.post(reverse("login"), {"username": "ana", "password": "pass12345"})

    def test_login_requires_code(self):
        secret, _codes = self.enable()
        response = self.login_password()
        self.assertRedirects(response, reverse("login_verify"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)  # not signed in yet

        self.client.post(reverse("login_verify"), {"code": "000000"})
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

        # Next time step, so the code used during setup can't be replayed.
        with mock.patch("core.totp.time.time", return_value=(totp.current_counter() + 1) * 30):
            response = self.client.post(reverse("login_verify"), {"code": self.code_for(secret, 1)})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_code_cannot_be_reused(self):
        secret, _codes = self.enable()
        # The setup already used the current code.
        self.login_password()
        self.client.post(reverse("login_verify"), {"code": self.code_for(secret)})
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_recovery_code_works_once(self):
        _secret, codes = self.enable()
        self.login_password()
        response = self.client.post(reverse("login_verify"), {"code": codes[0]})
        self.assertRedirects(response, reverse("dashboard"))
        self.client.logout()
        self.login_password()
        self.client.post(reverse("login_verify"), {"code": codes[0]})
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_too_many_attempts(self):
        self.enable()
        self.login_password()
        for _ in range(5):
            response = self.client.post(reverse("login_verify"), {"code": "000000"})
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("falcondb_2fa_pending", self.client.session)

    def test_disable_requires_password(self):
        self.enable()
        self.client.force_login(self.user)
        self.client.post(reverse("two_factor_manage"), {"action": "disable", "password": "wrong"})
        self.assertTrue(TwoFactor.objects.filter(user=self.user).exists())
        self.client.post(reverse("two_factor_manage"), {"action": "disable", "password": "pass12345"})
        self.assertFalse(TwoFactor.objects.filter(user=self.user).exists())

    def test_new_recovery_codes(self):
        _secret, codes = self.enable()
        self.client.force_login(self.user)
        response = self.client.post(reverse("two_factor_manage"), {"action": "recovery", "password": "pass12345"})
        new_codes = response.context["codes"]
        self.assertEqual(len(set(new_codes) & set(codes)), 0)


class LanguageTests(TestCase):
    def test_switch_language(self):
        response = self.client.get(reverse("home"), headers={"Accept-Language": "es"})
        self.assertContains(response, "Empezar gratis")
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Start for free")
        self.assertContains(response, '<html lang="en">')

    def test_contact_in_footer(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Marlon Falcon Hernández")
        self.assertContains(response, "mailto:mfalconsoft@gmail.com")

    def test_api_errors_follow_accept_language(self):
        response = self.client.get("/api/v1/aaaaaaaaaaaaaaaaaaaa", headers={"Accept-Language": "en"})
        self.assertEqual(response.json()["error"], "Project not found.")
        response = self.client.get("/api/v1/aaaaaaaaaaaaaaaaaaaa", headers={"Accept-Language": "es"})
        self.assertEqual(response.json()["error"], "Proyecto no encontrado.")


class PasswordResetByAdminTests(TestCase):
    def test_admin_resets_password(self):
        admin = make_user("boss", is_superuser=True, is_staff=True)
        ana = make_user("ana")
        self.client.force_login(admin)
        response = self.client.post(reverse("users"), {"action": "reset_password", "user": ana.pk})
        temporary = response.context["password_reset"]["password"]
        self.assertContains(response, temporary)
        ana.refresh_from_db()
        self.assertTrue(ana.check_password(temporary))
        self.assertFalse(ana.check_password("pass12345"))
        # The admin keeps their own session.
        self.assertEqual(self.client.get(reverse("users")).status_code, 200)

    def test_regular_user_cannot_reset(self):
        ana, bob = make_user("ana"), make_user("bob")
        self.client.force_login(ana)
        self.client.post(reverse("users"), {"action": "reset_password", "user": bob.pk})
        bob.refresh_from_db()
        self.assertTrue(bob.check_password("pass12345"))


class SiteTests(TestCase):
    def test_cookie_banner_until_answered(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "data-cookie-banner ")
        self.assertNotContains(response, "data-cookie-banner hidden")
        self.client.cookies["falcondb_cookie_consent"] = "essential"
        self.assertContains(self.client.get(reverse("home")), "data-cookie-banner hidden")

    def test_cookie_policy_in_both_languages(self):
        self.assertContains(self.client.get(reverse("cookies"), headers={"Accept-Language": "en"}), "Cookie policy")
        self.assertContains(self.client.get(reverse("cookies"), headers={"Accept-Language": "es"}), "Política de cookies")

    def test_home_link_in_menu(self):
        user = make_user("ana")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"), headers={"Accept-Language": "en"})
        self.assertContains(response, ">Home</a>")

    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})

    def test_ensureadmin(self):
        make_user("old-admin", is_superuser=True)
        env = {"FALCONDB_ADMIN_USERNAME": "marlon", "FALCONDB_ADMIN_EMAIL": "m@example.com",
               "FALCONDB_ADMIN_PASSWORD": "secret-pass-123"}
        with mock.patch.dict("os.environ", env):
            call_command("ensureadmin", stdout=StringIO())
            call_command("ensureadmin", stdout=StringIO())  # idempotent
        admins = list(get_user_model().objects.filter(is_superuser=True).values_list("username", flat=True))
        self.assertEqual(admins, ["marlon"])
        self.assertTrue(get_user_model().objects.get(username="marlon").check_password("secret-pass-123"))
