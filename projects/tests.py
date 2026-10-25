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


class TransferTests(TestCase):
    def setUp(self):
        from .models import ProjectUser

        self.user = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.user, "Shop", "My shop")
        self.project.auth_enabled = True
        self.project.save()
        table = services.create_table(self.project, "products", [
            {"name": "name", "type_": "text", "required": True, "unique": True},
            {"name": "price", "type_": "decimal", "default": "0"},
            {"name": "note", "type_": "text", "default": "it's new"},
            {"name": "added", "type_": "datetime", "default": "now()"},
            {"name": "code", "type_": "uuid", "default": "uuid()"},
            {"name": "meta", "type_": "json"},
        ], access=ProjectTable.OWNER, description="Catalog")
        app_user = ProjectUser.objects.create(project=self.project, email="u@x.com", password="x")
        schema.insert_row(self.project.schema, "products", {"name": "Tea", "price": "2.5", "meta": {"a": [1]},
                                                             "owner_id": app_user.pk})
        schema.insert_row(self.project.schema, "products", {"name": "Coffee"})
        schema.delete_row(self.project.schema, "products", 1)
        schema.insert_row(self.project.schema, "products", {"name": "Cake"})
        self.table = table

    def export(self, data):
        import json

        response = self.client.get(self.project.url("export") + ("?data=1" if data else ""))
        self.assertIn("attachment;", response["Content-Disposition"])
        return json.loads(response.content)

    def test_export_structure(self):
        self.client.force_login(self.user)
        exported = self.export(data=False)
        self.assertEqual((exported["format"], exported["version"]), ("falcondatabase", 1))
        self.assertEqual(exported["project"]["name"], "Shop")
        table = exported["tables"][0]
        self.assertNotIn("rows", table)
        self.assertEqual(table["access"], "owner")
        columns = {c["name"]: c for c in table["columns"]}
        self.assertNotIn("owner_id", columns)
        self.assertEqual(columns["name"]["required"], True)
        self.assertEqual(columns["name"]["unique"], True)
        self.assertEqual(columns["price"]["default"], "0")
        self.assertEqual(columns["note"]["default"], "it's new")
        self.assertEqual(columns["added"]["default"], "now()")
        self.assertEqual(columns["code"]["default"], "uuid()")

    def test_round_trip_with_data(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        import json

        self.client.force_login(self.user)
        exported = self.export(data=True)
        self.assertEqual([r["name"] for r in exported["tables"][0]["rows"]], ["Coffee", "Cake"])
        upload = SimpleUploadedFile("shop.json", json.dumps(exported).encode(), content_type="application/json")
        response = self.client.post(reverse("project_import"), {"file": upload, "name": "Shop copy"})
        copy = self.user.projects.get(name="Shop copy")
        self.assertRedirects(response, copy.get_absolute_url())
        self.assertTrue(copy.auth_enabled)
        imported = copy.tables.get(name="products")
        self.assertEqual((imported.access, imported.description), ("owner", "Catalog"))
        rows, total = schema.select_rows(copy.schema, "products", imported.columns())
        self.assertEqual(total, 2)
        self.assertEqual([r["id"] for r in rows], [2, 3])  # ids preserved
        new_row = schema.insert_row(copy.schema, "products", {"name": "Pie"})
        self.assertEqual(new_row["id"], 4)  # identity continues after the imported ids
        self.assertEqual(new_row["note"], "it's new")
        self.assertIsNotNone(new_row["code"])

    def test_invalid_files_roll_back(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        import json

        self.client.force_login(self.user)
        before = self.user.projects.count()
        cases = [b"not json", json.dumps({"format": "other"}).encode(),
                 json.dumps({"format": "falcondatabase", "version": 1, "project": {"name": "X"},
                             "tables": [{"name": "ok", "columns": []}, {"name": "Bad Name", "columns": []}]}).encode()]
        for content in cases:
            upload = SimpleUploadedFile("x.json", content, content_type="application/json")
            response = self.client.post(reverse("project_import"), {"file": upload})
            self.assertRedirects(response, reverse("project_new"))
        self.assertEqual(self.user.projects.count(), before)

    def test_only_owner_exports(self):
        other = get_user_model().objects.create_user("bob", "bob@example.com", "pass12345")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.project.url("export")).status_code, 404)


class KpiTests(TestCase):
    def test_dashboard_kpis(self):
        from .kpis import account_kpis

        user = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        project = services.create_project(user, "Shop")
        services.create_table(project, "t", [{"name": "n", "type_": "text"}])
        for i in range(3):
            schema.insert_row(project.schema, "t", {"n": str(i)})
        kpis = {k["key"]: k for k in account_kpis(user)}
        self.assertEqual(len(kpis), 10)
        self.assertEqual((kpis["projects"]["value"], kpis["tables"]["value"], kpis["rows"]["value"]), (1, 1, 3))
        self.assertGreater(kpis["storage"]["value"], 0)
        self.assertTrue(kpis["visitors"]["compare"])
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(len(response.context["kpis"]), 10)


class SharingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("ana", "ana@example.com", "pass12345")
        self.bob = User.objects.create_user("bob", "bob@example.com", "pass12345")
        self.eve = User.objects.create_user("eve", "eve@example.com", "pass12345")
        self.project = services.create_project(self.owner, "Shop")

    def share(self, email, role):
        self.client.force_login(self.owner)
        return self.client.post(self.project.url("settings"), {"action": "add_member", "email": email, "role": role})

    def test_share_by_email(self):
        from .models import ProjectMember

        self.share("nobody@example.com", "editor")
        self.share("ana@example.com", "editor")
        self.assertFalse(ProjectMember.objects.exists())
        self.share("BOB@example.com", "editor")
        self.share("bob@example.com", "viewer")  # already a member: ignored
        member = ProjectMember.objects.get()
        self.assertEqual((member.user, member.role), (self.bob, "editor"))

        self.client.force_login(self.bob)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual([m.project for m in dashboard.context["shared"]], [self.project])
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 200)

    def test_editor_and_viewer_permissions(self):
        self.share("bob@example.com", "editor")
        self.share("eve@example.com", "viewer")
        create = {"name": "items", "access": "public", "columns-0-name": "n", "columns-0-type": "text"}

        self.client.force_login(self.bob)
        self.assertRedirects(self.client.post(self.project.url("table_new"), create), self.project.url("table", "items"))
        self.assertEqual(self.client.get(self.project.url("settings")).status_code, 403)

        self.client.force_login(self.eve)
        self.assertEqual(self.client.get(self.project.url("table", "items")).status_code, 200)
        self.assertEqual(self.client.post(self.project.url("table", "items"), {"n": "x"}).status_code, 403)
        self.assertEqual(self.client.post(self.project.url("table_new"), {**create, "name": "other"}).status_code, 403)
        self.assertEqual(self.client.get(self.project.url("settings")).status_code, 403)
        self.assertEqual(self.client.post(self.project.url("storage"), {"action": "settings", "storage_enabled": "on"}).status_code, 403)

        outsider = get_user_model().objects.create_user("zed", "zed@example.com", "pass12345")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 404)

    def test_remove_and_leave(self):
        from .models import ProjectMember

        self.share("bob@example.com", "viewer")
        self.share("eve@example.com", "editor")
        member = ProjectMember.objects.get(user=self.bob)
        self.client.post(self.project.url("settings"), {"action": "member_role", "member": member.pk, "role": "editor"})
        member.refresh_from_db()
        self.assertEqual(member.role, "editor")
        self.client.post(self.project.url("settings"), {"action": "remove_member", "member": member.pk})
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 404)

        ProjectMember.objects.filter(user=self.eve).update(role="viewer")
        self.client.force_login(self.eve)
        self.assertRedirects(self.client.post(self.project.url("leave")), reverse("dashboard"))
        self.assertFalse(ProjectMember.objects.filter(user=self.eve).exists())

    def test_shared_projects_in_analytics(self):
        self.share("bob@example.com", "viewer")
        self.client.force_login(self.bob)
        projects = self.client.get(reverse("analytics")).context["projects"]
        self.assertEqual(projects, [self.project])


class ActivityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.client.force_login(self.owner)
        self.client.post(reverse("project_new"), {"name": "Shop"})
        self.project = self.owner.projects.get()

    def kinds(self):
        return list(self.project.activity.order_by("created_at", "id").values_list("kind", flat=True))

    def test_dashboard_api_and_portal_actions_are_recorded(self):
        self.client.post(self.project.url("table_new"), {"name": "items", "access": "public",
                                                         "columns-0-name": "n", "columns-0-type": "text"})
        self.client.post(self.project.url("table", "items"), {"n": "a"})
        self.client.post(f"/api/v1/{self.project.ref}/tables/items", [{"n": "b"}, {"n": "c"}],
                         content_type="application/json", headers={"apikey": self.project.anon_key})
        self.assertEqual(self.kinds(), ["project_created", "table_created", "rows_inserted", "rows_inserted"])
        api_event = self.project.activity.first()
        self.assertEqual((api_event.actor_name, api_event.count, api_event.target), ("API", 2, "items"))
        self.assertEqual(self.project.activity.get(kind="table_created").user, self.owner)

        overview = self.client.get(self.project.get_absolute_url())
        self.assertEqual(overview.context["contrib"]["total"], 4)
        self.assertEqual(len(overview.context["recent"]), 4)

    def test_contribution_calendar(self):
        import datetime

        from . import activity
        from .models import ActivityEvent

        today = datetime.date(2026, 10, 25)  # a Sunday
        for days_ago, n in [(0, 3), (1, 1), (40, 6), (400, 9)]:
            for _ in range(n):
                ActivityEvent.objects.create(project=self.project, kind="rows_inserted",
                                             created_at=datetime.datetime.combine(today - datetime.timedelta(days=days_ago),
                                                                                  datetime.time(12), tzinfo=datetime.UTC))
        ActivityEvent.objects.filter(kind="project_created").delete()
        data = activity.contributions(self.project.activity.all(), today=today)
        days = [d for week in data["weeks"] for d in week["days"] if d["count"] is not None]
        self.assertEqual(len(days), 365)
        self.assertTrue(all(len(week["days"]) == 7 for week in data["weeks"]))
        self.assertEqual(data["weeks"][0]["days"][0]["date"].weekday(), 6)  # columns start on Sunday
        self.assertEqual((data["total"], data["busiest"]), (10, 6))       # the 400-day-old events are out
        by_date = {d["date"]: d for d in days}
        self.assertEqual(by_date[today]["count"], 3)
        self.assertEqual(by_date[today - datetime.timedelta(days=40)]["level"], 4)
        self.assertEqual(by_date[today - datetime.timedelta(days=1)]["level"], 1)
        self.assertEqual(by_date[today - datetime.timedelta(days=2)]["level"], 0)
        labelled = [w["label"] for w in data["weeks"] if w["label"]]
        self.assertEqual(len(labelled), 12)

    def test_dashboard_project_picker(self):
        other = services.create_project(self.owner, "Blog")
        response = self.client.get(reverse("dashboard") + f"?contrib={other.ref}")
        self.assertEqual(response.context["contrib_picked"], other)
        self.assertEqual(response.context["contrib"]["total"], 0)
        self.assertEqual(self.client.get(reverse("dashboard")).context["contrib"]["total"], 1)
