from django.contrib.auth import get_user_model
from django.test import TestCase

from projects import services
from projects.models import ProjectTable


class ApiTestCase(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(owner, "App")
        self.project.auth_enabled = True
        self.project.save()
        self.table = services.create_table(self.project, "todos", [
            {"name": "title", "type_": "text", "required": True},
            {"name": "done", "type_": "boolean", "default": "false"},
            {"name": "priority", "type_": "integer"},
            {"name": "meta", "type_": "json"},
        ], access=ProjectTable.PUBLIC)
        self.base = f"/api/v1/{self.project.ref}"

    def call(self, method, path, data=None, key=None, token=None):
        headers = {"apikey": key or self.project.anon_key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return getattr(self.client, method)(self.base + path, data=data, content_type="application/json",
                                            headers=headers)

    def signup(self, email="u@example.com"):
        response = self.call("post", "/auth/signup", {"email": email, "password": "secreto1"})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()


class TableApiTests(ApiTestCase):
    def test_requires_valid_api_key(self):
        self.assertEqual(self.client.get(self.base + "/tables/todos").status_code, 401)
        self.assertEqual(self.call("get", "/tables/todos", key="nope").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/aaaaaaaaaaaaaaaaaaaa/tables/todos").status_code, 404)

    def test_crud(self):
        response = self.call("post", "/tables/todos", {"title": "Comprar pan", "meta": {"tags": ["casa"]}})
        self.assertEqual(response.status_code, 201)
        row = response.json()["data"]
        self.assertEqual(row["title"], "Comprar pan")
        self.assertFalse(row["done"])
        self.assertEqual(row["meta"], {"tags": ["casa"]})

        self.assertEqual(self.call("get", f"/tables/todos/{row['id']}").json()["data"]["id"], row["id"])
        response = self.call("patch", f"/tables/todos/{row['id']}", {"done": True})
        self.assertTrue(response.json()["data"]["done"])
        self.assertEqual(self.call("delete", f"/tables/todos/{row['id']}").status_code, 200)
        self.assertEqual(self.call("get", f"/tables/todos/{row['id']}").status_code, 404)

    def test_bulk_insert_is_atomic(self):
        response = self.call("post", "/tables/todos", [{"title": "a"}, {"title": None}])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.call("get", "/tables/todos").json()["count"], 0)
        response = self.call("post", "/tables/todos", [{"title": "a"}, {"title": "b"}])
        self.assertEqual(len(response.json()["data"]), 2)

    def test_filters_order_and_pagination(self):
        self.call("post", "/tables/todos", [
            {"title": "uno", "priority": 1}, {"title": "dos", "priority": 2, "done": True},
            {"title": "tres", "priority": 3}, {"title": "cuatro"},
        ])
        get = lambda query: self.call("get", "/tables/todos?" + query).json()
        self.assertEqual([r["title"] for r in get("priority=gte.2&order=priority.desc")["data"]], ["tres", "dos"])
        self.assertEqual(get("done=eq.true")["count"], 1)
        self.assertEqual(get("priority=is.null")["data"][0]["title"], "cuatro")
        self.assertEqual(get("title=in.(uno,tres)")["count"], 2)
        self.assertEqual(get("title=ilike.%25RE%25")["data"][0]["title"], "tres")
        page = get("order=id.asc&limit=2&offset=2")
        self.assertEqual(([r["title"] for r in page["data"]], page["count"]), (["tres", "cuatro"], 4))
        self.assertEqual(list(get("select=id,title&limit=1")["data"][0]), ["id", "title"])

    def test_errors_are_json(self):
        self.assertEqual(self.call("get", "/tables/nope").status_code, 404)
        response = self.call("get", "/tables/todos?missing=eq.1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing", response.json()["error"])
        response = self.call("post", "/tables/todos", {"priority": "alto", "title": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_index_lists_visible_tables(self):
        services.create_table(self.project, "secrets", [], access=ProjectTable.PRIVATE)
        names = [t["name"] for t in self.call("get", "").json()["tables"]]
        self.assertEqual(names, ["todos"])
        names = [t["name"] for t in self.call("get", "", key=self.project.service_key).json()["tables"]]
        self.assertEqual(names, ["secrets", "todos"])

    def test_cors_headers(self):
        response = self.client.options(self.base + "/tables/todos", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertIn("apikey", response["Access-Control-Allow-Headers"])
        sdk = self.client.get("/sdk/falcondb.js", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(sdk["Access-Control-Allow-Origin"], "*")
        self.assertIn(b"createClient", sdk.content)


class PolicyTests(ApiTestCase):
    def set_access(self, access):
        services.set_access(self.table, access)

    def test_public_read(self):
        self.set_access(ProjectTable.PUBLIC_READ)
        self.assertEqual(self.call("get", "/tables/todos").status_code, 200)
        self.assertEqual(self.call("post", "/tables/todos", {"title": "x"}).status_code, 401)
        token = self.signup()["token"]
        self.assertEqual(self.call("post", "/tables/todos", {"title": "x"}, token=token).status_code, 201)

    def test_authenticated(self):
        self.set_access(ProjectTable.AUTHENTICATED)
        self.assertEqual(self.call("get", "/tables/todos").status_code, 401)
        token = self.signup()["token"]
        self.assertEqual(self.call("get", "/tables/todos", token=token).status_code, 200)
        self.assertEqual(self.call("get", "/tables/todos", token="bad-token").status_code, 401)

    def test_private_only_service_key(self):
        self.set_access(ProjectTable.PRIVATE)
        token = self.signup()["token"]
        self.assertEqual(self.call("get", "/tables/todos", token=token).status_code, 404)
        self.assertEqual(self.call("get", "/tables/todos", key=self.project.service_key).status_code, 200)

    def test_owner_rows_are_isolated(self):
        self.set_access(ProjectTable.OWNER)
        ana, bob = self.signup("ana@x.com"), self.signup("bob@x.com")
        row = self.call("post", "/tables/todos", {"title": "de ana", "owner_id": bob["user"]["id"]},
                        token=ana["token"]).json()["data"]
        self.assertEqual(row["owner_id"], ana["user"]["id"])
        self.call("post", "/tables/todos", {"title": "de bob"}, token=bob["token"])

        listing = self.call("get", "/tables/todos", token=ana["token"]).json()
        self.assertEqual([r["title"] for r in listing["data"]], ["de ana"])
        self.assertEqual(self.call("get", f"/tables/todos/{row['id']}", token=bob["token"]).status_code, 404)
        self.assertEqual(self.call("patch", f"/tables/todos/{row['id']}", {"title": "x"},
                                   token=bob["token"]).status_code, 404)
        self.assertEqual(self.call("delete", f"/tables/todos/{row['id']}", token=bob["token"]).status_code, 404)
        self.assertEqual(self.call("get", "/tables/todos", key=self.project.service_key).json()["count"], 2)


class AuthApiTests(ApiTestCase):
    def test_signup_login_and_user(self):
        session = self.signup("Eva@Example.com")
        self.assertEqual(session["user"]["email"], "eva@example.com")
        self.assertEqual(self.call("post", "/auth/signup", {"email": "eva@example.com", "password": "secreto1"})
                         .status_code, 409)

        bad = self.call("post", "/auth/login", {"email": "eva@example.com", "password": "wrong"})
        self.assertEqual(bad.status_code, 401)
        token = self.call("post", "/auth/login", {"email": "eva@example.com", "password": "secreto1"}).json()["token"]

        me = self.call("get", "/auth/user", token=token).json()["user"]
        self.assertEqual(me["email"], "eva@example.com")
        updated = self.call("patch", "/auth/user", {"data": {"name": "Eva"}}, token=token).json()["user"]
        self.assertEqual(updated["data"], {"name": "Eva"})

    def test_validation(self):
        self.assertEqual(self.call("post", "/auth/signup", {"email": "no-es-email", "password": "secreto1"})
                         .status_code, 400)
        self.assertEqual(self.call("post", "/auth/signup", {"email": "a@b.com", "password": "123"}).status_code, 400)

    def test_disabled_auth_and_signup(self):
        self.project.allow_signup = False
        self.project.save()
        self.assertEqual(self.call("post", "/auth/signup", {"email": "a@b.com", "password": "secreto1"})
                         .status_code, 403)
        self.project.auth_enabled = False
        self.project.save()
        self.assertEqual(self.call("post", "/auth/login", {"email": "a@b.com", "password": "secreto1"})
                         .status_code, 403)

    def test_token_from_other_project_is_rejected(self):
        token = self.signup()["token"]
        other = services.create_project(self.project.owner, "Otra")
        other.auth_enabled = True
        other.save()
        response = self.client.get(f"/api/v1/{other.ref}/auth/user",
                                   headers={"apikey": other.anon_key, "Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_deactivated_user_token_stops_working(self):
        session = self.signup()
        self.project.users.filter(pk=session["user"]["id"]).update(is_active=False)
        self.assertEqual(self.call("get", "/auth/user", token=session["token"]).status_code, 401)


class SerializationTests(ApiTestCase):
    def test_decimal_is_a_number(self):
        services.add_column(self.table, name="price", type_="decimal")
        row = self.call("post", "/tables/todos", {"title": "x", "price": "12.50"}).json()["data"]
        self.assertEqual(row["price"], 12.5)
