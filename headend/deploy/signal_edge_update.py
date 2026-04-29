import sys, json
sys.path.insert(0, '.')
from database import SessionLocal, Device

db = SessionLocal()
devices = db.query(Device).filter(Device.status == 'online').all()
count = 0
for d in devices:
    cfg = json.loads(d.device_config or '{}')
    cfg['update_requested'] = True
    d.device_config = json.dumps(cfg)
    count += 1
db.commit()
db.close()
print(f'update_requested sat for {count} edge enheder')
