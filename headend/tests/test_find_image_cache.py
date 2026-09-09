"""
Regression test: _find_image_cached() must not permanently memoize a "not
found" result.

Background (2026-09-09, Edge 1 clock-drift backlog, Claude): a capture whose
file was requested by the gallery BEFORE its upload finished (during an
Edge-offline outage) got cached as "not found" (empty string) by a plain
functools.lru_cache with no TTL/invalidation. Once the file actually landed
on disk minutes later, every subsequent lookup for that exact
(device_id, filename, roots_key) still returned the stale empty string —
permanently, until the headend process restarted. Users saw genuinely
missing thumbnails/images that no client-side hard refresh could fix, since
the bug lived in server-side process memory, not in the browser.

Fix: _find_image_cached() only memoizes hits; misses are always recomputed
on the next call, so a file that shows up after being briefly absent is
found on the very next request.

Kør (fra headend/):
    python3 -m pytest tests/test_find_image_cache.py -v
"""
import os
import sys
import tempfile
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import main  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_find_image_cache():
    main._find_image_cache.clear()
    yield
    main._find_image_cache.clear()


def test_miss_is_not_cached_and_file_is_found_once_it_exists(tmp_path):
    """A lookup that misses (file not yet on disk) must be retried on the
    next call, not permanently stuck returning empty."""
    device_id = "TL-TESTDEV"
    filename = "Kunde_Site_Kamera_1_20260909_120000.jpg"
    roots_key = (str(tmp_path),)

    # Fil findes ikke endnu (fx: capture registreret i DB, men upload i gang)
    first = main._find_image_cached(device_id, filename, roots_key)
    assert first == ""
    assert (device_id, filename, roots_key) not in main._find_image_cache

    # Filen lander på disk (upload fuldført)
    day_dir = tmp_path / "cust" / "site" / "cam" / "2026" / "09" / "09"
    day_dir.mkdir(parents=True)
    image_path = day_dir / filename
    image_path.write_bytes(b"fake-jpeg-bytes")

    # Uden re-caching af misses skal den findes NU, ingen proces-genstart krævet
    second = main._find_image_cached(device_id, filename, roots_key)
    assert second == str(image_path)


def test_hit_is_cached_after_first_successful_lookup(tmp_path):
    """A found path is memoized: the underlying (potentially expensive)
    glob search doesn't run again for the same key."""
    device_id = "TL-TESTDEV"
    filename = "Kunde_Site_Kamera_1_20260909_130000.jpg"
    roots_key = (str(tmp_path),)

    day_dir = tmp_path / "cust" / "site" / "cam" / "2026" / "09" / "09"
    day_dir.mkdir(parents=True)
    image_path = day_dir / filename
    image_path.write_bytes(b"fake-jpeg-bytes")

    found = main._find_image_cached(device_id, filename, roots_key)
    assert found == str(image_path)
    assert main._find_image_cache[(device_id, filename, roots_key)] == str(image_path)

    # Slet filen fra disk — hvis vi rammer cachen (og ikke re-globber), skal
    # den stadig returnere den tidligere fundne sti.
    image_path.unlink()
    cached_again = main._find_image_cached(device_id, filename, roots_key)
    assert cached_again == str(image_path)
