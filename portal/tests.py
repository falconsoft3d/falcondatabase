from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects import schema, services
from projects.models import ProjectTable, ProjectUser


class PortalTestCase(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")
        self.products = services.create_table(self.project, "products", [
            {"name": "name", "type_": "text", "required": True}, {"name": "price", "type_": "decimal"},
        ])
        self.notes = services.create_table(self.project, "notes", [{"name": "text", "type_": "text"}],
                                           access=ProjectTable.OWNER)
        self.secret = services.create_table(self.project, "secret", [{"name": "v", "type_": "text"}])
        self.secret.portal_mode = ProjectTable.PORTAL_HIDDEN
        self.secret.save()
        self.products.portal_mode = ProjectTable.PORTAL_EDIT
        self.products.save()
        self.notes.portal_mode = ProjectTable.PORTAL_EDIT
        self.notes.save()
        self.project.portal_enabled = True
        self.project.portal_slug = "proyecto1"
        self.project.save()
        schema.insert_row(self.project.schema, "products", {"name": "Coffee", "price": "2.5"})
        schema.insert_row(self.project.schema, "products", {"name": "Tea", "price": "3"})
        self.eva = self.app_user("eva@example.com")
        self.bob = self.app_user("bob@example.com")

    def app_user(self, email):
        user = ProjectUser(project=self.project, email=email)
        user.set_password("secret1")
        user.save()
        return user

    def url(self, name, *args):
        return reverse(f"portal:{name}", args=["ana", "proyecto1", *args])

    def login(self, email="eva@example.com", password="secret1"):
        return self.client.post(self.url("login"), {"email": email, "password": password})


class PortalSettingsTests(PortalTestCase):
    def test_owner_configures_portal(self):
        self.client.force_login(self.owner)
        url = self.project.url("portal")
        for bad in ["A", "ab", "x y", "-bad-"]:
            response = self.client.post(url, {"portal_enabled": "on", "portal_slug": bad})
            self.assertEqual(response.status_code, 200, bad)
            self.assertTrue(response.context["error"])
        other = services.create_project(self.owner, "Other")
        response = self.client.post(other.url("portal"), {"portal_enabled": "on", "portal_slug": "proyecto1"})
        self.assertTrue(response.context["error"])

        response = self.client.post(url, {"portal_enabled": "on", "portal_slug": "mi-tienda", "portal_public": "on",
                                          "mode-products": "view", "mode-secret": "edit"})
        self.assertRedirects(response, url)
        self.project.refresh_from_db()
        self.assertEqual((self.project.portal_slug, self.project.portal_public), ("mi-tienda", True))
        self.assertEqual(self.project.tables.get(name="secret").portal_mode, "edit")

    def test_address_is_per_user(self):
        self.assertEqual(self.url("home"), "/app/ana/proyecto1/")
        bob = get_user_model().objects.create_user("bob", "bob@example.com", "pass12345")
        bob_project = services.create_project(bob, "Shop")
        self.client.force_login(bob)
        response = self.client.post(bob_project.url("portal"), {"portal_enabled": "on", "portal_slug": "proyecto1"})
        self.assertRedirects(response, bob_project.url("portal"))
        self.assertEqual(self.client.get("/app/bob/proyecto1/").status_code, 302)  # private: asks to sign in
        self.assertEqual(self.client.get("/app/nobody/proyecto1/").status_code, 404)

    def test_disabled_portal(self):
        self.project.portal_enabled = False
        self.project.save()
        self.assertEqual(self.client.get(self.url("home")).status_code, 404)


class PortalAccessTests(PortalTestCase):
    def test_private_portal_requires_login(self):
        response = self.client.get(self.url("table", "products"))
        self.assertRedirects(response, f"{self.url('login')}?next={self.url('table', 'products')}")
        self.assertEqual(self.login(password="wrong").status_code, 200)
        self.assertRedirects(self.login(), self.url("home"))
        home = self.client.get(self.url("home"))
        names = [t.name for t in home.context["table_list"]]
        self.assertEqual(names, ["notes", "products"])  # "secret" is hidden
        self.assertEqual(self.client.get(self.url("table", "secret")).status_code, 404)

    def test_portal_session_does_not_open_dashboard(self):
        self.login()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_public_portal(self):
        self.project.portal_public = True
        self.project.save()
        response = self.client.get(self.url("table", "products"))
        self.assertContains(response, "Coffee")
        self.assertFalse(response.context["editable"])
        self.assertEqual(self.client.get(self.url("row_new", "products")).status_code, 302)
        self.assertEqual(self.client.get(self.url("table", "notes")).status_code, 302)  # Owner table

    def test_signup(self):
        response = self.client.post(self.url("signup"), {"email": "new@example.com", "password": "secret1"})
        self.assertRedirects(response, self.url("home"))
        self.assertTrue(self.project.users.filter(email="new@example.com").exists())
        self.project.allow_signup = False
        self.project.save()
        self.assertEqual(self.client.get(self.url("signup")).status_code, 404)


class PortalEditingTests(PortalTestCase):
    def test_create_update_delete(self):
        self.login()
        response = self.client.post(self.url("row_new", "products"), {"name": "Cake", "price": "4.5"})
        self.assertRedirects(response, self.url("table", "products"))
        cake = schema.select_rows(self.project.schema, "products", self.products.columns(),
                                  [("name", "eq", "Cake")])[0][0]
        self.client.post(self.url("row", "products", cake["id"]), {"name": "Cheesecake", "price": "5"})
        self.assertEqual(schema.get_row(self.project.schema, "products", cake["id"])["name"], "Cheesecake")
        self.client.post(self.url("row_delete", "products", cake["id"]))
        self.assertIsNone(schema.get_row(self.project.schema, "products", cake["id"]))

    def test_view_only_table(self):
        self.products.portal_mode = ProjectTable.PORTAL_VIEW
        self.products.save()
        self.login()
        response = self.client.get(self.url("row", "products", 1))
        self.assertTemplateUsed(response, "portal/detail.html")
        self.client.post(self.url("row", "products", 1), {"name": "Hacked"})
        self.assertEqual(schema.get_row(self.project.schema, "products", 1)["name"], "Coffee")
        self.assertEqual(self.client.post(self.url("row_delete", "products", 1)).status_code, 404)

    def test_owner_rows_are_private(self):
        self.login()
        self.client.post(self.url("row_new", "notes"), {"text": "eva's note"})
        note = schema.select_rows(self.project.schema, "notes", self.notes.columns())[0][0]
        self.assertEqual(note["owner_id"], self.eva.pk)

        self.client.post(self.url("logout"))
        self.login("bob@example.com")
        response = self.client.get(self.url("table", "notes"))
        self.assertEqual(response.context["total"], 0)
        self.assertEqual(self.client.get(self.url("row", "notes", note["id"])).status_code, 404)

    def test_search_and_order(self):
        self.login()
        response = self.client.get(self.url("table", "products") + "?q=tea")
        self.assertEqual([r["name"] for r in response.context["rows"]], ["Tea"])
        response = self.client.get(self.url("table", "products") + "?order=name")
        self.assertEqual([r["name"] for r in response.context["rows"]], ["Coffee", "Tea"])
        response = self.client.get(self.url("table", "products") + "?q=100%25")
        self.assertEqual(response.context["total"], 0)
