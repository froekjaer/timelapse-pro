from pathlib import Path

path = Path("headend/main.py")
source = path.read_text(encoding="utf-8")

old_import = "from services.update_supersession import supersede_pending_app_updates\n"
new_import = old_import + "from services.update_authority import update_applies_to_device as _update_applies_to_device\n"
if source.count(old_import) != 1:
    raise SystemExit("update authority import anchor mismatch; refusing to patch")
source = source.replace(old_import, new_import, 1)

old_helper = '''def _parse_target_device_ids(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(v) for v in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def _update_applies_to_device(update: PendingUpdate, device: Device | None, inv: DeviceInventory) -> bool:
    target_ids = _parse_target_device_ids(update.target_device_ids)
    if target_ids:
        return inv.device_id in target_ids
    if update.scope == "global":
        return True
    if update.scope == "device":
        return update.scope_id == inv.device_id
    if update.scope == "customer" and device:
        return update.scope_id == device.customer_id
    if update.scope == "site" and device:
        return update.scope_id == device.site_id
    return False


'''
if source.count(old_helper) != 1:
    raise SystemExit("legacy update applicability helper anchor mismatch; refusing to patch")
source = source.replace(old_helper, "", 1)

old_policy = '''    # Find godkendte opdateringer til denne enhed
    from database import PendingUpdate as _PU
    from sqlalchemy import or_
    approved = db.query(_PU).filter(
        _PU.status.in_(["approved", "rollback_requested"]),
        or_(_PU.scope == "global", _PU.scope_id == device_id)
    ).all()

    filtered = []
    for u in approved:
        if u.target_device_ids:
            targets = json.loads(u.target_device_ids)
            if device_id not in targets:
                continue
'''
new_policy = '''    # Find godkendte opdateringer til denne enhed via samme canonical authority predicate
    from database import PendingUpdate as _PU
    inventory = db.query(DeviceInventory).filter_by(device_id=device_id).first() or DeviceInventory(device_id=device_id)
    approved = db.query(_PU).filter(_PU.status.in_(["approved", "rollback_requested"])).all()

    filtered = []
    for u in approved:
        if not _update_applies_to_device(u, device, inventory):
            continue
'''
if source.count(old_policy) != 1:
    raise SystemExit("update policy selection anchor mismatch; refusing to patch")
source = source.replace(old_policy, new_policy, 1)

old_report = '''    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if reason and status in final_statuses:
'''
new_report = '''    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    report_device = db.query(Device).filter_by(device_id=device_id).first()
    report_inventory = db.query(DeviceInventory).filter_by(device_id=device_id).first() or DeviceInventory(device_id=device_id)
    if not _update_applies_to_device(u, report_device, report_inventory):
        raise HTTPException(status_code=403, detail="Edge er ikke autoriseret target for denne update")
    if reason and status in final_statuses:
'''
if source.count(old_report) != 1:
    raise SystemExit("update report target-binding anchor mismatch; refusing to patch")
source = source.replace(old_report, new_report, 1)

path.write_text(source, encoding="utf-8")
