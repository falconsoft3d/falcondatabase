"""Outgoing requests to user-provided URLs, kept away from the server's private network."""

import ipaddress
import socket
import urllib.request
from urllib.parse import urlsplit

from django.conf import settings

USER_AGENT = "falcondatabase-uptime/1.0"


class BlockedAddress(Exception):
    pass


def guard(url):
    """Refuse URLs that point to private, local or reserved addresses (unless allowed in settings)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BlockedAddress("Only http:// and https:// URLs can be monitored.")
    if settings.FALCONDB_UPTIME_ALLOW_PRIVATE:
        return
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return  # the request itself fails (and is retried): DNS errors are often temporary
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global or address.is_multicast:
            raise BlockedAddress(f"{parts.hostname} points to a private address ({address}).")


class GuardedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        guard(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


opener = urllib.request.build_opener(GuardedRedirects)
