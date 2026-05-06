"""
TimeLapse Pro — Sprint C: Edge agent integration
=================================================
Tilføjer til edge/agent.py:
  - SSH tunnel manager integration
  - Update policy check via headend
  - API ping helper til tunnel auto-start

Kør fra roden af timelapse-pro repoet:
    python sprint_c/fix_sprint_c_agent.py
"""

from pathlib import Path

AGENT_PATH = Path("edge/agent.py")
assert AGENT_PATH.exists(), "FEJL: Kør fra roden af repoet"

content = AGENT_PATH.read_text()

# ── Guard ─────────────────────────────────────────────────────────────────
GUARD = "SshTunnelManager"
if GUARD in content:
    print("✓ SSH tunnel integration allerede tilføjet — ingen ændringer")
    exit(0)

# ── 1. SSH tunnel import tilføjes efter eksisterende imports ──────────────
OLD_IMPORT_ANCHOR = "from upload.headend_client import HeadendClient"
NEW_IMPORT = """from upload.headend_client import HeadendClient
try:
    from tunnel.ssh_manager import SshTunnelManager
    _SSH_TUNNEL_AVAILABLE = True
except ImportError:
    _SSH_TUNNEL_AVAILABLE = False"""

assert OLD_IMPORT_ANCHOR in content, "FEJL: Kunne ikke finde HeadendClient import"
content = content.replace(OLD_IMPORT_ANCHOR, NEW_IMPORT, 1)

# ── 2. SSH tunnel initialisering i __init__ ───────────────────────────────
OLD_INIT_ANCHOR = "# 3. Detect camera features (once per session)"
NEW_TUNNEL_INIT = """        # SSH tunnel manager (Sprint C)
        self._tunnel = None
        if _SSH_TUNNEL_AVAILABLE:
            try:
                self._tunnel = SshTunnelManager(self._cfg, self._api)
                self._tunnel.start()
                log.info("SSH tunnel manager initialiseret")
            except Exception as exc:
                log.warning("SSH tunnel manager fejl: %s", exc)

        # 3. Detect camera features (once per session)"""

assert OLD_INIT_ANCHOR in content, "FEJL: Kunne ikke finde init ankerpunkt"
content = content.replace(OLD_INIT_ANCHOR, NEW_TUNNEL_INIT, 1)

# ── 3. API ping helper i HeadendClient-kaldet ────────────────────────────
# Tilføj ping() metode til HeadendClient (injiceret som monkey-patch her)
OLD_API_ANCHOR = "    def _post(self, path: str, data: dict)"
NEW_PING = """    def ping(self) -> bool:
        \"\"\"Returner True hvis headend API er tilgængeligt.\"\"\"
        try:
            session = _build_session(self._cfg_mgr.api_token)
            r = session.get(
                f"{self._base_url}/api/health",
                timeout=5
            )
            return r.status_code == 200
        except Exception:
            return False

    def _post(self, path: str, data: dict)"""

HEADEND_CLIENT = Path("edge/upload/headend_client.py")
if HEADEND_CLIENT.exists():
    hc = HEADEND_CLIENT.read_text()
    if "def ping(self)" not in hc and OLD_API_ANCHOR in hc:
        hc = hc.replace(OLD_API_ANCHOR, NEW_PING, 1)
        HEADEND_CLIENT.write_text(hc)
        print(f"✓ {HEADEND_CLIENT} opdateret med ping() metode")

# ── 4. Tilføj SSH module init fil ─────────────────────────────────────────
tunnel_dir = Path("edge/tunnel")
tunnel_dir.mkdir(exist_ok=True)
(tunnel_dir / "__init__.py").write_text("# TimeLapse Pro — SSH Tunnel Module\n")

# Kopier ssh_manager.py til edge/tunnel/
ssh_src = Path("sprint_c/ssh_manager.py")
ssh_dst = Path("edge/tunnel/ssh_manager.py")
if ssh_src.exists() and not ssh_dst.exists():
    import shutil
    shutil.copy2(ssh_src, ssh_dst)
    print(f"✓ edge/tunnel/ssh_manager.py oprettet")

# ── 5. Bump version i agent.py ────────────────────────────────────────────
content = content.replace(
    "# Version  : 3.1.0",
    "# Version  : 3.2.1"
).replace(
    "# Dato     : 12. april 2026",
    "# Dato     : 06. maj 2026"
)

AGENT_PATH.write_text(content)
print(f"✓ {AGENT_PATH} opdateret med SSH tunnel integration")
print("\nHusk:")
print("  git add edge/agent.py edge/tunnel/ edge/upload/headend_client.py")
print("\nNæste: generer SSH nøglepar på Orange Pi:")
print("  mkdir -p /opt/timelapse/edge/ssh")
print("  ssh-keygen -t ed25519 -f /opt/timelapse/edge/ssh/tunnel_key -N ''")
print("  # Kopier tunnel_key.pub til headend tunnel-bruger's authorized_keys")
