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


class AiToolsTests(TestCase):
    def setUp(self):
        from core.models import AccessToken

        self.owner = get_user_model().objects.create_user("ana", "ana@example.com", "pass12345")
        self.project = services.create_project(self.owner, "App")
        self.other = services.create_project(self.owner, "Other")
        self.token, self.raw = AccessToken.issue(self.owner, "claude")

    def headers(self, raw=None):
        return {"Authorization": f"Bearer {raw or self.raw}"}

    def tool(self, tool_name, raw=None, **arguments):
        return self.client.post(f"/api/ai/tools/{tool_name}", data=arguments, content_type="application/json",
                                headers=self.headers(raw))

    def rpc(self, method, params=None, msg_id=1, raw=None):
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if msg_id is not None:
            message["id"] = msg_id
        return self.client.post("/api/ai/mcp", data=message, content_type="application/json",
                                headers=self.headers(raw))

    def test_requires_token(self):
        self.assertEqual(self.client.post("/api/ai/mcp", data={}, content_type="application/json").status_code, 401)
        self.assertEqual(self.client.get("/api/ai/tools", headers=self.headers("fdb_ai_nope")).status_code, 401)
        self.assertEqual(self.client.get("/api/ai/tools", headers=self.headers()).status_code, 200)
        self.token.refresh_from_db()
        self.assertIsNotNone(self.token.last_used_at)

    def test_mcp_handshake(self):
        result = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "test", "version": "1"}}).json()["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(self.rpc("notifications/initialized", msg_id=None).status_code, 202)
        names = {t["name"] for t in self.rpc("tools/list").json()["result"]["tools"]}
        self.assertTrue({"create_table", "insert_rows", "create_user", "create_project"} <= names)
        self.assertNotIn("create_account", names)  # admins only
        self.assertEqual(self.rpc("nope").json()["error"]["code"], -32601)

    def test_tables_data_and_users(self):
        ref = self.project.ref
        response = self.rpc("tools/call", {"name": "create_table", "arguments": {
            "project": ref, "name": "Tasks", "access": "private",
            "columns": [{"name": "title", "type": "text", "required": True}, {"name": "done", "type": "boolean"}],
        }}).json()["result"]
        self.assertFalse(response["isError"], response)
        self.assertEqual(self.tool("add_column", project=ref, table="tasks", name="due", type="date").status_code, 200)
        self.assertEqual(self.tool("rename_column", project=ref, table="tasks", column="due", new_name="deadline").status_code, 200)
        self.assertEqual(self.tool("update_table", project="ana/app", table="tasks", new_name="todos").status_code, 200)

        rows = self.tool("insert_rows", project="app", table="todos",
                         rows=[{"title": "a"}, {"title": "b", "done": True}]).json()["data"]["data"]
        self.assertEqual(len(rows), 2)
        result = self.tool("query_rows", project=ref, table="todos", filters={"done": "is.true"}).json()["data"]
        self.assertEqual((result["count"], result["data"][0]["title"]), (1, "b"))
        self.tool("update_row", project=ref, table="todos", id=rows[0]["id"], values={"done": True})
        self.assertEqual(self.tool("query_rows", project=ref, table="todos", filters={"done": True}).json()["data"]["count"], 2)
        self.assertEqual(self.tool("delete_rows", project=ref, table="todos", ids=[rows[0]["id"]]).json()["data"]["deleted"], [rows[0]["id"]])
        columns = [c["name"] for c in self.tool("describe_project", project=ref).json()["data"]["tables"][0]["columns"]]
        self.assertEqual(columns, ["id", "created_at", "title", "done", "deadline"])

        bad = self.tool("insert_rows", project=ref, table="todos", rows=[{"title": "ok"}, {"title": None}])
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.tool("query_rows", project=ref, table="todos").json()["data"]["count"], 1)

        user = self.tool("create_user", project=ref, email="Bob@Example.com", password="secreto1", data={"name": "Bob"})
        self.assertEqual(user.status_code, 200)
        self.assertEqual(self.tool("create_user", project=ref, email="bob@example.com", password="secreto1").status_code, 409)
        self.tool("update_user", project=ref, user="bob@example.com", is_active=False, data={"plan": "pro"})
        bob = self.project.users.get()
        self.assertEqual((bob.is_active, bob.data), (False, {"name": "Bob", "plan": "pro"}))
        self.tool("delete_user", project=ref, user=bob.pk)
        self.assertFalse(self.project.users.exists())
        self.assertTrue(self.project.activity.filter(kind="table_renamed", user=self.owner).exists())

        self.assertEqual(self.tool("delete_table", project=ref, table="todos").status_code, 200)
        self.assertFalse(self.project.tables.exists())

    def test_tool_errors_in_mcp(self):
        result = self.rpc("tools/call", {"name": "create_table", "arguments": {"project": "zzz", "name": "x"}}).json()["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(self.tool("create_table", project=self.project.ref).status_code, 400)  # missing name

    def test_scoped_and_read_only_tokens(self):
        from core.models import AccessToken
        from projects.models import ProjectMember

        _token, scoped = AccessToken.issue(self.owner, "one", project=self.project)
        projects = self.tool("list_projects", raw=scoped).json()["data"]["projects"]
        self.assertEqual([p["ref"] for p in projects], [self.project.ref])
        self.assertEqual(self.tool("describe_project", raw=scoped, project=self.other.ref).status_code, 404)
        self.assertEqual(self.tool("create_project", raw=scoped, name="x").status_code, 404)

        _token, reader = AccessToken.issue(self.owner, "ro", read_only=True)
        names = {t["name"] for t in self.client.get("/api/ai/tools", headers=self.headers(reader)).json()["tools"]}
        self.assertIn("query_rows", names)
        self.assertNotIn("create_table", names)
        self.assertEqual(self.tool("create_table", raw=reader, project=self.project.ref, name="t").status_code, 404)

        guest = get_user_model().objects.create_user("eva", "eva@example.com", "pass12345")
        ProjectMember.objects.create(project=self.project, user=guest, role=ProjectMember.VIEWER)
        _token, guest_raw = AccessToken.issue(guest, "eva")
        self.assertEqual(self.tool("describe_project", raw=guest_raw, project="ana/app").status_code, 200)
        self.assertEqual(self.tool("create_table", raw=guest_raw, project="ana/app", name="t").status_code, 403)

    def test_dashboard_pages(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.project.url("ai"), {"action": "create", "name": "laptop"})
        self.assertEqual(response.status_code, 200)
        token = self.owner.access_tokens.get(name="laptop")
        self.assertEqual(token.project, self.project)
        self.assertContains(response, response.context["new_token"])
        self.assertContains(response, "claude mcp add --transport http falcondatabase")
        self.assertEqual(self.tool("list_projects", raw=response.context["new_token"]).status_code, 200)

        self.client.post(self.project.url("ai"), {"action": "revoke", "token": token.pk})
        self.assertFalse(self.owner.access_tokens.filter(pk=token.pk).exists())

        response = self.client.post("/settings/ai/", {"action": "create", "name": "all", "access": "read"})
        self.assertTrue(self.owner.access_tokens.get(name="all").read_only)
        self.assertEqual(self.client.get("/ai/").status_code, 200)
