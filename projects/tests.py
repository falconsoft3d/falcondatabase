from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import schema, services
from .models import ProjectTable


class SchemaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.user, "Mi App")

    def create_products(self, **kwargs):
        return services.create_table(self.project, "productos", [
            {"name": "nombre", "type_": "text", "required": True},
            {"name": "precio", "type_": "decimal", "default": "0"},
            {"name": "activo", "type_": "boolean", "default": "true"},
            {"name": "extra", "type_": "json"},
            {"name": "codigo", "type_": "uuid", "default": "uuid()", "unique": True},
        ], **kwargs)

    def test_project_gets_its_own_schema(self):
        self.assertEqual(self.project.slug, "mi-app")
        rows = schema._execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", [self.project.schema])
        self.assertEqual(len(rows), 1)

    def test_create_table_and_introspect_columns(self):
        table = self.create_products()
        columns = {c.name: c for c in table.columns()}
        self.assertEqual(list(columns), ["id", "created_at", "nombre", "precio", "activo", "extra", "codigo"])
        self.assertTrue(columns["id"].primary_key)
        self.assertEqual(columns["precio"].type, "decimal")
        self.assertFalse(columns["nombre"].nullable)
        self.assertTrue(columns["codigo"].unique)

    def test_row_crud(self):
        table = self.create_products()
        row = schema.insert_row(self.project.schema, table.name, {"nombre": "Café", "extra": {"origen": "CO"}})
        self.assertEqual(row["precio"], 0)
        self.assertTrue(row["activo"])
        self.assertEqual(row["extra"], {"origen": "CO"})
        self.assertIsNotNone(row["codigo"])

        updated = schema.update_row(self.project.schema, table.name, row["id"], {"precio": "2.50"})
        self.assertEqual(str(updated["precio"]), "2.50")
        self.assertTrue(schema.delete_row(self.project.schema, table.name, row["id"]))
        self.assertEqual(table.row_count(), 0)

    def test_invalid_identifiers_are_rejected(self):
        for name in ["Productos", "1tabla", "drop table x;--", "a-b", ""]:
            with self.assertRaises(schema.SchemaError):
                services.create_table(self.project, name, [])
        with self.assertRaises(schema.SchemaError):
            services.create_table(self.project, "t", [{"name": "id", "type_": "text"}])
        with self.assertRaises(schema.SchemaError):
            services.create_table(self.project, "t", [{"name": "x", "type_": "money"}])

    def test_owner_policy_adds_owner_column(self):
        table = self.create_products()
        services.set_access(table, ProjectTable.OWNER)
        self.assertIn(schema.OWNER_COLUMN, [c.name for c in table.columns()])

    def test_add_and_drop_column(self):
        table = self.create_products()
        services.add_column(table, name="stock", type_="integer", default="5", required=True)
        self.assertIn("stock", [c.name for c in table.columns()])
        services.drop_column(table, "stock")
        self.assertNotIn("stock", [c.name for c in table.columns()])
        with self.assertRaises(schema.SchemaError):
            services.drop_column(table, "id")

    def test_delete_project_drops_schema(self):
        self.create_products()
        name = self.project.schema
        services.delete_project(self.project)
        self.assertEqual(schema._execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", [name]), [])


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.client.force_login(self.user)

    def test_signup_and_login_with_email(self):
        self.client.logout()
        response = self.client.post(reverse("signup"), {
            "username": "luis", "email": "luis@example.com",
            "password1": "un-pass-largo-123", "password2": "un-pass-largo-123",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.client.logout()
        self.assertTrue(self.client.login(username="luis@example.com", password="un-pass-largo-123"))

    def test_change_password(self):
        url = reverse("account")
        response = self.client.post(url, {
            "old_password": "incorrecta", "new_password1": "nueva-clave-987", "new_password2": "nueva-clave-987",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.login(username="ana", password="pass12345"))

        response = self.client.post(url, {
            "old_password": "pass12345", "new_password1": "nueva-clave-987", "new_password2": "nueva-clave-987",
        })
        self.assertRedirects(response, url)
        # The session survives the change.
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.client.logout()
        self.assertFalse(self.client.login(username="ana", password="pass12345"))
        self.assertTrue(self.client.login(username="ana", password="nueva-clave-987"))

    def test_change_password_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("account"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('account')}")

    def test_reserved_username(self):
        self.client.logout()
        response = self.client.post(reverse("signup"), {
            "username": "dashboard", "email": "x@example.com", "password1": "un-pass-largo-123",
            "password2": "un-pass-largo-123",
        })
        self.assertContains(response, "reservado")

    def test_full_flow(self):
        response = self.client.post(reverse("project_new"), {"name": "Tienda", "description": "demo"})
        project = self.user.projects.get()
        self.assertRedirects(response, project.get_absolute_url())

        response = self.client.post(project.url("table_new"), {
            "name": "clientes", "access": "public",
            "columns-0-name": "nombre", "columns-0-type": "text", "columns-0-required": "on",
            "columns-1-name": "edad", "columns-1-type": "integer",
        })
        self.assertRedirects(response, project.url("table", "clientes"))

        response = self.client.post(project.url("table", "clientes"), {"nombre": "Eva", "edad": "30"})
        self.assertRedirects(response, project.url("table", "clientes"))
        response = self.client.get(project.url("table", "clientes"))
        self.assertContains(response, "Eva")

        row_id = schema.select_rows(project.schema, "clientes", project.tables.get().columns())[0][0]["id"]
        response = self.client.post(project.url("row_edit", "clientes", row_id), {"nombre": "Eva M", "edad": ""})
        self.assertRedirects(response, project.url("table", "clientes"))
        row = schema.get_row(project.schema, "clientes", row_id)
        self.assertEqual((row["nombre"], row["edad"]), ("Eva M", None))

        for name in ["overview", "tables", "auth", "api", "settings"]:
            self.assertEqual(self.client.get(project.url(name)).status_code, 200, name)
        for name in ["table_structure", "table_api"]:
            self.assertEqual(self.client.get(project.url(name, "clientes")).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_insert_error_is_reported(self):
        project = services.create_project(self.user, "P")
        services.create_table(project, "t", [{"name": "n", "type_": "integer", "required": True}])
        response = self.client.post(project.url("table", "t"), {"n": ""}, follow=True)
        self.assertContains(response, "null value")

    def test_other_users_cannot_see_project(self):
        project = services.create_project(self.user, "Privado")
        other = get_user_model().objects.create_user("bob", "bob@example.com", "pass12345")
        self.client.force_login(other)
        self.assertEqual(self.client.get(project.get_absolute_url()).status_code, 404)
