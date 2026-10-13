"""What the browser saw when a passkey login failed (Peter 2026-10-13).

Safari refused the Touch ID request inside the browser — no request reached
macOS and nothing reached the server — and the only trace was the red text on
the login page, which had to be read off the screen. The login page now
reports the WebAuthn error name and message here, so it lands in the Headend
log ("Login client report: ...") and the next failure is visible at once.

Unauthenticated by necessity (the user is not logged in). Bounded: short,
sanitised fields only (no credential data, no username), and a per-client
rate limit so it cannot flood the log.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque

from fastapi import APIRouter, Request

log = logging.getLogger("headend")
router = APIRouter()

MAX_PER_MINUTE = 20
_lock = threading.Lock()
_recent: dict[str, deque] = {}
_FIELD = re.compile(r"[^\w .,:;()\[\]/'\"!?=+\-–—æøåÆØÅ]")


def _clean(value, limit: int) -> str:
    return _FIELD.sub("?", str(value or ""))[:limit]


def _allowed(client: str, now: float) -> bool:
    with _lock:
        stamps = _recent.setdefault(client, deque())
        while stamps and now - stamps[0] > 60:
            stamps.popleft()
        if len(stamps) >= MAX_PER_MINUTE:
            return False
        stamps.append(now)
        if len(_recent) > 5000:
            _recent.clear()
        return True


@router.post("/api/auth/webauthn/client-report", status_code=204)
async def login_client_report(request: Request):
    client = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    if not _allowed(client, time.time()):
        return None
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    log.warning(
        "Login client report: stage=%s name=%s message=%s ua=%s",
        _clean(payload.get("stage"), 40),
        _clean(payload.get("name"), 60),
        _clean(payload.get("message"), 300),
        _clean(request.headers.get("user-agent"), 200),
    )
    return None
