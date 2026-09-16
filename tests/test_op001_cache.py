from __future__ import annotations

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
REAL_CONTENT = ("# OP-001 — Mission Operational Preamble (MOP)\n\n" + "x" * 3000)


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
    cached_file = tmp_path / "OP-001-Mission-Operational-Preamble.md"
    provenance_file = tmp_path / "OP-001.provenance.json"
    monkeypatch.setattr(op001cache, "CACHED_FILE", cached_file)
    monkeypatch.setattr(op001cache, "PROVENANCE_FILE", provenance_file)
    return tmp_path


def _write_provenance(cache_dir: Path, **overrides):
    data = {
        "canonical_repository": "froekjaer/mission-framework",
        "canonical_path": "docs/operational/OP-001-Mission-Operational-Preamble.md",
        "cached_revision": CANONICAL_HEAD,
        "cached_at": "2026-09-16T00:00:00Z",
        "last_check_at": "2026-09-16T00:00:00Z",
        "last_check_result": "VERIFIED",
    }
    data.update(overrides)
    (cache_dir / "OP-001.provenance.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def _mock_urlopen(monkeypatch, *, ref_sha: str | None = CANONICAL_HEAD, content: str | None = REAL_CONTENT, raise_error: Exception | None = None):
    def fake_urlopen(req, timeout=10):
        if raise_error is not None:
            raise raise_error
        if "api.github.com" in req.full_url:
            return FakeResponse(json.dumps({"object": {"sha": ref_sha}}).encode("utf-8"))
        if "raw.githubusercontent.com" in req.full_url:
            return FakeResponse((content or "").encode("utf-8"))
        raise AssertionError(f"unexpected URL requested: {req.full_url}")

    monkeypatch.setattr(op001cache.urllib.request, "urlopen", fake_urlopen)


# 1. canonical reachable and cache matches
def test_verified_when_head_matches_cache(cache_dir, monkeypatch):
    _write_provenance(cache_dir)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_text(REAL_CONTENT, encoding="utf-8")
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD)

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "VERIFIED"
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["last_check_result"] == "VERIFIED"
    assert provenance["cached_revision"] == CANONICAL_HEAD


# 2. canonical reachable and newer than cache
def test_stale_when_head_differs_from_cache(cache_dir, monkeypatch):
    _write_provenance(cache_dir, cached_revision=OLD_REVISION)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_text("old content", encoding="utf-8")
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD)

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "STALE"
    # check-only must not touch the cached content or bump cached_revision
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_text() == "old content"
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == OLD_REVISION


def test_stale_with_refresh_applies_new_content(cache_dir, monkeypatch):
    _write_provenance(cache_dir, cached_revision=OLD_REVISION)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_text("old content", encoding="utf-8")
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=REAL_CONTENT)

    result = op001cache.check(apply_refresh=True)

    assert result["refreshed"] is True
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_text() == REAL_CONTENT
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == CANONICAL_HEAD
    assert provenance["last_check_result"] == "VERIFIED"


# 3 & 4. canonical unavailable, with previously verified / previously unknown cache
@pytest.mark.parametrize("previous_state", ["VERIFIED", "UNKNOWN", "STALE"])
def test_unknown_when_canonical_unreachable(cache_dir, monkeypatch, previous_state):
    _write_provenance(cache_dir, last_check_result=previous_state)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_text(REAL_CONTENT, encoding="utf-8")
    _mock_urlopen(monkeypatch, raise_error=urllib.error.URLError("simulated network failure"))

    result = op001cache.check(apply_refresh=False)

    assert result["last_check_result"] == "UNKNOWN"
    # UNKNOWN must never be reported as VERIFIED or STALE - and the cache
    # content must be left completely untouched (test 10, no silent mutation).
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_text() == REAL_CONTENT
    provenance = json.loads((cache_dir / "OP-001.provenance.json").read_text())
    assert provenance["cached_revision"] == CANONICAL_HEAD  # untouched
    assert provenance["last_check_result"] == "UNKNOWN"


def test_cache_remains_usable_when_canonical_unreachable(cache_dir, monkeypatch):
    """A previously-verified cache stays on disk and readable even when offline."""
    _write_provenance(cache_dir, last_check_result="VERIFIED")
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_text(REAL_CONTENT, encoding="utf-8")
    _mock_urlopen(monkeypatch, raise_error=urllib.error.URLError("simulated network failure"))

    result = op001cache.check(apply_refresh=False)

    assert result["cache_usable"] is True
    assert op001cache.CACHED_FILE.read_text(encoding="utf-8") == REAL_CONTENT


# 5. malformed/missing cache metadata
def test_missing_provenance_file_fails_clearly(cache_dir):
    with pytest.raises(SystemExit):
        op001cache._load_provenance()


def test_malformed_provenance_json_fails_clearly(cache_dir):
    (cache_dir / "OP-001.provenance.json").write_text("not json {{{", encoding="utf-8")
    with pytest.raises(SystemExit):
        op001cache._load_provenance()


# 6. cache/source integrity mismatch
def test_refresh_rejects_corrupted_content(cache_dir, monkeypatch):
    _write_provenance(cache_dir, cached_revision=OLD_REVISION)
    (cache_dir / "OP-001-Mission-Operational-Preamble.md").write_text("old content", encoding="utf-8")
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content="garbage, not the real document")

    result = op001cache.check(apply_refresh=True)

    assert result.get("refreshed") is not True
    # cache must be left untouched when the fetched content fails the integrity check
    assert (cache_dir / "OP-001-Mission-Operational-Preamble.md").read_text() == "old content"


def test_ref_response_with_non_sha_object_is_rejected(cache_dir, monkeypatch):
    """A malformed/unexpected ref API response must not be trusted as a commit SHA."""

    def fake_urlopen(req, timeout=10):
        return FakeResponse(json.dumps({"object": {"sha": "not-a-real-sha"}}).encode("utf-8"))

    monkeypatch.setattr(op001cache.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ValueError):
        op001cache._fetch_canonical_head_sha()


# 9. canonical authority remains identifiable
def test_canonical_authority_constants_are_correct():
    assert op001cache.CANONICAL_REPOSITORY == "froekjaer/mission-framework"
    assert op001cache.CANONICAL_PATH == "docs/operational/OP-001-Mission-Operational-Preamble.md"


def test_bootstrap_creates_cache_and_provenance(cache_dir, monkeypatch):
    _mock_urlopen(monkeypatch, ref_sha=CANONICAL_HEAD, content=REAL_CONTENT)

    result = op001cache.bootstrap()

    assert result["cached_revision"] == CANONICAL_HEAD
    assert op001cache.CACHED_FILE.read_text(encoding="utf-8") == REAL_CONTENT
    provenance = json.loads(op001cache.PROVENANCE_FILE.read_text())
    assert provenance["last_check_result"] == "VERIFIED"
    assert provenance["canonical_repository"] == "froekjaer/mission-framework"
