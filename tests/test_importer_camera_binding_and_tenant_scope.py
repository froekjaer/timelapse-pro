"""Regression test (2026-08-06): Peter asked for a dedicated review of the
image-import function (headend/importer.py) as part of the same-day
Customer/Site/Camera/Device hierarchy review.

Two independent gaps were found and fixed:

1. Tenant scoping: /api/import/start, /api/import/status/{job_id}, and
   /api/import/jobs were gated only by require_role("admin") at router
   inclusion — which does NOT distinguish a customer-scoped admin (role=admin
   WITH customer_id set) from a platform admin. A customer-scoped admin could
   import images tagged to a different customer's site, poll another
   customer's job status by guessing its job_id, or simply list every
   customer's active/historical import jobs (customer/site/camera names) via
   /api/import/jobs. Same vulnerability class Peter flagged earlier the same
   day for timelapse generation, on the write side instead of the read side.

2. camera_id binding: start_import() created a virtual "TL-IMPORT-*" Device
   row but never a Camera row or DeviceAssignment binding it to one. Every
   imported capture's camera_id therefore stayed NULL forever (nothing for
   _resolve_capture_camera_customer() to find) — exactly the gap that forced
   a manual DeviceAssignment backdate + backfill run for Kamera 1 (Nordre
   Villavej) earlier the same session. Fixed by having start_import()
   find-or-create the Camera location and an active DeviceAssignment with a
   deliberately early assigned_at (2000-01-01), so freshly imported captures
   get camera_id set immediately instead of depending on a later backfill.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = (ROOT / "headend" / "importer.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = IMPORTER.index(f"def {name}(")
    try:
        end = IMPORTER.index("\n@router.", start + 1)
    except ValueError:
        end = len(IMPORTER)
    return IMPORTER[start:end]


def test_start_import_enforces_customer_tenant_scope() -> None:
    section = _function_source("start_import")
    assert "_ensure_customer_access(current_user, customer_id)" in section


def test_get_import_status_enforces_customer_tenant_scope() -> None:
    section = _function_source("get_import_status")
    assert "_ensure_customer_access(current_user, job.get(\"customer_id\"))" in section


def test_list_import_jobs_filters_by_customer() -> None:
    section = _function_source("list_import_jobs")
    assert "_is_platform_admin(current_user)" in section
    assert 'j.get("customer_id") == user_customer_id' in section


def test_start_import_creates_camera_binding_for_captures() -> None:
    section = _function_source("start_import")
    assert "db.query(Camera).filter_by(site_id=site_id, camera_name=camera_name)" in section, (
        "start_import must find-or-create a Camera location so imported captures "
        "can resolve camera_id, instead of leaving it permanently NULL."
    )
    assert "db.query(DeviceAssignment)" in section
    assert "assigned_at=datetime(2000, 1, 1, tzinfo=timezone.utc)" in section, (
        "the DeviceAssignment created for a fresh import must predate any plausible "
        "historical capture — using now() here would repeat the exact retroactive-"
        "assigned_at bug fixed for Kamera 1 earlier the same session."
    )
