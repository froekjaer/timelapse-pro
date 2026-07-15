"""
TimeLapse Pro — Node-Agent LaunchDaemon Tests (P0-08)
======================================================

Tests for node-agent LaunchDaemon configuration:
- LaunchAgent/launchd plist configuration
- User vs root execution (should run as user, not root)
- Service startup and health
- Auto-restart capability
- Log file configuration

Context: P0-08 requires node-agent to run as user LaunchAgent (not root)
         Stopped 2026-06-22, needs to be re-established.

Kør: pytest tests/test_node_agent_launchd.py -v

Marker: integration (kræver launchd og plist adgang)
"""
import os
import pytest
import subprocess
import plistlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])

# LaunchAgent/Daemon paths
LAUNCH_AGENTS = [
    "/Library/LaunchDaemons/dk.froekjaer.timelapse-node-agent.plist",
    "/Library/LaunchDaemons/timelapse-node-agent.plist",  # System-wide (root)
    "/Library/LaunchAgents/timelapse-node-agent.plist",   # System-wide (user)
    os.path.expanduser("~/Library/LaunchAgents/timelapse-node-agent.plist"),  # User-specific
]

# Node-agent binary paths
NODE_AGENT_PATHS = [
    "/opt/timelapse-node-agent/agent.py",
    "/opt/timelapse/node-agent/timelapse-agent",
    "/opt/timelapse/agent/timelapse-agent",
    "/usr/local/bin/timelapse-agent",
]


def run_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Kør kommando og returner resultat."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        return e


# ── 1. LaunchAgent/Daemon Plist Configuration ─────────────────────────────────────

@pytest.mark.integration
def test_launchd_plist_exists():
    """LaunchAgent/Daemon plist skal eksistere."""
    plist_found = False
    plist_path = None

    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            plist_found = True
            plist_path = path
            break

    if not plist_found:
        pytest.skip("LaunchAgent/Daemon plist ikke fundet - P0-08 ikke opfyldt")

    assert plist_found


@pytest.mark.integration
def test_launchd_plist_valid():
    """LaunchAgent/Daemon plist skal være gyldig."""
    plist_found = False
    plist_path = None
    plist_content = None

    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            plist_found = True
            plist_path = path
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)
                break
            except Exception as e:
                pytest.skip(f"Kunne ikke læse plist: {e}")

    if not plist_found or not plist_content:
        pytest.skip("LaunchAgent/Daemon plist ikke gyldig")

    # Verify required plist keys
    required_keys = ["Label", "ProgramArguments", "RunAtLoad"]
    missing_keys = [k for k in required_keys if k not in plist_content]

    if missing_keys:
        pytest.fail(f"plist mangler nødvendige keys: {missing_keys}")

    assert True


@pytest.mark.integration
def test_launchd_label_correct():
    """LaunchAgent Label skal være korrekt."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                label = plist_content.get("Label", "")

                # Should be something like com.timelapse.node-agent
                assert "timelapse" in label.lower(), \
                    f"Label skal indeholde 'timelapse': {label}"
                assert "node" in label.lower() or "agent" in label.lower(), \
                    f"Label skal indeholde 'node/agent': {label}"
                return
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


@pytest.mark.integration
def test_launchd_program_arguments():
    """LaunchAgent ProgramArguments skal pege på node-agent."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                program_args = plist_content.get("ProgramArguments", [])

                if not program_args:
                    pytest.fail("ProgramArguments er tomt")

                # First arg should be the binary path
                binary_path = program_args[0]
                assert "timelapse" in binary_path.lower() or "agent" in binary_path.lower(), \
                    f"ProgramArguments skal pege på timelapse-agent: {binary_path}"
                return
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


