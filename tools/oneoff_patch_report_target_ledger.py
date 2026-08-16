from pathlib import Path

path = Path("headend/main.py")
source = path.read_text(encoding="utf-8")

old = '''    report_device = db.query(Device).filter_by(device_id=device_id).first()
    report_inventory = db.query(DeviceInventory).filter_by(device_id=device_id).first() or DeviceInventory(device_id=device_id)
    if not _update_applies_to_device(u, report_device, report_inventory):
        raise HTTPException(status_code=403, detail="Edge er ikke autoriseret target for denne update")
'''
new = '''    authorized_target = db.query(UpdateTarget).filter_by(
        pending_update_id=u.id,
        device_id=device_id,
    ).first()
    if not authorized_target:
        resolved_target_ids = {target.device_id for target in _resolve_update_targets(db, u)}
        if device_id not in resolved_target_ids:
            raise HTTPException(status_code=403, detail="Edge er ikke autoriseret target for denne update")
'''
if source.count(old) != 1:
    raise SystemExit("report target-binding anchor mismatch; refusing to patch")
source = source.replace(old, new, 1)
path.write_text(source, encoding="utf-8")
