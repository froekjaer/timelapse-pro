from pathlib import Path

path = Path("edge/agent.py")
source = path.read_text(encoding="utf-8")

old_import = "from security               import verify_update_artifact\n"
new_import = (
    "from security               import verify_update_artifact\n"
    "from update_lifecycle       import release_receipt_matches_artifact, restore_previous_app_release\n"
)
if source.count(old_import) != 1:
    raise SystemExit("update lifecycle import anchor mismatch; refusing to patch")
source = source.replace(old_import, new_import, 1)

old_rollback_call = '''                if status == "rollback_requested":
                    log.info("Rollback anmodet for opdatering %d (%s)", uid, utype)
                    self._run_rollback(uid)
                    return
'''
new_rollback_call = '''                if status == "rollback_requested":
                    log.info("Rollback anmodet for opdatering %d (%s)", uid, utype)
                    self._run_rollback(uid, utype, update.get("artifact"))
                    return
'''
if source.count(old_rollback_call) != 1:
    raise SystemExit("rollback call anchor mismatch; refusing to patch")
source = source.replace(old_rollback_call, new_rollback_call, 1)

old_approved = '''                if status == "approved":
                    ok, reason = verify_update_artifact(update, self._cfg.get("security", {}))
                    if not ok:
                        log.error("Opdatering %d afvist af Edge trust policy: %s", uid, reason)
                        self._report_update(uid, "blocked", f"artifact_verification_failed: {reason}")
                        return
                    log.info("Udfører opdatering %d: %s", uid, utype)
                    self._run_update(uid, utype, update.get("artifact"))
                    return  # Ét ad gangen
'''
new_approved = '''                if status == "approved":
                    ok, reason = verify_update_artifact(update, self._cfg.get("security", {}))
                    if not ok:
                        log.error("Opdatering %d afvist af Edge trust policy: %s", uid, reason)
                        self._report_update(uid, "blocked", f"artifact_verification_failed: {reason}")
                        return
                    artifact = update.get("artifact")
                    receipt_path = Path("/opt/timelapse/edge/.timelapse-release.json")
                    if artifact and release_receipt_matches_artifact(receipt_path, artifact):
                        log.info(
                            "Opdatering %d er allerede installeret ifølge durable release receipt; rapporterer deployed igen",
                            uid,
                        )
                        self._report_update(uid, "deployed", "release_receipt_already_matches_artifact")
                        return
                    log.info("Udfører opdatering %d: %s", uid, utype)
                    self._run_update(uid, utype, artifact)
                    return  # Ét ad gangen
'''
if source.count(old_approved) != 1:
    raise SystemExit("approved update anchor mismatch; refusing to patch")
source = source.replace(old_approved, new_approved, 1)

rollback_start_marker = "    def _run_rollback(self, update_id: int) -> None:\n"
rollback_end_marker = "    def _send_heartbeat(self, *, check_updates: bool = True) -> None:\n"
if source.count(rollback_start_marker) != 1 or source.count(rollback_end_marker) != 1:
    raise SystemExit("rollback method scope mismatch; refusing to patch")
start = source.index(rollback_start_marker)
end = source.index(rollback_end_marker, start)
legacy = source[start:end]
for required in ('bash", "-c"', 'cp -r', 'self._report_update(update_id, "rolled_back")'):
    if required not in legacy:
        raise SystemExit(f"rollback legacy marker missing: {required}; refusing to patch")

replacement = '''    def _run_rollback(self, update_id: int, update_type: str, artifact: dict | None = None) -> None:
        """Tving rollback af en app-release via den lokale, verificerbare prev-kopi."""
        import subprocess as _sp

        if update_type in ("os_security", "os_updates"):
            log.warning("OS rollback %d afvist: offline OS-flowet lover ikke rollback", update_id)
            self._report_update(update_id, "blocked", "os_forced_rollback_not_supported")
            return

        try:
            result = restore_previous_app_release(Path("/opt/timelapse"), artifact)
        except FileNotFoundError:
            log.warning("Ingen forrige app-version til rollback")
            self._report_update(update_id, "blocked", "rollback_source_missing")
            return
        except Exception as exc:
            log.warning("Tvungen rollback %d fejlede: %s", update_id, exc)
            self._report_update(update_id, "blocked", f"forced_rollback_failed: {str(exc)[:500]}")
            return

        log.info(
            "Rollback til forrige app-version gennemført: restored=%s removed_new=%s",
            result.get("restored_files"),
            result.get("removed_new_files"),
        )
        self._report_update(update_id, "rolled_back")
        _sp.Popen(["systemctl", "restart", "timelapse-edge"])

'''
source = source[:start] + replacement + source[end:]
path.write_text(source, encoding="utf-8")
