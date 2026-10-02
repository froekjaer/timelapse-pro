"""LAB preview delete endpoints (Peter, 2026-10-02): working images can be
removed from the LAB UI; only preview_*.jpg under the device's LAB root."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from api import lab_previews_api  # noqa: E402
from database import get_db  # noqa: E402


def _client(tmp_path, allowed=True):
    seen = []

    def require_role(_role):
        return SimpleNamespace(username="peter")

    def ensure_access(_db, _user, device_id):
        seen.append(device_id)
        if not allowed:
            raise HTTPException(status_code=403, detail="no access")

    app = FastAPI()
    app.include_router(lab_previews_api.create_lab_previews_router(require_role, ensure_access, lambda: tmp_path))
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app), seen


def _files(tmp_path, *names):
    root = tmp_path / "_lab" / "TL-1"
    (root / ".thumbs").mkdir(parents=True)
    for n in names:
        (root / n).write_bytes(b"x")
        (root / ".thumbs" / n).write_bytes(b"t")
    return root


def test_delete_one_removes_image_and_thumb(tmp_path):
    root = _files(tmp_path, "preview_1.jpg", "preview_2.jpg")
    client, seen = _client(tmp_path)
    r = client.delete("/api/lab/TL-1/previews/preview_1.jpg")
    assert r.status_code == 200 and r.json()["deleted"] == 1
    assert not (root / "preview_1.jpg").exists() and not (root / ".thumbs/preview_1.jpg").exists()
    assert (root / "preview_2.jpg").exists() and seen == ["TL-1"]


def test_delete_all_only_previews(tmp_path):
    root = _files(tmp_path, "preview_1.jpg", "preview_2.jpg")
    (root / "keep.txt").write_text("k")
    client, _ = _client(tmp_path)
    r = client.delete("/api/lab/TL-1/previews")
    assert r.json()["deleted"] == 2
    assert sorted(p.name for p in root.iterdir() if p.is_file()) == ["keep.txt"]


@pytest.mark.parametrize("name", ["keep.txt", "..%2Fpreview_1.jpg", "preview_..jpg.png"])
def test_rejects_non_preview_or_traversal(tmp_path, name):
    _files(tmp_path, "preview_1.jpg")
    client, _ = _client(tmp_path)
    assert client.delete(f"/api/lab/TL-1/previews/{name}").status_code in (400, 404)


def test_device_access_enforced(tmp_path):
    root = _files(tmp_path, "preview_1.jpg")
    client, _ = _client(tmp_path, allowed=False)
    assert client.delete("/api/lab/TL-1/previews").status_code == 403
    assert (root / "preview_1.jpg").exists()
