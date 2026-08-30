from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


RELEASE_SCHEMA = "timelapse.edge.release.v1"
PENDING_UPDATE_SCHEMA = "timelapse.edge.pending_update.v1"
PENDING_UPDATE_FILENAME = ".timelapse-update-pending.json"

# Capture the lifecycle module that the known-good, currently running agent
# imported before an artifact can replace files on disk.  The installer writes
# this exact source into the durable recovery directory for the independent
# post-restart guard, so rollback never depends on importing the candidate
# release that is being verified.
_TRUSTED_MODULE_SOURCE = Path(__file__).read_text(encoding="utf-8")


def _expected_release_identity(artifact: dict | None) -> tuple[str, str, str]:
    artifact = artifact if isinstance(artifact, dict) else {}
    manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
    return (
        str(artifact.get("artifact_id") or ""),
        str(artifact.get("source_commit") or manifest.get("source_commit") or ""),
        str(artifact.get("version") or manifest.get("version") or ""),
    )


def release_receipt_matches_artifact(receipt_path: Path, artifact: dict | None) -> bool:
    """Return True only when the durable local receipt identifies this exact artifact."""
    artifact_id, source_commit, version = _expected_release_identity(artifact)
    if not artifact_id or not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(receipt, dict):
        return False
    if receipt.get("schema") != RELEASE_SCHEMA:
        return False
    if str(receipt.get("artifact_id") or "") != artifact_id:
        return False
    if source_commit and str(receipt.get("source_commit") or "") != source_commit:
        return False
    if version and str(receipt.get("version") or "") != version:
        return False
    return True


def _safe_edge_output_paths(artifact: dict | None) -> list[Path]:
    artifact = artifact if isinstance(artifact, dict) else {}
    manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
    outputs: list[Path] = []
    for item in manifest.get("outputs", []):
        if not isinstance(item, dict):
            continue
        raw = str(item.get("path") or "")
        if not raw.startswith("edge/"):
            continue
        rel = Path(raw)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe rollback artifact path: {raw}")
        outputs.append(rel)
    return outputs


