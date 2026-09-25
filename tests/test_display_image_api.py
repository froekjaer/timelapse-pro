"""Tests for headend/api/display_image_api.py — the display-resolution image
tier added 2026-09-20 to fix slow full-image loading in the device Lightbox
(see Dokumentation/HANDOVER_LOG.md same date).

Pure unit-level: no live server, no DB. The router's dependency callbacks
(find_image/ensure_access/log_access/xaccel/sanitize) are fakes, and the
route's endpoint function is called directly (its `Depends(...)` defaults
are just overridden by passing real keyword values, exactly like FastAPI's
own request handling would) — this exercises the real business logic
without needing the full app/auth/DB stack.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "headend"))

from api.display_image_api import (  # noqa: E402
    bounded_generate_display,
    display_dir_for,
    find_existing_display,
    generate_display_image,
    setup_display_router,
)


def _make_jpeg(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), (100, 150, 200)).save(str(path), "JPEG", quality=90)


# ── generate_display_image ───────────────────────────────────────────────────

def test_large_image_is_resized_to_max_dimension(tmp_path, monkeypatch):
    monkeypatch.setattr("api.display_image_api.DISPLAY_MAX_DIMENSION", 200)
    src = tmp_path / "original.jpg"
    _make_jpeg(src, 4000, 3000)  # 4:3, larger than the 200px cap
    dest = tmp_path / ".display" / "original.jpg"

    ok, err = generate_display_image(src, dest)

    assert ok is True
    assert err is None
    with Image.open(dest) as img:
        assert max(img.size) == 200
        # aspect ratio preserved (4:3)
        assert abs(img.width / img.height - 4000 / 3000) < 0.01


def test_small_image_is_not_upscaled(tmp_path, monkeypatch):
    monkeypatch.setattr("api.display_image_api.DISPLAY_MAX_DIMENSION", 2048)
    src = tmp_path / "small.jpg"
    _make_jpeg(src, 400, 300)
    dest = tmp_path / ".display" / "small.jpg"

    ok, _err = generate_display_image(src, dest)

    assert ok is True
    with Image.open(dest) as img:
        assert img.size == (400, 300)  # unchanged, never upscaled


def test_generation_failure_on_corrupt_source_returns_false(tmp_path):
    src = tmp_path / "corrupt.jpg"
    src.write_bytes(b"not a real jpeg")
    dest = tmp_path / ".display" / "corrupt.jpg"

    ok, err = generate_display_image(src, dest)

    assert ok is False
    assert err is not None
    assert not dest.exists()


# ── find_existing_display / display_dir_for ──────────────────────────────────

def test_find_existing_display_none_when_missing(tmp_path):
    src = tmp_path / "img.jpg"
    assert find_existing_display(src) is None


def test_find_existing_display_returns_cached_variant(tmp_path):
    src = tmp_path / "img.jpg"
    cached = display_dir_for(src) / "img.jpg"
    _make_jpeg(cached, 800, 600)

    found = find_existing_display(src)

    assert found == cached


def test_display_dir_is_sibling_of_original(tmp_path):
    src = tmp_path / "customer" / "site" / "cam" / "2026" / "09" / "20" / "img.jpg"
    assert display_dir_for(src) == src.parent / ".display"


# ── bounded_generate_display: concurrency bound ──────────────────────────────

def test_bounded_generate_respects_semaphore_timeout(tmp_path, monkeypatch):
    src = tmp_path / "img.jpg"
    _make_jpeg(src, 4000, 3000)
    dest = tmp_path / ".display" / "img.jpg"

    saturated_semaphore = MagicMock()
    saturated_semaphore.acquire.return_value = False  # simulate all slots busy + timeout
    monkeypatch.setattr("api.display_image_api._display_gen_semaphore", saturated_semaphore)

    ok, err = bounded_generate_display(src, dest)

    assert ok is False
    assert err == "concurrency_limit"
    saturated_semaphore.release.assert_not_called()  # never acquired, must not release


# ── Route logic (direct endpoint call, no HTTP/DB stack) ─────────────────────

def _router_endpoint(**fakes):
    find_image_fn = fakes.get("find_image_fn")
    ensure_access_fn = fakes.get("ensure_access_fn", lambda *a: MagicMock())
    log_access_fn = fakes.get("log_access_fn", lambda *a, **k: None)
    xaccel_fn = fakes.get("xaccel_fn", lambda *a, **k: None)
    sanitize_fn = fakes.get("sanitize_fn", lambda d: d)
    router = setup_display_router(find_image_fn, ensure_access_fn, log_access_fn, xaccel_fn, sanitize_fn)
    return router.routes[0].endpoint


def test_route_returns_404_when_image_not_found():
    endpoint = _router_endpoint(find_image_fn=lambda device_id, filename: None)

    with pytest.raises(Exception) as exc_info:
        endpoint(device_id="TL-X", filename="missing.jpg", _user=MagicMock(), db=MagicMock())
    assert "404" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 404


def test_route_generates_and_serves_display_variant_on_first_view(tmp_path):
    src = tmp_path / "img.jpg"
    _make_jpeg(src, 4000, 3000)
    xaccel_calls = []

    endpoint = _router_endpoint(
        find_image_fn=lambda device_id, filename: src,
        xaccel_fn=lambda path, media_type, cache_control="": xaccel_calls.append((path, media_type, cache_control)) or None,
    )

    response = endpoint(device_id="TL-X", filename="img.jpg", _user=MagicMock(), db=MagicMock())

    assert xaccel_calls, "expected the xaccel callback to be invoked"
    served_path, media_type, cache_control = xaccel_calls[0]
    assert served_path == display_dir_for(src) / "img.jpg"
    assert served_path.exists()
    assert media_type == "image/jpeg"
    assert "max-age" in cache_control
    # FileResponse fallback path (xaccel_fn returned None): response is a real file response
    assert response is not None


def test_route_falls_back_to_original_when_generation_fails(tmp_path, monkeypatch):
    src = tmp_path / "img.jpg"
    src.write_bytes(b"not a real jpeg")  # generation will fail on this
    xaccel_calls = []

    endpoint = _router_endpoint(
        find_image_fn=lambda device_id, filename: src,
        xaccel_fn=lambda path, media_type, cache_control="": xaccel_calls.append((path, media_type, cache_control)) or None,
    )

    endpoint(device_id="TL-X", filename="img.jpg", _user=MagicMock(), db=MagicMock())

    served_path, _media_type, cache_control = xaccel_calls[0]
    assert served_path == src  # fell back to the true original, not a broken/missing display file
    assert cache_control == ""  # no long-lived cache header on the fallback-to-original path


def test_route_reuses_cached_display_variant_without_regenerating(tmp_path):
    src = tmp_path / "img.jpg"
    _make_jpeg(src, 4000, 3000)
    cached = display_dir_for(src) / "img.jpg"
    _make_jpeg(cached, 111, 83)  # pre-existing cached variant, deliberately distinct size
    xaccel_calls = []

    endpoint = _router_endpoint(
        find_image_fn=lambda device_id, filename: src,
        xaccel_fn=lambda path, media_type, cache_control="": xaccel_calls.append(path) or None,
    )

    endpoint(device_id="TL-X", filename="img.jpg", _user=MagicMock(), db=MagicMock())

    with Image.open(xaccel_calls[0]) as img:
        assert img.size == (111, 83)  # served the pre-existing cache, didn't regenerate


def test_route_logs_access_and_enforces_capture_access(tmp_path):
    src = tmp_path / "img.jpg"
    _make_jpeg(src, 400, 300)
    ensure_access_calls = []
    log_calls = []

    endpoint = _router_endpoint(
        find_image_fn=lambda device_id, filename: src,
        ensure_access_fn=lambda _db, _user, device_id, filename: ensure_access_calls.append((device_id, filename)) or "capture-row",
        log_access_fn=lambda _db, _user, capture, action: log_calls.append((capture, action)),
    )

    endpoint(device_id="TL-X", filename="img.jpg", _user=MagicMock(), db=MagicMock())

    assert ensure_access_calls == [("TL-X", "img.jpg")]
    assert log_calls == [("capture-row", "display_view")]
