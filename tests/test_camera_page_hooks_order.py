"""Regression test (2026-08-06): CameraPage.tsx (the "gear icon" device
config page, /cameras/:deviceId) crashed with "Minified React error #310"
(Rendered more hooks than during the previous render) whenever the page
finished loading its data.

Root cause: two useEffect() calls (the built-in local-TOTP countdown timer)
were placed AFTER the component's early `if (loading) return ...` / `if
(!device) return ...` guards. React's Rules of Hooks require every hook to be
called unconditionally, in the same order, on every render — the first
render (while loading) called fewer hooks than the second render (once data
arrived and execution proceeded past the early returns), which React detects
and throws on.

Fix: moved both useEffect() calls above the early-return guards, keeping
their existing internal null-guards (`if (!btTotp?.current_code) return`) so
they remain no-ops until data is available. This is a plain source-position
check — there is no frontend test runner in this repo (no jest/vitest
configured), so this mirrors the source-level regression pattern already used
throughout tests/ for backend fixes.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "timelapse-ui" / "src" / "pages" / "CameraPage.tsx").read_text(encoding="utf-8")


def test_no_hook_calls_after_the_early_return_guards() -> None:
    early_return_idx = SOURCE.index("if (loading) return <div")
    assert "if (!device) return" in SOURCE[early_return_idx:early_return_idx + 200]

    tail = SOURCE[early_return_idx:]
    for hook in ("useState(", "useEffect(", "useMemo(", "useCallback("):
        assert hook not in tail, (
            f"{hook} must not appear after CameraPage's early-return guards — React "
            "requires hooks to be called unconditionally on every render, and calling "
            "one only once loading/device resolve throws 'Rendered more hooks than "
            "during the previous render' (error #310) as soon as data loads."
        )
