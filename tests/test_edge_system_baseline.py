"""Edge system baseline: what only one Edge had is now on every Edge and in
the image (Edge1/Edge2 comparison, Peter 2026-10-04)."""
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "edge" / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


baseline = _load("timelapse_system_baseline")
bt = _load("timelapse_bt_address")
reboot = _load("timelapse_nightly_reboot")

EDGE1_SSHD = """Include /etc/ssh/sshd_config.d/*.conf
#LoginGraceTime 2m
PermitRootLogin yes
PubkeyAuthentication yes
PasswordAuthentication yes
UsePAM yes

Match User servicetekniker
    AuthorizedKeysCommand /usr/bin/python3 /opt/timelapse/edge/scripts/technician_authorized_keys.py %u
    AuthorizedKeysCommandUser nobody
    PasswordAuthentication no

Match User emergency
    PasswordAuthentication yes
"""
EDGE1_BT_UNIT = """[Service]
ExecStart=/bin/bash -c 'sleep 2 && hcitool cmd 0x3f 0x0070 A2 A4 35 C9 88 2C && hciconfig hci0 reset'
"""


def _tree(tmp_path):
    (tmp_path / "etc/ssh").mkdir(parents=True)
    (tmp_path / "etc/ssh/sshd_config").write_text(EDGE1_SSHD)
    (tmp_path / "etc/cron.d").mkdir(parents=True)
    (tmp_path / "etc/cron.d/timelapse-reboot").write_text("0 3 * * *   root   /sbin/shutdown -r now\n")
    (tmp_path / "etc/systemd/system").mkdir(parents=True)
    (tmp_path / "etc/systemd/system/bt-set-addr.service").write_text(EDGE1_BT_UNIT)
    return tmp_path


def test_sshd_hardened_globally_match_blocks_untouched(tmp_path):
    root = _tree(tmp_path)
    assert baseline.sshd(root, apply=False)["status"] == "changed"
    text = (root / "etc/ssh/sshd_config").read_text()
    head, _, tail = text.partition("Match User servicetekniker")
    assert "PermitRootLogin no" in head and "PasswordAuthentication no" in head
    assert "PermitRootLogin yes" not in text
    # Break-glass keeps its password login inside its own Match block.
    assert "Match User emergency\n    PasswordAuthentication yes" in tail
    assert baseline.sshd(root, apply=False)["status"] == "ok"            # idempotent


def test_sshd_missing_directive_inserted_before_first_match():
    out = baseline._sshd_rewrite("UsePAM yes\nMatch User x\n    PasswordAuthentication yes\n")
    assert out.index("PermitRootLogin no") < out.index("Match User x")
    assert out.index("PasswordAuthentication no") < out.index("Match User x")


def test_journald_dropin_matches_edge2(tmp_path):
    assert baseline.journald(tmp_path, apply=False)["status"] == "changed"
    text = (tmp_path / baseline.JOURNALD_DROPIN).read_text()
    for line in ("Storage=volatile", "Compress=yes", "RateLimitIntervalSec=30s", "RateLimitBurst=10000"):
        assert line in text
    assert baseline.journald(tmp_path, apply=False)["status"] == "ok"


def test_legacy_cron_reboots_removed_and_crontab_pattern(tmp_path):
    root = _tree(tmp_path)
    assert baseline.legacy_reboot_cron(root, apply=False)["removed"] == ["etc/cron.d/timelapse-reboot"]
    assert baseline.CRON_REBOOT_LINE.match("0 4 * * * /sbin/reboot")
    assert not baseline.CRON_REBOOT_LINE.match("*/5 * * * * /usr/bin/backup")


def test_edge1_bt_address_migrated_so_pairings_survive(tmp_path):
    root = _tree(tmp_path)
    result = baseline.migrate_bt_address(root, apply=False)
    assert result["address"] == "2C:88:C9:35:A4:A2"                  # Edge1's live hciconfig value
    assert (root / "etc/timelapse/bt-address").read_text().strip() == "2C:88:C9:35:A4:A2"
    assert not (root / "etc/systemd/system/bt-set-addr.service").exists()


def test_bt_address_derivation_and_vendor_command():
    a = bt.derive_address("TL-043EB9E72EFD")
    assert a == bt.derive_address("TL-043EB9E72EFD") != bt.derive_address("TL-C87FF9587CA0")
    first = int(a.split(":")[0], 16)
    assert first & 0x02 and not first & 0x01                         # locally administered unicast
    assert a != bt.VENDOR_PLACEHOLDER
    assert bt.vendor_command("2C:88:C9:35:A4:A2")[4:] == ["A2", "A4", "35", "C9", "88", "2C"]