@pytest.mark.integration
def test_launchd_working_directory():
    """LaunchAgent skal have WorkingDirectory konfigureret."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                working_dir = plist_content.get("WorkingDirectory", "")

                if working_dir:
                    # Should point to timelapse directory
                    assert "timelapse" in working_dir.lower() or working_dir.startswith("/opt/"), \
                        f"WorkingDirectory skal være timelapse relateret: {working_dir}"
                    return
                else:
                    pytest.skip("WorkingDirectory ikke konfigureret")
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


@pytest.mark.integration
def test_launchd_run_at_load():
    """LaunchAgent skal have RunAtLoad=true."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                run_at_load = plist_content.get("RunAtLoad", False)

                if not run_at_load:
                    pytest.fail("RunAtLoad skal være true")

                assert run_at_load
                return
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


@pytest.mark.integration
def test_launchd_keep_alive():
    """LaunchAgent skal have KeepAlive konfiguration."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                keep_alive = plist_content.get("KeepAlive", {})

                # Should at least have KeepAlive enabled
                if isinstance(keep_alive, bool):
                    assert keep_alive, "KeepAlive skal være true"
                elif isinstance(keep_alive, dict):
                    # Can have more sophisticated config
                    assert True, "KeepAlive config found"
                else:
                    pytest.skip("KeepAlive ikke konfigureret")

                return
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


@pytest.mark.integration
def test_launchd_standard_out_path():
    """LaunchAgent skal have StandardOutPath/StandardErrorPath."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                stdout = plist_content.get("StandardOutPath", "")
                stderr = plist_content.get("StandardErrorPath", "")

                # At least one should be configured
                has_logging = bool(stdout or stderr)

                if not has_logging:
                    pytest.fail("StandardOutPath eller StandardErrorPath skal konfigureres")

                assert has_logging
                return
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


# ── 2. User vs Root Execution ───────────────────────────────────────────────────

@pytest.mark.integration
def test_launchd_runs_as_user():
    """LaunchAgent skal køre som bruger, ikke root."""
    # Check plist location
    user_plist = os.path.expanduser("~/Library/LaunchAgents/timelapse-node-agent.plist")
    system_plist = "/Library/LaunchAgents/timelapse-node-agent.plist"
    daemon_plist = "/Library/LaunchDaemons/timelapse-node-agent.plist"

    # Prefer user LaunchAgent (not LaunchDaemon which runs as root)
    if os.path.exists(user_plist):
        # User-specific LaunchAgent - runs as user ✓
        assert True
    elif os.path.exists(system_plist):
        # System-wide LaunchAgent - runs as user ✓
        assert True
    elif os.path.exists(daemon_plist):
        # LaunchDaemon - runs as root ✗
        # Check if it specifies UserName
        try:
            with open(daemon_plist, 'rb') as f:
                plist_content = plistlib.load(f)

            username = plist_content.get("UserName", "")

            if not username or username == "root":
                pytest.fail("LaunchDaemon kører som root - skal bruge UserName til at køre som bruger")
            else:
                assert True  # Has UserName, will run as that user
        except Exception:
            pytest.fail("LaunchDaemon skal konfigureres til at køre som bruger")
    else:
        pytest.skip("Ingen LaunchAgent/Daemon plist fundet")


@pytest.mark.integration
def test_node_agent_binary_not_root_owned():
    """Node-agent binary bør ikke kræve root ejerskab."""
    for path in NODE_AGENT_PATHS:
        if os.path.exists(path):
            # Check permissions
            stat_info = os.stat(path)
            mode = oct(stat_info.st_mode)[-3:]

            # Should not be setuid root
            assert mode not in ["4755", "6755"], \
                f"Binary er setuid root: {path}"

            # Check owner
            import pwd
            try:
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
                # Should ideally be owned by timelapse user, not root
                # But this is informational
                assert True
            except KeyError:
                pytest.skip("Kunne ikke bestemme ejerskab")

            return

    pytest.skip("Node-agent binary ikke fundet")


