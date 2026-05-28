#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Node Agent
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.0.0
# Dato     : 2026-05-11
# ───────────────────────────────────────────────────────────────────────────
# Universel agent der kører på ALLE noder (edge + headend).
# Samler hardware-inventar og security events og poster til headend.
#
# Kørsel:
#   python3 agent.py --config /etc/timelapse/node-agent.conf
#
# Installeres som:
#   Linux  : systemd service (via install/linux.sh)
#   macOS  : launchd plist   (via install/macos.sh)
# ═══════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from config import NodeAgentConfig
from collectors.inventory import collect_inventory
from collectors.security import collect_security_events
from collectors.updates import collect_available_updates
from transport import post_available_updates, post_inventory, post_security_events

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)-30s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("node-agent")

# ── Graceful shutdown ─────────────────────────────────────────────────────
_running = True

def _handle_signal(sig, frame):
    global _running
    log.info("Signal %s modtaget — lukker ned", sig)
    _running = False

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ── Hovedloop ─────────────────────────────────────────────────────────────

def run(cfg: NodeAgentConfig) -> None:
    log.info("Node Agent starter — device_id=%s headend=%s",
             cfg.device_id, cfg.headend_url)

    # Første kørsel sker straks ved startup
    last_inventory = 0.0
    last_security  = 0.0

    while _running:
        now = time.time()

        # ── Inventar (hvert inventory_interval sekunder) ──────────────────
        if now - last_inventory >= cfg.inventory_interval:
            try:
                log.info("Samler inventar...")
                inv = collect_inventory(cfg)
                ok, msg = post_inventory(cfg, inv)
                if ok:
                    log.info("Inventar rapporteret OK")
                else:
                    log.warning("Inventar-rapportering fejlede: %s", msg)
                updates = collect_available_updates(cfg)
                if updates.get("os_security_count") or updates.get("os_updates_count"):
                    ok, msg = post_available_updates(cfg, updates)
                    if ok:
                        log.info("Update-status rapporteret OK: os_security=%s os_updates=%s",
                                 updates.get("os_security_count"), updates.get("os_updates_count"))
                    else:
                        log.warning("Update-status rapportering fejlede: %s", msg)
            except Exception as e:
                log.warning("Inventar-fejl (uventet): %s", e)
            last_inventory = now

        # ── Security events (hvert security_interval sekunder) ────────────
        if now - last_security >= cfg.security_interval:
            try:
                events = collect_security_events(cfg)
                if events:
                    log.info("Poster %d security events", len(events))
                    ok, msg = post_security_events(cfg, events)
                    if not ok:
                        log.warning("Security events fejlede: %s", msg)
                else:
                    log.debug("Ingen nye security events")
            except Exception as e:
                log.warning("Security-fejl (uventet): %s", e)
            last_security = now

        # Sov 10 sekunder ad gangen (responsiv til shutdown)
        for _ in range(10):
            if not _running:
                break
            time.sleep(1)

    log.info("Node Agent stoppet")


# ── Entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TimeLapse Pro Node Agent")
    parser.add_argument(
        "--config", "-c",
        default="/etc/timelapse/node-agent.conf",
        help="Sti til konfigurationsfil"
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Konfigurationsfil ikke fundet: %s", config_path)
        log.error("Opret den med install/linux.sh eller install/macos.sh")
        sys.exit(1)

    cfg = NodeAgentConfig.load(config_path)
    run(cfg)
