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
        from core.changelog import VERSION
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok", "version": VERSION})

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


class AvatarTests(TestCase):
    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)

    def image_file(self, fmt="PNG", size=(600, 400)):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", size, (237, 99, 125)).save(buffer, fmt)
        return SimpleUploadedFile(f"me.{fmt.lower()}", buffer.getvalue(), content_type=f"image/{fmt.lower()}")

    def test_upload_resize_serve_and_remove(self):
        from io import BytesIO

        from PIL import Image

        self.client.post(reverse("account"), {"action": "avatar", "avatar": self.image_file()})
        response = self.client.get(reverse("avatar", args=[self.user.pk]))
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertEqual(Image.open(BytesIO(response.content)).size, (256, 256))
        self.assertContains(self.client.get(reverse("dashboard")), f'src="/avatars/{self.user.pk}/?v=')

        self.client.post(reverse("account"), {"action": "avatar_delete"})
        self.assertEqual(self.client.get(reverse("avatar", args=[self.user.pk])).status_code, 404)

    def test_rejects_non_images(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        response = self.client.post(reverse("account"), {"action": "avatar", "avatar": fake}, follow=True)
        self.assertContains(response, "flash-error")
        self.assertEqual(self.client.get(reverse("avatar", args=[self.user.pk])).status_code, 404)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("avatar", args=[self.user.pk])).status_code, 302)


class ChangelogTests(TestCase):
    def test_versions_page_and_footer(self):
        from core.changelog import RELEASES, VERSION

        self.assertEqual(VERSION, RELEASES[0]["version"])
        response = self.client.get(reverse("changelog"), headers={"Accept-Language": "en"})
        self.assertContains(response, f"v{VERSION}")
        for release in RELEASES:
            self.assertContains(response, release["title"]["en"])
        spanish = self.client.get(reverse("changelog"), headers={"Accept-Language": "es"})
        self.assertContains(spanish, RELEASES[0]["title"]["es"])
        self.assertContains(self.client.get(reverse("home")), f'v{VERSION}</a>')

    def test_every_release_is_bilingual(self):
        from core.changelog import RELEASES

        for release in RELEASES:
            self.assertTrue(release["title"]["en"] and release["title"]["es"])
            for kind, en, es in release["changes"]:
                self.assertIn(kind, ("added", "improved", "fixed"))
                self.assertTrue(en and es)


class AccountApiTests(TestCase):
    def setUp(self):
        self.user = make_user("ana")

    def token(self, **extra):
        body = {"username": "ana", "password": "pass12345", **extra}
        return self.client.post(reverse("account_token"), body, content_type="application/json")

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_token_and_analytics(self):
        from projects import services

        self.assertEqual(self.client.post(reverse("account_token"), {"username": "ana", "password": "x"},
                                          content_type="application/json").status_code, 401)
        response = self.token()
        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        self.assertEqual(response.json()["user"]["username"], "ana")

        services.create_project(self.user, "Shop")
        other = make_user("bob")
        services.create_project(other, "Secret")
        data = self.client.get(reverse("account_analytics") + "?days=7", headers=self.auth(token)).json()
        self.assertEqual([p["name"] for p in data["projects"]], ["Shop"])
        self.assertEqual(len(data["report"]["series"]), 7)
        self.assertIn("today", data)

        self.assertEqual(self.client.get(reverse("account_me")).status_code, 401)
        self.assertEqual(self.client.get(reverse("account_me"), headers=self.auth("bad")).status_code, 401)

    def test_password_change_revokes_token(self):
        token = self.token().json()["token"]
        self.assertEqual(self.client.get(reverse("account_me"), headers=self.auth(token)).status_code, 200)
        self.user.set_password("new-pass-987")
        self.user.save()
        self.assertEqual(self.client.get(reverse("account_me"), headers=self.auth(token)).status_code, 401)

    def test_two_factor_required(self):
        device = TwoFactor.objects.create(user=self.user, secret=totp.generate_secret())
        response = self.token()
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()["two_factor_required"])
        self.assertEqual(self.token(code="000000").status_code, 401)
        code = totp._code(device.secret, totp.current_counter())
        self.assertEqual(self.token(code=code).status_code, 200)

    def test_extension_download_is_preconfigured(self):
        import io
        import json
        import zipfile

        self.assertContains(self.client.get(reverse("extension")), reverse("extension_zip"))
        response = self.client.get(reverse("extension_zip"))
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        names = archive.namelist()
        self.assertIn("falcondatabase-extension/manifest.json", names)
        self.assertIn("falcondatabase-extension/icons/icon-128.png", names)
        manifest = json.loads(archive.read("falcondatabase-extension/manifest.json"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["host_permissions"], ["http://testserver/*"])
        config = archive.read("falcondatabase-extension/config.js").decode()
        self.assertIn('DEFAULT_SERVER = "http://testserver"', config)
        self.assertContains(self.client.get(reverse("home")), reverse("extension"))
