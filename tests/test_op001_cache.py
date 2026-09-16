from __future__ import annotations

import hashlib
import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "Dokumentation" / "mission-framework" / "refresh_op001_cache.py"
SPEC = importlib.util.spec_from_file_location("refresh_op001_cache_test", MODULE_PATH)
op001cache = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(op001cache)

CANONICAL_HEAD = "9a1a45435ed0781f987760b00722d4a7700d5052"
OLD_REVISION = "2db8c2ba1a1f58ce07cdad0e78c35de949b20c09"
REAL_CONTENT = (op001cache.EXPECTED_CONTENT_MARKER + b"\n\n" + b"x" * 3000)
OTHER_CONTENT = (op001cache.EXPECTED_CONTENT_MARKER + b"\n\n" + b"y" * 3000)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._payload


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Point the module at an isolated cache directory for each test."""
    monkeypatch.setattr(op001cache, "CACHED_FILE", tmp_path / "OP-001-Mission-Operational-Preamble.md")
    monkeypatch.setattr(op001cache, "PROVENANCE_FILE", tmp_path / "OP-001.provenance.json")
    monkeypatch.setattr(op001cache, "CACHED_FILE_PREV", tmp_path / "OP-001-Mission-Operational-Preamble.md.prev")
    monkeypatch.setattr(op001cache, "PROVENANCE_FILE_PREV", tmp_path / "OP-001.provenance.json.prev")
    monkeypatch.setattr(op001cache, "HERE", tmp_path)
    return tmp_path


def _write_active(cache_dir: Path, content: bytes = REAL_CONTENT, **overrides):
    data = {
        "canonical_repository": "froekjaer/mission-framework",
        "canonical_path": "docs/operational/OP-001-Mission-Operational-Preamble.md",
        "cached_revision": CANONICAL_HEAD,
        "content_sha256": _digest(content),
        "cached_at": "2026-09-16T00:00:00Z",
        "last_check_at": "2026-09-16T00:00:00Z",
        "last_check_result": "VERIFIED",
    }
    data.update(overrides)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_bytes(content)
    (cache_dir / "OP-001.provenance.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def _write_backup(cache_dir: Path, content: bytes = REAL_CONTENT, **overrides):
    data = {
        "canonical_repository": "froekjaer/mission-framework",
        "canonical_path": "docs/operational/OP-001-Mission-Operational-Preamble.md",
        "cached_revision": CANONICAL_HEAD,
        "content_sha256": _digest(content),
        "cached_at": "2026-09-16T00:00:00Z",
        "last_check_at": "2026-09-16T00:00:00Z",
        "last_check_result": "VERIFIED",
    }
    data.update(overrides)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md.prev").write_bytes(content)
    (cache_dir / "OP-001.provenance.json.prev").write_text(json.dumps(data), encoding="utf-8")
    return data


def _mock_urlopen(monkeypatch, *, ref_sha: str | None = CANONICAL_HEAD, content: bytes | None = REAL_CONTENT, raise_error: Exception | None = None):
    def fake_urlopen(req, timeout=10):
        if raise_error is not None:
            raise raise_error
        if "api.github.com" in req.full_url:
            return FakeResponse(json.dumps({"object": {"sha": ref_sha}}).encode("utf-8"))
        if "raw.githubusercontent.com" in req.full_url:
            return FakeResponse(content or b"")
        raise AssertionError(f"unexpected URL requested: {req.full_url}")

    monkeypatch.setattr(op001cache.urllib.request, "urlopen", fake_urlopen)


# --- 1. bootstrap VERIFIED ---
def test_bootstrap_creates_cache_and_provenance(cache_dir, monkeypatch):
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=REAL_CONTENT)

    result = op001cache.bootstrap()

    assert result["cached_revision"] == CANONICAL_HEAD
    assert result["content_sha256"] == _digest(REAL_CONTENT)
    assert op001cache.CACHED_FILE.read_bytes() == REAL_CONTENT
    provenance = json.loads(op001cache.PROVENANCE_FILE.read_text())
    assert provenance["last_check_result"] == "VERIFIED"
    assert provenance["content_sha256"] == _digest(REAL_CONTENT)


# --- 2. mutate one byte of cached OP-001; check must NOT return VERIFIED (F1) ---
def test_tampered_content_is_not_reported_verified(cache_dir, monkeypatch):
    _write_active(cache_dir)
    # Flip a byte - may or may not remain valid UTF-8, must not matter.
    raw = bytearray((cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_bytes(bytes(raw))
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD)  # canonical reachable and "matches" the (stale) recorded revision

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] != "VERIFIED"
    assert result["last_check_result"] == "CORRUPTED"
    # forensic evidence preserved - tampered bytes must not be silently rewritten
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == bytes(raw)


def test_tampering_that_breaks_utf8_does_not_crash(cache_dir):
    """A byte flip that produces invalid UTF-8 must be handled, not raise UnicodeDecodeError."""
    _write_active(cache_dir)
    raw = bytearray((cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes())
    raw[10] = 0x9A  # a byte that is not valid as a UTF-8 continuation/start byte here
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_bytes(bytes(raw))

    result = op001cache.check(apply_refresh=False)  # must not raise

    assert result["last_check_result"] == "CORRUPTED"


# --- provenance digest tampering / malformed / missing ---
def test_provenance_digest_tampered_detected(cache_dir):
    _write_active(cache_dir, content_sha256="0" * 64)  # doesn't match real content

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "CORRUPTED"


def test_malformed_digest_treated_as_untrustworthy(cache_dir):
    _write_active(cache_dir, content_sha256="not-a-hex-digest")

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "CORRUPTED"


def test_missing_digest_is_unknown_not_verified(cache_dir):
    """Old-format provenance with no content_sha256 at all - we cannot check,
    so this must never silently become VERIFIED, and must not be treated as
    positive evidence of tampering (no unprompted recovery attempt)."""
    data = _write_active(cache_dir)
    del data["content_sha256"]
    (cache_dir / "OP-001.provenance.json").write_text(json.dumps(data), encoding="utf-8")

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "UNKNOWN"
    assert result["last_check_result"] != "VERIFIED"


def test_content_restored_but_provenance_mismatched(cache_dir):
    """Content bytes are actually fine, but provenance's digest describes
    something else entirely (e.g. provenance edited independently)."""
    _write_active(cache_dir, content_sha256=_digest(OTHER_CONTENT))

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "CORRUPTED"


# --- 3-7. refresh transaction: establish valid cache, refresh toward a
# different valid generation, inject failure during commit, verify the
# previous cache remains usable, verify no mixed state reports VERIFIED (F2) ---
def test_interrupted_refresh_leaves_no_verified_mixed_state(cache_dir, monkeypatch):
    _write_active(cache_dir, content=REAL_CONTENT, cached_revision=OLD_REVISION)
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=OTHER_CONTENT)  # genuinely different content

    # Fail the SECOND os.replace call (provenance commit), after the first
    # (content commit) has already succeeded - the exact window F2 covers.
    orig_replace = op001cache.os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated disk failure on provenance commit")
        return orig_replace(src, dst)

    monkeypatch.setattr(op001cache.os, "replace", flaky_replace)

    result = op001cache.check(apply_refresh=True)

    assert result.get("refreshed") is not True
    assert "refresh_error" in result

    # A *.prev backup of the original valid pair must exist and be usable.
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md.prev").read_bytes() == REAL_CONTENT

    # The active pair may now be mixed (new content, old provenance) - but a
    # fresh check (network working normally again) must NEVER report VERIFIED
    # for that mixed pair; it must detect it and recover.
    monkeypatch.setattr(op001cache.os, "replace", orig_replace)
    recovery_result = op001cache.check(apply_refresh=False)

    assert recovery_result["last_check_result"] in ("VERIFIED", "STALE")  # recovered to a real, self-consistent state
    assert recovery_result.get("recovered_from_backup") is True
    # Recovered content must be the last known-good (OLD) content, not a
    # silently-accepted mix.
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == REAL_CONTENT


def test_failed_temp_file_write_does_not_touch_active_state(cache_dir, monkeypatch):
    """A failure while writing the temp content file (before any os.replace)
    must leave the active cache completely untouched."""
    _write_active(cache_dir, content=REAL_CONTENT, cached_revision=OLD_REVISION)
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=OTHER_CONTENT)

    def failing_mkstemp(*args, **kwargs):
        raise OSError("simulated disk full during temp file creation")

    monkeypatch.setattr(op001cache.tempfile, "mkstemp", failing_mkstemp)

    result = op001cache.check(apply_refresh=True)

    assert result.get("refreshed") is not True
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == REAL_CONTENT
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == OLD_REVISION


def test_corrupted_with_no_backup_is_not_silently_recovered(cache_dir):
    """If both the active pair is inconsistent AND no *.prev backup exists,
    the result must be an honest CORRUPTED, never a fabricated VERIFIED."""
    _write_active(cache_dir, content_sha256="0" * 64)
    assert not (cache_dir / "OP-001-Mission-Operational-Preamble.md.prev").exists()

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "CORRUPTED"
    assert result["cache_usable"] is False


def test_recovery_from_backup_when_active_is_corrupted(cache_dir):
    _write_active(cache_dir, content_sha256="0" * 64)  # active broken
    _write_backup(cache_dir, content=REAL_CONTENT, cached_revision=CANONICAL_HEAD)  # backup good

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] != "CORRUPTED"
    assert result.get("recovered_from_backup") is True
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == REAL_CONTENT


# --- 1/2 original scenarios, re-verified against the new schema ---
def test_verified_when_head_matches_cache(cache_dir, monkeypatch):
    _write_active(cache_dir)
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD)

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "VERIFIED"
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["last_check_result"] == "VERIFIED"
    assert provenance["cached_revision"] == CANONICAL_HEAD


def test_stale_when_head_differs_from_cache(cache_dir, monkeypatch):
    _write_active(cache_dir, cached_revision=OLD_REVISION)
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD)

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "STALE"
    # check-only must not touch the cached content or bump cached_revision
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == REAL_CONTENT
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == OLD_REVISION


def test_stale_with_refresh_applies_new_content(cache_dir, monkeypatch):
    _write_active(cache_dir, cached_revision=OLD_REVISION)
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=OTHER_CONTENT)

    result = op001cache.check(apply_refresh=True)

    assert result["refreshed"] is True
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == OTHER_CONTENT
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == CANONICAL_HEAD
    assert provenance["last_check_result"] == "VERIFIED"
    assert provenance["content_sha256"] == _digest(OTHER_CONTENT)
    # a backup of the pre-refresh valid state must exist
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md.prev").read_bytes() == REAL_CONTENT


# --- 3 & 4. canonical unavailable, with previously verified / previously unknown cache ---
@pytest.mark.parametrize("previous_state", ["VERIFIED", "UNKNOWN", "STALE"])
def test_unknown_when_canonical_unreachable(cache_dir, monkeypatch, previous_state):
    _write_active(cache_dir, last_check_result=previous_state)
    _mock_urlopen(monkeypatch, raise_error=urllib.error.URLError("simulated network failure"))

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "UNKNOWN"
    # UNKNOWN must never be reported as VERIFIED or STALE - and the cache
    # content must be left completely untouched (no silent mutation).
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == REAL_CONTENT
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == CANONICAL_HEAD  # untouched
    assert provenance["last_check_result"] == "UNKNOWN"


def test_cache_remains_usable_when_canonical_unreachable(cache_dir, monkeypatch):
    """A previously-verified cache stays on disk and readable even when offline."""
    _write_active(cache_dir, last_check_result="VERIFIED")
    _mock_urlopen(monkeypatch, raise_error=urllib.error.URLError("simulated network failure"))

    result = op001cache.check(apply_refresh=False)

    assert result["cache_usable"] is True
    assert op001cache.CACHED_FILE.read_bytes() == REAL_CONTENT


# --- 5. malformed/missing cache metadata (now handled inside check(), not a separate loader) ---
def test_missing_everything_raises_clear_error_not_corrupted(cache_dir):
    """A brand-new directory with nothing bootstrapped yet is not 'corrupted' -
    it is simply not set up, and must say so clearly rather than crash or
    silently invent a CORRUPTED verdict for something that never existed."""
    with pytest.raises(op001cache.CacheError):
        op001cache.check(apply_refresh=False)


def test_malformed_provenance_json_is_corrupted_not_a_crash(cache_dir):
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_bytes(REAL_CONTENT)
    (cache_dir / "OP-001.provenance.json").write_text("not json {{{", encoding="utf-8")

    result = op001cache.check(apply_refresh=False)  # must not raise

    assert result["last_check_result"] == "CORRUPTED"


# --- 6. cache/source integrity mismatch on refresh (fetched content rejected) ---
def test_refresh_rejects_corrupted_remote_content(cache_dir, monkeypatch):
    _write_active(cache_dir, cached_revision=OLD_REVISION)
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=b"garbage, not the real document")

    result = op001cache.check(apply_refresh=True)

    assert result.get("refreshed") is not True
    # cache must be left untouched when the fetched content fails the integrity check
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_bytes() == REAL_CONTENT


def test_ref_response_with_non_sha_object_is_rejected(cache_dir, monkeypatch):
    """A malformed/unexpected ref API response must not be trusted as a commit SHA."""

    def fake_urlopen(req, timeout=10):
        return FakeResponse(json.dumps({"object": {"sha": "not-a-real-sha"}}).encode("utf-8"))

    monkeypatch.setattr(op001cache.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(op001cache.CacheError):
        op001cache._fetch_canonical_head_sha()


# --- 9. canonical authority remains identifiable ---
def test_canonical_authority_constants_are_correct():
    assert op001cache.CANONICAL_REPOSITORY == "froekjaer/mission-framework"
    assert op001cache.CANONICAL_PATH == "docs/operational/OP-001-Mission-Operational-Preamble.md"


# --- error handling: expected failures must not produce a raw traceback via the CLI ---
def test_cli_reports_clean_error_not_traceback(cache_dir, capsys):
    # Directly exercise the CLI error path for a not-yet-bootstrapped directory.
    import sys as _sys

    old_argv = _sys.argv
    _sys.argv = ["refresh_op001_cache.py"]
    try:
        exit_code = op001cache.main()
    finally:
        _sys.argv = old_argv

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert "ERROR" in captured.err
