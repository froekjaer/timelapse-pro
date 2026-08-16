from pathlib import Path

path = Path("edge/upload/headend_client.py")
source = path.read_text(encoding="utf-8")

backup_scope = source.index("    def upload_edge_backup(")
backup_end = source.index("    def notify_tunnel_ready(", backup_scope)
backup = source[backup_scope:backup_end]
old_session = '''            session = requests.Session()
            session.headers["Authorization"] = f"Bearer {self._cfg_mgr.api_token}"
            session.headers["User-Agent"] = "TimeLapsePro-EdgeAgent/1.0"
            session.headers.pop("Content-Type", None)
'''
new_session = '''            session = _build_session(self._cfg_mgr.api_token)
            session.headers.pop("Content-Type", None)
'''
if backup.count(old_session) != 1:
    raise SystemExit("backup session legacy block not found exactly once; refusing to patch")
backup = backup.replace(old_session, new_session)
source = source[:backup_scope] + backup + source[backup_end:]

ping_scope = source.index("    def ping(")
ping_end = source.index("    def _post(", ping_scope)
ping = source[ping_scope:ping_end]
old_health = '            r = session.get(f"{self._base_url}/api/health", timeout=5)\n'
new_health = '            r = session.get(f"{self._base_url}/health", timeout=5)\n'
if ping.count(old_health) != 1:
    raise SystemExit("legacy ping health URL not found exactly once; refusing to patch")
ping = ping.replace(old_health, new_health)
source = source[:ping_scope] + ping + source[ping_end:]

path.write_text(source, encoding="utf-8")
