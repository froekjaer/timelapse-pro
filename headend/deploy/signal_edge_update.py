import sys, json, os
sys.path.insert(0, '.')

# Læs DATABASE_URL fra plist hvis ikke sat i environment
if not os.environ.get("DATABASE_URL"):
    try:
        import subprocess
        url = subprocess.run(
            ["plutil", "-extract", "EnvironmentVariables.DATABASE_URL",
             "raw", "/Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist"],
            capture_output=True, text=True
        ).stdout.strip()
        if url:
            os.environ["DATABASE_URL"] = url
    except Exception:
        pass

from database import SessionLocal, Device

db = SessionLocal()
try:
    devices = db.query(Device).filter(Device.status == 'online').all()
    count = 0
    for d in devices:
        cfg = json.loads(d.device_config or '{}')
        cfg['update_requested'] = True
        d.device_config = json.dumps(cfg)
        count += 1
    db.commit()
    print(f'update_requested sat for {count} edge enheder')
except Exception as e:
    print(f"Fejl: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    db.close()
