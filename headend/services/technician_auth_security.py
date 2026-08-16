from __future__ import annotations

import html
import re


# Device identifiers are protocol identifiers, not free-form display names.
# Keep the grammar deliberately narrow while preserving existing physical and
# import-style TimeLapse identifiers (letters, digits, dot, underscore, colon,
# hyphen).  This also prevents HTML/script syntax from entering a technician
# auth session at the unauthenticated boundary.
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def validate_technician_device_id(value: str) -> str:
    """Return an exact valid machine identifier or raise ``ValueError``.

    The technician-auth start endpoint is intentionally reachable before user
    authentication because the Edge creates the QR challenge.  Treat its
    ``device_id`` as untrusted protocol data and reject free-form text rather
    than attempting to sanitize/canonicalize it.
    """
    if not isinstance(value, str) or not _DEVICE_ID_RE.fullmatch(value):
        raise ValueError("invalid_technician_device_id")
    return value


def html_text(value: object) -> str:
    """Escape untrusted text for insertion into HTML text/attribute context."""
    return html.escape(str(value), quote=True)
