"""Regression test (2026-08-06): Peter asked for a full review of the Global
-> Customer -> Site -> Camera location -> Device hierarchy. That review found
there is no database-level foreign key ANYWHERE in this chain (Site.customer_id,
Camera.site_id, Camera.customer_id, Device.site_id, Device.customer_id are all
plain unconstrained columns) — every bit of referential integrity is whatever
the application code happens to check before a DELETE. delete_site() checked
for live Device rows but not Camera rows, and delete_customer() checked for
Site rows but not Camera rows directly (a Camera can have customer_id set with
site_id NULL, see create_camera()). Both gaps would let a site/customer with
historic (possibly image-bearing) camera locations be deleted, leaving those
Camera rows pointing at an id that no longer exists — invisible until
something tries to resolve it again.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = MAIN.index(f"def {name}(")
    end = MAIN.index("\n@app.", start + 1)
    return MAIN[start:end]


def test_delete_site_blocks_when_camera_locations_remain() -> None:
    section = _function_source("delete_site")
    assert "db.query(Camera).filter_by(site_id=site_id).count()" in section, (
        "delete_site must refuse to delete a site that still has Camera rows — "
        "there is no DB-level foreign key protecting against orphaning them."
    )


def test_delete_customer_blocks_when_camera_locations_remain() -> None:
    section = _function_source("delete_customer")
    assert "db.query(Camera).filter_by(customer_id=customer_id).count()" in section, (
        "delete_customer must refuse to delete a customer that still has Camera "
        "rows directly attached (customer_id set, site_id possibly NULL) — the "
        "Site-only check does not catch this case."
    )
