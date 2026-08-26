# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — dict_merge.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""Small, dependency-free helpers shared across headend modules.

`_deep_merge` moved out of main.py (2026-08-26) as part of the auth.py
extraction — auth.py's session-policy resolution needs it, and main.py's own
config-hierarchy resolution already used it in a dozen other places. A tiny
utility with zero dependencies is the right shape for a module both main.py
and auth.py can import without any circularity concern.

Named `dict_merge.py`, not `utils.py` — PYTHONPATH in this repo includes
both headend/ and edge/ as separate roots (see conftest.py / the standard CI
command), and edge/ already has its own `utils` PACKAGE
(edge/utils/__init__.py). A same-named top-level module here would be an
ambiguous `import utils` depending on sys.path resolution order — confirmed
the hard way: it silently resolved to edge/utils instead of this file the
first time.
"""
from __future__ import annotations


def _deep_merge(base: dict, override: dict) -> dict:
    """Rekursiv merge — override vinder ved konflikt."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