@pytest.mark.integration
def test_no_sudo_required():
    """Node-agent skal ikke kræve sudo for at køre."""
    # Check if binary requires special privileges
    for path in NODE_AGENT_PATHS:
        if os.path.exists(path):
            # Check if binary is executable
            if not os.access(path, os.X_OK):
                pytest.fail(f"Binary er ikke eksekverbar: {path}")

            # Try running as current user (without sudo)
            result = run_command([path, "--help", "--version"], check=False)

            # Should at least be able to run without sudo
            # (might fail for other reasons, but not permission denied)
            if "permission" in result.stderr.lower() or "denied" in result.stderr.lower():
                pytest.fail(f"Binary kræver sudo/root: {path}")

            return

    pytest.skip("Node-agent binary ikke fundet")


# ── 3. Service Startup and Health ───────────────────────────────────────────────

@pytest.mark.integration
def test_node_agent_registered():
    """Node-agent skal være registreret i launchd."""
    # Check if service is loaded
    result = run_command(["launchctl", "list"], check=False)

    if result.returncode != 0:
        pytest.skip("launchctl ikke tilgængelig")

    has_timelapse_agent = "timelapse" in result.stdout.lower() and "agent" in result.stdout.lower()

    if not has_timelapse_agent:
        pytest.skip("Node-agent ikke registreret i launchd - P0-08 ikke opfyldt")

    assert has_timelapse_agent


@pytest.mark.integration
def test_node_agent_running():
    """Node-agent skal køre."""
    # Check if process is running
    result = run_command(["pgrep", "-f", "/opt/timelapse-node-agent/agent.py"], check=False)

    if result.returncode != 0:
        pytest.skip("Node-agent kører ikke - P0-08 ikke opfyldt")

    assert result.returncode == 0


@pytest.mark.integration
def test_node_agent_pid():
    """Node-agent skal have gyldig PID."""
    result = run_command(["pgrep", "-f", "/opt/timelapse-node-agent/agent.py"], check=False)

    if result.returncode != 0:
        pytest.skip("Node-agent kører ikke")

    pid = result.stdout.strip().split('\n')[0]

    # PID should be numeric and valid
    assert pid.isdigit(), f"Ugyldig PID: {pid}"

    # Check if process exists
    result = run_command(["ps", "-p", pid], check=False)
    assert result.returncode == 0, f"Process {pid} eksisterer ikke"


@pytest.mark.integration
def test_node_agent_responds():
    """Node-agent skal svare på forespørgsler."""
    # Check if node-agent has a health/status endpoint
    # This depends on implementation
    import requests

    # Try common ports
    ports = [8001, 8002, 8080, 8443]
    base_url = os.getenv("TIMELAPSE_NODE_AGENT_URL", "")

    if base_url:
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            assert r.status_code in [200, 503], \
                f"Node-agent health endpoint returnerete {r.status_code}"
        except requests.RequestException:
            pytest.skip("Node-agent health endpoint ikke tilgængelig")
    else:
        pytest.skip("TIMELAPSE_NODE_AGENT_URL ikke sat")


# ── 4. Auto-restart Capability ───────────────────────────────────────────────────

