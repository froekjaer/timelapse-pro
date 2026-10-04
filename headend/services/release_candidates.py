"""Release registration helpers (Peter, 2026-10-04).

- "Registrer seneste signerede tag" must pick the NEWEST release tag. It used
  `git describe --tags`, i.e. the newest tag reachable from the commit the
  Headend happens to run, so a new tag on a later commit was never found
  (lab.57 was registered as lab.56 twice on 2026-10-03).
- The update number (#id) must always be visible: registration returns and
  logs every candidate for the release commit with #id, device, name, status
  — also when the artifact already existed (e.g. built by the tag poller).
"""

from __future__ import annotations

from collections.abc import Callable


def latest_release_tag(git_text: Callable[[list[str]], str | None]) -> str:
    """Most recently created v* tag. Not version order: the old v2.9.0 tag
    (2026-05-12) sorts above every v2.8.1-lab.N, so version order kept picking
    it (Peter, 2026-10-04: "der kommer ingen nye")."""
    raw = git_text(["tag", "--list", "v*", "--sort=-creatordate"]) or ""
    return next((line.strip() for line in raw.splitlines() if line.strip()), "")


def device_label(device) -> str:
    if device is None:
        return ""
    parts = [getattr(device, "camera_name", None), getattr(device, "location_name", None), getattr(device, "site_name", None)]
    return " / ".join(p for p in parts if p) or ""


def candidates_for_commit(db, pending_model, device_model, commit: str) -> list[dict]:
    """Every app-update candidate for a release commit, oldest first."""
    if not commit:
        return []
    rows = (
        db.query(pending_model)
        .filter(pending_model.update_type == "app_updates", pending_model.version == commit)
        .order_by(pending_model.id)
        .all()
    )
    out = []
    for row in rows:
        device = db.query(device_model).filter_by(device_id=row.scope_id).first() if row.scope == "device" else None
        out.append({
            "id": row.id,
            "ref": f"#{row.id}",
            "device_id": row.scope_id,
            "device_name": device_label(device),
            "status": row.status,
            "environment": row.environment,
        })
    return out


def describe_candidates(candidates: list[dict]) -> str:
    """'#320 TL-043… (Mod baggård) pending, #321 …' for logs and messages."""
    return ", ".join(
        f"{c['ref']} {c['device_id']}" + (f" ({c['device_name']})" if c["device_name"] else "") + f" {c['status']}"
        for c in candidates
    ) or "ingen"