def _atomic_write_json(path: Path, payload: dict, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(tmp, flags, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        path.chmod(mode)
    finally:
        tmp.unlink(missing_ok=True)


def pending_app_update_path(repo: Path) -> Path:
    return repo / "edge" / PENDING_UPDATE_FILENAME


def load_pending_app_update(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("pending_update_marker_unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != PENDING_UPDATE_SCHEMA:
        raise RuntimeError("pending_update_marker_invalid_schema")
    return payload


def write_pending_app_update(
    path: Path,
    *,
    update_id: int,
    artifact: dict,
    recovery_dir: Path,
    managed_unit_files: tuple[str, ...] | list[str] = (),
    health_timeout_s: int = 180,
    repo: Path = Path("/opt/timelapse"),
) -> dict:
    if path.exists():
        raise FileExistsError("pending_app_update_recovery_exists")
    artifact_id, source_commit, version = _expected_release_identity(artifact)
    if not artifact_id:
        raise ValueError("pending_update_artifact_id_missing")
    outputs = [str(rel) for rel in _safe_edge_output_paths(artifact)]
    payload = {
        "schema": PENDING_UPDATE_SCHEMA,
        "state": "awaiting_restart_health",
        "update_id": int(update_id),
        "artifact_id": artifact_id,
        "source_commit": source_commit,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "recovery_dir": str(recovery_dir),
        "health_timeout_s": max(10, int(health_timeout_s)),
        "outputs": outputs,
        "managed_unit_files": [str(unit) for unit in managed_unit_files],
    }
    _atomic_write_json(path, payload)
    return payload


def pending_app_update_matches(path: Path, update_id: int, artifact: dict | None) -> bool:
    try:
        payload = load_pending_app_update(path)
    except Exception:
        return False
    if not payload or int(payload.get("update_id", -1)) != int(update_id):
        return False
    artifact_id, source_commit, version = _expected_release_identity(artifact)
    if str(payload.get("artifact_id") or "") != artifact_id:
        return False
    if source_commit and str(payload.get("source_commit") or "") != source_commit:
        return False
    if version and str(payload.get("version") or "") != version:
        return False
    return True


def mark_pending_app_update_health_confirmed(path: Path) -> dict:
    payload = load_pending_app_update(path)
    if not payload:
        raise FileNotFoundError("pending_update_marker_missing")
    if payload.get("state") == "rolled_back_by_guard":
        raise RuntimeError("pending_update_already_rolled_back")
    payload["state"] = "health_confirmed"
    payload["health_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(path, payload)
    return payload


def record_pending_app_update_health_probe(
    path: Path,
    *,
    stability_s: int,
    checks: dict | None = None,
    now: datetime | None = None,
) -> dict:
    payload = load_pending_app_update(path)
    if not payload:
        raise FileNotFoundError("pending_update_marker_missing")
    if payload.get("state") != "awaiting_restart_health":
        return payload

    now = now or datetime.now(timezone.utc)
    first_raw = payload.get("health_first_ok_at")
    if first_raw:
        try:
            first_ok = datetime.fromisoformat(str(first_raw))
        except ValueError:
            first_ok = now
            payload["health_first_ok_at"] = first_ok.isoformat()
    else:
        first_ok = now
        payload["health_first_ok_at"] = first_ok.isoformat()

    payload["health_last_ok_at"] = now.isoformat()
    payload["health_stability_s"] = max(0, int(stability_s))
    payload["health_checks"] = checks if isinstance(checks, dict) else {}
    elapsed_s = max(0, int((now - first_ok).total_seconds()))
    payload["health_elapsed_s"] = elapsed_s
    if elapsed_s >= max(0, int(stability_s)):
        payload["state"] = "health_confirmed"
        payload["health_confirmed_at"] = now.isoformat()
    _atomic_write_json(path, payload)
    return payload


def mark_pending_app_update_rolled_back(path: Path, reason: str) -> dict:
    payload = load_pending_app_update(path)
    if not payload:
        raise FileNotFoundError("pending_update_marker_missing")
    payload["state"] = "rolled_back_by_guard"
    payload["rollback_reason"] = str(reason)[:700]
    payload["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(path, payload)
    return payload


def _validated_recovery_dir(payload: dict) -> Path:
    recovery = Path(str(payload.get("recovery_dir") or "")).resolve()
    if not recovery.name.startswith("app-") or recovery.parent.name != "timelapse_update_recovery":
        raise ValueError("unsafe_pending_update_recovery_dir")
    return recovery


def cleanup_pending_app_update(path: Path) -> None:
    payload = load_pending_app_update(path)
    if not payload:
        return
    recovery = _validated_recovery_dir(payload)
    # Remove recovery material first. If that fails, keep the marker so the
    # update flow remains visibly blocked instead of silently orphaning state.
    if recovery.is_dir():
        shutil.rmtree(recovery)
    path.unlink(missing_ok=True)


def write_post_restart_guard(recovery_dir: Path) -> Path:
    """Persist a guard built from the known-good lifecycle module already in memory."""
    recovery_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    module_path = recovery_dir / "update_lifecycle_guard.py"
    module_path.write_text(_TRUSTED_MODULE_SOURCE, encoding="utf-8")
    module_path.chmod(0o700)
    runner = recovery_dir / "run_guard.py"
    runner.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "from update_lifecycle_guard import guard_pending_app_update\n"
        "if len(sys.argv) != 2:\n"
        "    raise SystemExit(2)\n"
        "result = guard_pending_app_update(Path(sys.argv[1]))\n"
        "raise SystemExit(0 if result.get('ok') else 1)\n",
        encoding="utf-8",
    )
    runner.chmod(0o700)
    return runner


def _artifact_from_pending(payload: dict) -> dict:
    return {
        "artifact_id": str(payload.get("artifact_id") or ""),
        "source_commit": str(payload.get("source_commit") or ""),
        "version": str(payload.get("version") or ""),
        "manifest": {"outputs": [{"path": raw} for raw in payload.get("outputs", [])]},
    }


def _default_systemctl_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, check=False, capture_output=True, text=True, timeout=30)


def _report_rollback_from_restored_release(payload: dict, *, attempts: int = 3) -> bool:
    """Best-effort report using the just-restored known-good Edge client.

    Failure stays fail-closed: the local marker remains ``rolled_back_by_guard``
    and Headend is never told that the candidate release was deployed.
    """
    repo = Path(str(payload.get("repo") or "/opt/timelapse")).resolve()
    edge_dir = repo / "edge"
    if str(edge_dir) not in sys.path:
        sys.path.insert(0, str(edge_dir))
    try:
        from config.manager import ConfigManager
        from upload.headend_client import HeadendClient

        cfg_mgr = ConfigManager(edge_dir)
        cfg = cfg_mgr.load()
        client = HeadendClient(cfg, cfg_mgr)
        body = {
            "update_id": int(payload["update_id"]),
            "status": "rolled_back",
            "device_id": str(cfg.get("device", {}).get("device_id") or cfg_mgr.device_id),
            "reason": str(payload.get("rollback_reason") or "post_restart_health_timeout")[:700],
        }
        for attempt in range(max(1, attempts)):
            ok, _ = client._post("/updates/report", body)
            if ok:
                return True
            if attempt + 1 < attempts:
                time.sleep(2)
    except Exception:
        return False
    return False


def guard_pending_app_update(
    pending_path: Path,
    *,
    timeout_s: float | None = None,
    poll_s: float = 2.0,
    systemd_dir: Path = Path("/etc/systemd/system"),
    systemctl_runner=None,
    restart_service: bool = True,
    report_rollback: bool = True,
) -> dict:
    """Independent post-restart guard for an app artifact deployment.

    The guard runs outside ``timelapse-edge.service``.  A healthy candidate
    release marks the durable marker ``health_confirmed`` after its complete
    startup sequence.  If that never happens, this process restores ``prev``
    and the previous active systemd unit files, then restarts the known-good
    agent.  No shell expansion is used.
    """
    runner = systemctl_runner or _default_systemctl_runner
    payload = load_pending_app_update(pending_path)
    if not payload:
        return {"ok": True, "state": "marker_missing"}
    if payload.get("state") == "health_confirmed":
        return {"ok": True, "state": "health_confirmed"}
    if payload.get("state") == "rolled_back_by_guard":
        return {"ok": True, "state": "rolled_back_by_guard"}
    if payload.get("state") != "awaiting_restart_health":
        return {"ok": False, "state": "invalid_pending_state"}

    wait_s = float(timeout_s if timeout_s is not None else payload.get("health_timeout_s", 180))
    deadline = time.monotonic() + max(0.0, wait_s)
    while time.monotonic() < deadline:
        time.sleep(max(0.05, poll_s))
        current = load_pending_app_update(pending_path)
        if not current:
            return {"ok": True, "state": "marker_missing"}
        if current.get("state") == "health_confirmed":
            return {"ok": True, "state": "health_confirmed"}
        if current.get("state") == "rolled_back_by_guard":
            return {"ok": True, "state": "rolled_back_by_guard"}

    payload = load_pending_app_update(pending_path)
    if not payload:
        return {"ok": True, "state": "marker_missing"}
    if payload.get("state") == "health_confirmed":
        return {"ok": True, "state": "health_confirmed"}
    if payload.get("state") != "awaiting_restart_health":
        return {"ok": False, "state": "invalid_pending_state"}

    marker_repo = pending_path.parent.parent.resolve()
    configured_repo = Path(str(payload.get("repo") or "")).resolve()
    if configured_repo != marker_repo:
        raise ValueError("pending_update_repo_binding_mismatch")
    repo = marker_repo
    recovery = _validated_recovery_dir(payload)
    unit_backup = recovery / "systemd-backup"
    artifact = _artifact_from_pending(payload)

    restore_result = restore_previous_app_release(repo, artifact)

    managed_units = [str(unit) for unit in payload.get("managed_unit_files", []) if unit]
    for unit in managed_units:
        if Path(unit).name != unit:
            raise ValueError("unsafe_managed_unit_name")
        previous = unit_backup / unit
        target = systemd_dir / unit
        if previous.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(previous, target)
        elif target.exists():
            runner(["systemctl", "stop", unit])
            target.unlink()

    if managed_units:
        runner(["systemctl", "daemon-reload"])
        for unit in managed_units:
            if unit == "timelapse-edge.service":
                continue
            if (unit_backup / unit).is_file():
                runner(["systemctl", "try-restart", unit])

    payload = mark_pending_app_update_rolled_back(
        pending_path,
        "post_restart_health_timeout",
    )
    reported = False
    if report_rollback:
        reported = _report_rollback_from_restored_release(payload)
        if reported:
            payload["rollback_reported_at"] = datetime.now(timezone.utc).isoformat()
            _atomic_write_json(pending_path, payload)

    if restart_service:
        runner(["systemctl", "restart", "timelapse-edge.service"])

    if reported:
        cleanup_pending_app_update(pending_path)

    return {
        "ok": True,
        "state": "rolled_back_by_guard",
        "reported": reported,
        **restore_result,
    }


def restore_previous_app_release(repo: Path, artifact: dict | None = None) -> dict:
    """Restore the previous app release without shell expansion.

    Files present in ``prev`` are copied recursively (including dotfiles). Files
    introduced only by the current artifact are removed when that artifact's
    output list is available. The previous release receipt is restored and read
    back before success is returned.
    """
    repo = repo.resolve()
    previous = (repo / "prev").resolve()
    if not previous.is_dir():
        raise FileNotFoundError("rollback_source_missing")
    try:
        previous.relative_to(repo)
    except ValueError as exc:
        raise ValueError("rollback source escaped repository") from exc

    removed_new_files = 0
    for rel in _safe_edge_output_paths(artifact):
        current = repo / rel
        prior = previous / rel
        if prior.exists():
            continue
        if current.is_symlink() or current.is_file():
            current.unlink()
            removed_new_files += 1

    restored_files = 0
    for source in previous.rglob("*"):
        if not source.is_file():
            continue
        rel = source.relative_to(previous)
        destination = repo / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored_files += 1

    receipt_path = repo / "edge" / ".timelapse-release.json"
    previous_receipt = previous / "edge" / receipt_path.name
    receipt = None
    if previous_receipt.is_file():
        try:
            expected = json.loads(previous_receipt.read_text(encoding="utf-8"))
            actual = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("rollback_receipt_readback_failed") from exc
        if expected != actual:
            raise RuntimeError("rollback_receipt_readback_mismatch")
        receipt = actual
    else:
        receipt_path.unlink(missing_ok=True)

    return {
        "restored_files": restored_files,
        "removed_new_files": removed_new_files,
        "receipt": receipt,
    }
