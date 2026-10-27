"""Endpoints for AI assistants, authenticated with a personal access token.

    POST /api/ai/mcp            Model Context Protocol (streamable HTTP, JSON responses)
    GET  /api/ai/tools          tools available to the token
    POST /api/ai/tools/<name>   call a tool; the body holds its arguments

Requests send ``Authorization: Bearer fdb_ai_…``. Tokens are created in
Settings → AI access.
"""

import json

from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from core.changelog import VERSION
from core.models import AccessToken

from . import ai_tools
from .auth import ApiError, get_bearer
from .views import ApiJSONEncoder, read_json, respond

# Newest first; the server answers with the client's version when it knows it.
MCP_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
MCP_INSTRUCTIONS = (
    "falcondatabase is a backend of PostgreSQL projects. Start with list_projects, then describe_project "
    "to see the tables and columns before changing anything. Project arguments accept the ref, "
    "“owner/slug” or the slug. Tables always have id and created_at. Ask the user before destructive tools "
    "(delete_table, drop_column, delete_rows, delete_user)."
)


def authenticate(request):
    token = AccessToken.lookup(get_bearer(request))
    if token is None:
        raise ApiError(_("Invalid or missing AI token. Send it in “Authorization: Bearer fdb_ai_…”."), 401)
    ai_tools.touch(token)
    return token


def unauthorized(message):
    response = respond({"error": message}, 401)
    response["WWW-Authenticate"] = 'Bearer realm="falcondatabase"'
    return response


@csrf_exempt
def tools(request):
    if request.method != "GET":
        return respond({"error": _("Method %(method)s not allowed.") % {"method": request.method}}, 405)
    try:
        token = authenticate(request)
    except ApiError as exc:
        return unauthorized(exc.message)
    return respond({"tools": [t.as_mcp() for t in ai_tools.available_tools(token)]})


@csrf_exempt
def call_tool(request, name):
    if request.method != "POST":
        return respond({"error": _("Method %(method)s not allowed.") % {"method": request.method}}, 405)
    try:
        token = authenticate(request)
    except ApiError as exc:
        return unauthorized(exc.message)
    try:
        return respond({"data": ai_tools.call(token, name, read_json(request))})
    except ApiError as exc:
        return respond({"error": exc.message}, exc.status)


# --- MCP -------------------------------------------------------------------------

def rpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle_message(token, message):
    """Answer one JSON-RPC message; notifications and responses get ``None``."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return rpc_error(None, -32600, "Invalid Request")
    method = message.get("method")
    if method is None or "id" not in message:
        return None
    msg_id, params = message["id"], message.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        return rpc_result(msg_id, {
            "protocolVersion": requested if requested in MCP_VERSIONS else MCP_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "falcondatabase", "title": "falcondatabase", "version": VERSION},
            "instructions": MCP_INSTRUCTIONS,
        })
    if method == "ping":
        return rpc_result(msg_id, {})
    if method == "tools/list":
        return rpc_result(msg_id, {"tools": [t.as_mcp() for t in ai_tools.available_tools(token)]})
    if method == "tools/call":
        name = params.get("name")
        if name not in ai_tools.TOOLS:
            return rpc_error(msg_id, -32602, f"Unknown tool: {name}")
        try:
            result, is_error = ai_tools.call(token, name, params.get("arguments") or {}), False
        except ApiError as exc:
            result, is_error = {"error": exc.message}, True
        text = json.dumps(result, cls=ApiJSONEncoder, ensure_ascii=False)
        return rpc_result(msg_id, {"content": [{"type": "text", "text": text}], "isError": is_error})
    return rpc_error(msg_id, -32601, f"Method not found: {method}")


@csrf_exempt
def mcp(request):
    if request.method != "POST":
        # No server-initiated stream: every answer comes back in the POST response.
        response = respond({"error": _("Method %(method)s not allowed.") % {"method": request.method}}, 405)
        response["Allow"] = "POST"
        return response
    try:
        token = authenticate(request)
    except ApiError as exc:
        return unauthorized(exc.message)
    try:
        payload = json.loads(request.body or b"null")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return respond(rpc_error(None, -32700, "Parse error"), 400)

    if isinstance(payload, list):
        answers = [a for a in (handle_message(token, m) for m in payload) if a is not None]
        if not answers:
            return HttpResponse(status=202)
        return JsonResponse(answers, safe=False, encoder=ApiJSONEncoder, json_dumps_params={"ensure_ascii": False})
    answer = handle_message(token, payload)
    return respond(answer) if answer is not None else HttpResponse(status=202)
