"""Password protection for a deployed instance.

Running locally on 127.0.0.1, the machine's own login is the access control and
nothing else is needed. The moment the app is reachable from the internet that
stops being true, and the content makes this more than a nicety: a Blitz carries
cropped images of a copyrighted textbook. Serving those to anyone with the URL
is redistribution, whatever the intent.

So: bound to localhost, no password required. Bound to anything else, a password
is required and the app refuses to start without one — an accidentally public
instance should be impossible to create, not merely discouraged.
"""

from __future__ import annotations

import hmac
import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse, Response

PASSWORD_ENV = "BLITZ_PASSWORD"
REALM = "VCE Blitz"
# Reachable only from this machine; the OS login is the access control.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
# Served without a password so a platform health check does not need credentials.
PUBLIC_PATHS = {"/healthz"}


class MissingPassword(RuntimeError):
    """Raised at startup rather than serving a public instance unprotected."""


def password() -> str | None:
    value = os.environ.get(PASSWORD_ENV, "").strip()
    return value or None


def require_password_for(host: str) -> bool:
    return host not in LOCAL_HOSTS


def check_startup(host: str) -> None:
    """Refuse to start an internet-reachable instance with no password."""
    if require_password_for(host) and not password():
        raise MissingPassword(
            f"Refusing to serve on {host} without a password.\n"
            f"A deployed Blitz serves cropped images of a copyrighted textbook, "
            f"so it must not be open to anyone with the URL.\n"
            f"Set {PASSWORD_ENV} to a strong value and try again "
            f"(suggestion: {secrets.token_urlsafe(18)})."
        )


def _unauthorised() -> Response:
    return JSONResponse(
        {"detail": "Authentication required"},
        status_code=401,
        headers={"WWW-Authenticate": f'Basic realm="{REALM}", charset="UTF-8"'},
    )


def _supplied(request: Request) -> str | None:
    import base64
    import binascii

    header = request.headers.get("authorization", "")
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    _, _, supplied = decoded.partition(":")
    return supplied


async def auth_middleware(request: Request, call_next):
    """HTTP Basic, any username, compared in constant time.

    Basic auth over HTTPS is enough here: one shared password, one user, and a
    platform that terminates TLS. It needs no session store, no cookies and no
    login page to get wrong.
    """
    expected = password()
    if not expected or request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    supplied = _supplied(request)
    if supplied is None or not hmac.compare_digest(supplied, expected):
        return _unauthorised()
    return await call_next(request)
