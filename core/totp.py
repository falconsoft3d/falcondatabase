"""Time-based one-time passwords (RFC 6238), compatible with authenticator apps."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret, counter):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10 ** DIGITS).zfill(DIGITS)


def current_counter(now=None):
    return int((time.time() if now is None else now) // STEP)


def matching_counter(secret, code, now=None, window=1):
    """Return the time step ``code`` belongs to (allowing ±window steps of clock drift), or None."""
    code = "".join(code.split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    counter = current_counter(now)
    for candidate in range(counter - window, counter + window + 1):
        if hmac.compare_digest(_code(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(secret, account, issuer="falcondatabase"):
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"
