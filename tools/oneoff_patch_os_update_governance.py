from pathlib import Path

cmdb_path = Path("headend/cmdb.py")
cmdb = cmdb_path.read_text(encoding="utf-8")
start = cmdb.index("def _sync_edge_os_updates(")
end = cmdb.index("\n\n# ── Kryptering", start)
section = cmdb[start:end]
required = [
    'PendingUpdate.status.in_(["pending", "approved"])',
    'status="pending"',
    'Installér via Headend-signeret offline OS bundle.',
]
missing = [needle for needle in required if needle not in section]
if missing:
    raise SystemExit(f"CMDB legacy governance markers missing: {missing}; refusing to patch")
section = section.replace(
    'PendingUpdate.status.in_(["pending", "approved"])',
    'PendingUpdate.status.in_(["blocked", "pending"])',
)
section = section.replace(
    'f"Installér via Headend-signeret offline OS bundle."',
    'f"CMDB observation — ikke deployable. Opret/verificér lab-katalog og build-plan før Headend-signeret offline OS bundle."',
)
section = section.replace('status="pending",', 'status="blocked",')
section = section.replace(
    '            existing.environment = env\n',
    '            existing.environment = env\n            existing.status = "blocked"\n',
)
cmdb = cmdb[:start] + section + cmdb[end:]
cmdb_path.write_text(cmdb, encoding="utf-8")

main_path = Path("headend/main.py")
main = main_path.read_text(encoding="utf-8")
fn_start = main.index("def _os_bundle_auto_build_pending()")
fn_end = main.index("\ndef _auto_build_and_bind_os_bundle(", fn_start)
fn = main[fn_start:fn_end]
anchor = '''            device_id = (update.scope_id or "").strip()
            if not device_id:
                log.debug("OS bundle auto-poller: update #%d har ingen scope_id — springer over", update.id)
                continue

            log.info(
'''
replacement = '''            device_id = (update.scope_id or "").strip()
            if not device_id:
                log.debug("OS bundle auto-poller: update #%d har ingen scope_id — springer over", update.id)
                continue

            plan_path = _plan_path_for_update(update)
            if not plan_path:
                log.warning(
                    "OS bundle auto-poller: update #%d mangler lab build-plan evidence — bygger ikke",
                    update.id,
                )
                continue

            log.info(
'''
if fn.count(anchor) != 1:
    raise SystemExit("auto-builder scoped anchor mismatch; refusing to patch")
fn = fn.replace(anchor, replacement)
main = main[:fn_start] + fn + main[fn_end:]
main_path.write_text(main, encoding="utf-8")