def test_nightly_reboot_decisions():
    cfg = {"system": {"nightly_reboot": {"enabled": True, "time": "03:00", "window_minutes": 30, "min_uptime_hours": 6}}}
    at = datetime(2026, 10, 5, 3, 10)
    assert reboot.decide(cfg, at, 20, False, False) == (True, "reboot")
    assert reboot.decide(cfg, datetime(2026, 10, 5, 3, 40), 20, False, False)[1] == "outside_window"
    assert reboot.decide(cfg, at, 1, False, False)[1] == "recently_booted"
    assert reboot.decide(cfg, at, 20, True, False)[1] == "update_pending"
    assert reboot.decide(cfg, at, 20, False, True)[1] == "technician_session_active"
    # UI dropdowns store strings — "false" must disable it.
    off = {"system": {"nightly_reboot": {"enabled": "false", "window_minutes": "30"}}}
    assert reboot.decide(off, at, 20, False, False)[1] == "disabled"
    # Defaults when the Headend has not sent the section yet.
    assert reboot.decide({}, at, 20, False, False) == (True, "reboot")
    # Window crossing midnight.
    assert reboot.in_window(datetime(2026, 10, 5, 0, 10), "23:50", 30)


def test_agent_manages_the_units_and_they_exist():
    src = (ROOT / "edge" / "agent.py").read_text(encoding="utf-8")
    units = (ROOT / "edge" / "managed_units.py").read_text(encoding="utf-8")
    for unit in ("timelapse-watchdog.service", "timelapse-system-baseline.service", "timelapse-bt-address.service",
                 "timelapse-nightly-reboot.service", "timelapse-nightly-reboot.timer"):
        assert f'"{unit}"' in units
        assert (SCRIPTS / unit).is_file()
    assert 'TIMER_DRIVEN_UNITS = frozenset({"timelapse-nightly-reboot.service"})' in units
    assert "from managed_units import MANAGED_UNITS, TIMER_DRIVEN_UNITS" in src
    for script in ("timelapse_system_baseline.py", "timelapse_bt_address.py", "timelapse_nightly_reboot.py"):
        assert f'"edge/scripts/{script}"' in src


def test_image_builder_ships_and_enables_the_same_units():
    docker = (ROOT / "headend/tools/Dockerfile.edge").read_text(encoding="utf-8")
    inject = (ROOT / "headend/tools/inject_edge_image.py").read_text(encoding="utf-8")
    for unit in ("timelapse-timesync.timer", "timelapse-watchdog.service", "timelapse-system-baseline.service",
                 "timelapse-bt-address.service", "timelapse-nightly-reboot.timer"):
        assert unit in docker and f'"etc/systemd/system/{unit}"' in inject
    assert "for UNIT in timelapse-timesync.timer timelapse-nightly-reboot.timer" in inject
    assert ": > /mnt/root/etc/machine-id" in inject


def test_headend_default_and_ui_fields():
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    assert '"nightly_reboot": {"enabled": True, "time": "03:00", "window_minutes": 30, "min_uptime_hours": 6}' in main
    ui = (ROOT / "timelapse-ui/src/pages/GlobalConfigPage.tsx").read_text(encoding="utf-8")
    assert "key: 'nightly_reboot.time'" in ui and "options: NIGHTLY_REBOOT_TIMES" in ui
    cam = (ROOT / "timelapse-ui/src/pages/CameraPage.tsx").read_text(encoding="utf-8")
    assert "key: 'system.nightly_reboot.enabled'" in cam


def test_inventory_reports_our_timers_and_the_real_watchdog_name(monkeypatch):
    sys.path.insert(0, str(ROOT / "edge"))
    from utils import inventory
    from types import SimpleNamespace

    def fake_run(cmd, **_kw):
        if "--type=timer" in cmd:
            return SimpleNamespace(returncode=0, stdout="apt-daily.timer enabled enabled\ntimelapse-nightly-reboot.timer enabled enabled\n")
        return SimpleNamespace(returncode=0, stdout="timelapse-watchdog.service enabled enabled\n")

    monkeypatch.setattr(inventory.subprocess, "run", fake_run)
    assert inventory._enabled_service_names() == ["timelapse-nightly-reboot.timer", "timelapse-watchdog.service"]
    assert "timelapse-watchdog.service" in inventory._TRACKED_SERVICES
    assert "timelapse-edge-watchdog.service" not in inventory._TRACKED_SERVICES
