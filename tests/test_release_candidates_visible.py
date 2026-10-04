"""Release registration (Peter, 2026-10-04): pick the NEWEST signed tag (not
the one behind the running commit), and always show update numbers (#id)
with device and status — also when the artifact already existed."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from services import release_candidates as rc  # noqa: E402


def test_latest_release_tag_uses_version_order_not_describe():
    seen = {}

    def git_text(args):
        seen["args"] = args
        return "v2.8.1-lab.58\nv2.8.1-lab.57\nv2.8.1-lab.9\n"

    assert rc.latest_release_tag(git_text) == "v2.8.1-lab.58"
    assert seen["args"] == ["tag", "--list", "v*", "--sort=-version:refname"]
    assert rc.latest_release_tag(lambda _a: "") == ""


class _Col:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return (self.name, other)


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conds):
        rows = self.rows
        for name, value in conds:
            rows = [r for r in rows if getattr(r, name) == value]
        return _Query(rows)

    def filter_by(self, **kw):
        return _Query([r for r in self.rows if all(getattr(r, k) == v for k, v in kw.items())])

    def order_by(self, _col):
        return _Query(sorted(self.rows, key=lambda r: r.id))

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


def test_candidates_carry_ref_device_name_and_status():
    Pending = SimpleNamespace(update_type=_Col("update_type"), version=_Col("version"), id=_Col("id"))
    Device = object()
    pend = [
        SimpleNamespace(id=321, update_type="app_updates", version="cf88", scope="device", scope_id="TL-C87", status="deployed", environment="test"),
        SimpleNamespace(id=320, update_type="app_updates", version="cf88", scope="device", scope_id="TL-043", status="pending", environment="test"),
        SimpleNamespace(id=316, update_type="app_updates", version="06ef", scope="device", scope_id="TL-043", status="pending", environment="test"),
    ]
    devs = [SimpleNamespace(device_id="TL-043", camera_name="Mod baggård", location_name=None, site_name=None),
            SimpleNamespace(device_id="TL-C87", camera_name="Kamera 1", location_name="Frøkjær", site_name=None)]
    db = SimpleNamespace(query=lambda model: _Query(pend if model is Pending else devs))
    out = rc.candidates_for_commit(db, Pending, Device, "cf88")
    assert [c["ref"] for c in out] == ["#320", "#321"]
    assert out[0] == {"id": 320, "ref": "#320", "device_id": "TL-043", "device_name": "Mod baggård", "status": "pending", "environment": "test"}
    assert rc.describe_candidates(out) == "#320 TL-043 (Mod baggård) pending, #321 TL-C87 (Kamera 1 / Frøkjær) deployed"
    assert rc.candidates_for_commit(db, Pending, Device, "") == []


def test_main_uses_newest_tag_and_returns_candidates():
    src = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    assert '_git_text(["describe", "--tags", "--abbrev=0"])' not in src
    assert "tag = _latest_release_tag(_git_text)" in src
    assert 'return {**result, "tag": tag, "candidates": candidates}' in src
    assert "_describe_candidates(made)" in src
