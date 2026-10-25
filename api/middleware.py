from django.conf import settings
from django.http import HttpResponse

ALLOWED_HEADERS = "apikey, authorization, content-type, x-api-key"
ALLOWED_METHODS = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
CORS_PATHS = ("/api/", "/sdk/")


class CorsMiddleware:
    """Let browser frontends on other origins call the API and load the SDK."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(CORS_PATHS):
            return self.get_response(request)
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        origin = request.headers.get("Origin")
        allowed = settings.FALCONDB_CORS_ORIGINS
        if origin and ("*" in allowed or origin in allowed):
            response["Access-Control-Allow-Origin"] = "*" if "*" in allowed else origin
            response["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
            response["Access-Control-Allow-Methods"] = ALLOWED_METHODS
            response["Access-Control-Max-Age"] = "86400"
            if "*" not in allowed:
                response["Vary"] = "Origin"
        return response