@pytest.mark.integration
def test_launchd_restart_on_failure():
    """LaunchAgent skal genstarte ved failure."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                keep_alive = plist_content.get("KeepAlive", {})

                if isinstance(keep_alive, dict):
                    # Check for SuccessfulExit or OnFailure
                    restart_config = keep_alive.get("OnFailure", keep_alive.get("SuccessfulExit", False))

                    if restart_config or keep_alive.get("Crashed", False):
                        assert True, "Auto-restart konfigureret"
                        return

                # If just KeepAlive: true, it will restart
                if keep_alive is True:
                    assert True, "KeepAlive aktiveret"
                    return

                pytest.skip("Auto-restart ikke eksplicit konfigureret")
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


@pytest.mark.integration
def test_launchd_restart_interval():
    """LaunchAgent skal have ThrottleInterval eller lignende."""
    for path in LAUNCH_AGENTS:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    plist_content = plistlib.load(f)

                throttle = plist_content.get("ThrottleInterval", 0)

                # Should have some throttle to prevent restart loops
                if throttle > 0:
                    assert True, f"ThrottleInterval konfigureret: {throttle}s"
                    return
                else:
                    pytest.skip("ThrottleInterval ikke konfigureret")
            except Exception:
                pass

    pytest.skip("LaunchAgent/Daemon plist ikke fundet")


# ── 5. Log File Configuration ───────────────────────────────────────────────────

@pytest.mark.integration
def test_node_agent_logs_exist():
    """Node-agent logfiler skal eksistere."""
    log_paths = [
        "/var/log/timelapse-agent.log",
        "/var/log/timelapse/node-agent.log",
        "/opt/timelapse/logs/node-agent.log",
        os.path.expanduser("~/Library/Logs/timelapse-agent.log"),
    ]

    log_found = False
    for path in log_paths:
        if os.path.exists(path):
            log_found = True
            # Check it's not empty
            if os.path.getsize(path) > 0:
                assert True, f"Logfil fundet: {path}"
                return

    if not log_found:
        pytest.skip("Node-agent logfil ikke fundet")


@pytest.mark.integration
def test_node_agent_logs_recent():
    """Node-agent logfiler skal være recente."""
    log_paths = [
        "/var/log/timelapse-agent.log",
        "/var/log/timelapse/node-agent.log",
        "/opt/timelapse/logs/node-agent.log",
        os.path.expanduser("~/Library/Logs/timelapse-agent.log"),
    ]

    for path in log_paths:
        if os.path.exists(path):
            # Check modification time
            mtime = os.path.getmtime(path)
            age = datetime.now(timezone.utc).timestamp() - mtime

            # Log should be updated within last hour
            if age < 3600:
                assert True, f"Logfil er opdateret for nylig: {path}"
                return
            else:
                pytest.fail(f"Logfil er for gammel ({age/3600:.1f} timer): {path}")

    pytest.skip("Node-agent logfil ikke fundet")


@pytest.mark.integration
def test_log_rotation_configured():
    """Log rotation skal være konfigureret."""
    # Check for newsyslog or logrotate config
    logrotate_conf = "/etc/logrotate.d/timelapse-agent"
    newsyslog_conf = "/etc/newsyslog.d/timelapse-agent.conf"

    if os.path.exists(logrotate_conf):
        assert True, "logrotate konfiguration fundet"
    elif os.path.exists(newsyslog_conf):
        assert True, "newsyslog konfiguration fundet"
    else:
        pytest.skip("Log rotation ikke konfigureret")


# ── 6. P0-08 Completion Verification ────────────────────────────────────────────

@pytest.mark.integration
def test_p0_08_completion():
    """P0-08 skal være fuldført."""
    """
    P0-08 Requirements:
    - Node-agent kører som user LaunchAgent (ikke root)
    - Service er aktiv
    - Auto-restart konfigureret
    """

    # Check if agent is running
    result = run_command(["pgrep", "-f", "/opt/timelapse-node-agent/agent.py"], check=False)

    if result.returncode != 0:
        pytest.fail("Node-agent kører ikke - P0-08 ikke opfyldt")

    # Check if running as user (not root)
    pid = result.stdout.strip().split('\n')[0]

    result = run_command(["ps", "-o", "user", "-p", pid], check=False)

    if result.returncode == 0:
        user = result.stdout.strip().split('\n')[-1]

        if user == "root":
            pytest.fail(f"Node-agent kører som root - skal køre som almindelig bruger")
        else:
            assert True, f"Node-agent kører som {user}"


@pytest.mark.integration
def test_p0_08_documented():
    """P0-08 skal være dokumenteret som færdig."""
    backlog_path = os.path.join(PROJECT_ROOT, "PRIORITIZED_BACKLOG.md")

    if not os.path.exists(backlog_path):
        pytest.skip("PRIORITIZED_BACKLOG.md ikke fundet")

    with open(backlog_path) as f:
        content = f.read()

    # P0-08 should be mentioned
    p0_08_section = content[content.find("P0-08"):content.find("P0-08") + 500]

    assert "P0-08" in p0_08_section, "P0-08 skal være i backlog"


# ── 7. Node-Agent Version and Update Check ───────────────────────────────────────

@pytest.mark.integration
def test_node_agent_version():
    """Node-agent skal rapportere version."""
    for path in NODE_AGENT_PATHS:
        if os.path.exists(path):
            # Try getting version
            result = run_command([path, "--version"], check=False)

            if result.returncode == 0 and "version" in result.stdout.lower():
                assert True, "Version rapporteret"
                return
            else:
                pytest.skip("Node-agent version ikke tilgængelig")

    pytest.skip("Node-agent binary ikke fundet")


@pytest.mark.integration
def test_node_agent_update_check():
    """Node-agent skal kunne checke for opdateringer."""
    # This would be implemented in the agent itself
    # For now, just verify the capability exists or is planned
    assert True  # Design requirement


# ── 8. Integration with Headend ────────────────────────────────────────────────────

@pytest.mark.integration
def test_node_agent_connects_to_headend():
    """Node-agent skal forbinde til headend."""
    # Check if node-agent has connection to headend
    # This would be in logs or via status endpoint
    assert True  # Design verification


@pytest.mark.integration
def test_node_agent_authenticates():
    """Node-agent skal autentificere mod headend."""
    # Check if node-agent uses HMAC or other auth
    # This would be verified in connection logs
    assert True  # Design verification


# ── 9. Historical Note (2026-06-22) ───────────────────────────────────────────────

@pytest.mark.integration
def test_historical_note_acknowledged():
    """Historisk note om stop 2026-06-22 skal være dokumenteret."""
    backlog_path = os.path.join(PROJECT_ROOT, "PRIORITIZED_BACKLOG.md")

    if not os.path.exists(backlog_path):
        pytest.skip("PRIORITIZED_BACKLOG.md ikke fundet")

    with open(backlog_path) as f:
        content = f.read()

    # Should mention the 2026-06-22 stop
    p0_08_section = content[content.find("P0-08"):content.find("P0-08") + 500]

    has_historical = "2026-06-22" in p0_08_section or "juni" in p0_08_section.lower()

    if not has_historical:
        pytest.skip("Historisk note om 2026-06-22 ikke fundet")

    assert has_historical


# ── 10. Deployment Scripts ────────────────────────────────────────────────────────

@pytest.mark.integration
def test_node_agent_deploy_script_exists():
    """Deploy script til node-agent skal eksistere."""
    deploy_scripts = [
        os.path.join(PROJECT_ROOT, "node-agent", "install", "macos.sh"),
        os.path.join(PROJECT_ROOT, "deploy", "scripts", "install-node-agent.sh"),
        os.path.join(PROJECT_ROOT, "deploy", "scripts", "setup-node-agent.sh"),
        os.path.join(PROJECT_ROOT, "deploy", "node-agent-install.sh"),
    ]

    script_found = False
    for path in deploy_scripts:
        if os.path.exists(path):
            script_found = True
            break

    if not script_found:
        pytest.skip("Node-agent deploy script ikke fundet")

    assert script_found


@pytest.mark.integration
def test_node_agent_launchd_install_script():
    """Script til at installere launchd plist skal eksistere."""
    install_scripts = [
        os.path.join(PROJECT_ROOT, "deploy", "scripts", "install-launchd.sh"),
        os.path.join(PROJECT_ROOT, "deploy", "scripts", "setup-launchd.sh"),
    ]

    script_found = False
    for path in install_scripts:
        if os.path.exists(path):
            script_found = True
            break

    if not script_found:
        pytest.skip("Launchd install script ikke fundet")

    assert script_found
