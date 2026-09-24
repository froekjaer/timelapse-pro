#!/usr/bin/env python3
"""Idempotent GRC-registrering af Golden Edge P0/P1-lukningen (2026-09-24).

Se Dokumentation/HANDOVER_LOG.md, 2026-09-24-entry, for den fulde
evidenskæde: to uafhængige codebase-research-passer, en samtidig z.ai
fysisk-enhed-audit, og direkte SSH-verifikation mod begge fysiske edges
(TL-C87FF9587CA0 = Edge1, TL-043EB9E72EFD = Edge2), krydsverificeret mod
hinanden før noget blev registreret som fund.

Registrerer:
- REQ-KRAVREGISTER-OG-STATUS-V10-CFG-006: evidens for Bluetooth-navn PASS på Edge1
- FIND-EDGE-TOTP-PORTAL-MISSING-DEPENDENCIES-20260924 (finding, fixed via PR #257)
- FIND-EDGE-BT-MAC-ADDRESS-COLLISION-20260924 (finding, open)
- FIND-EDGE1-INSECURE-SSH-AND-PACKAGE-DRIFT-20260924 (finding, open — device drift, ikke builder)
- FIND-EDGE-BREAKGLASS-SETUP-SERVICE-MISSING-20260924 (finding, open — bevidst IKKE rettet)
- FIND-PR249-MERGED-BEFORE-PHYSICAL-TEST-RECONCILED-20260924 (finding, closed — reconciliation)

Køres mod live-DB:  DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
  .venv/bin/python3 headend/tools/import_grc_golden_edge_20260924.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402

ACTOR = "claude"
HANDOVER = "Dokumentation/HANDOVER_LOG.md"
PR249 = "https://github.com/froekjaer/timelapse-pro/pull/249"
PR257 = "https://github.com/froekjaer/timelapse-pro/pull/257"

ITEMS = [
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE-TOTP-PORTAL-MISSING-DEPENDENCIES-20260924",
        "title": "Local technician TOTP portal crash-loops on any freshly-built Edge image (fixed via PR #257)",
        "status": "closed",
        "priority": "P0",
        "description": (
            "edge/scripts/totp-service.py does top-level `import pyotp` and `from fastapi import "
            "FastAPI, ...`, and serves itself via uvicorn — none of the three were declared in "
            "edge/requirements.txt, and no pip-install step anywhere in the builder pipeline "
            "(Dockerfile.edge, inject_edge_image.py) installs them. Confirmed directly (grep of "
            "totp-service.py's imports + edge/requirements.txt's full content) — on a genuinely "
            "fresh image the service ModuleNotFoundErrors on every start and crash-loops forever "
            "(Restart=on-failure, RestartSec=5) until a post-boot app update happens to "
            "pip-install these into the persistent venv. This silently disables the entire local "
            "technician web UI (totp-service.py IS that surface). Not part of Z.ai's original "
            "12-hypothesis list — found by an independent codebase research pass explicitly "
            "tasked with checking whether Z.ai had overlooked anything. Fixed in PR #257: "
            "fastapi>=0.136.1, uvicorn>=0.46.0, pyotp>=2.9.0 added to edge/requirements.txt "
            "(floors matched to headend/requirements.txt's exact pins to avoid a CI dependency "
            "conflict, not to TL-C87FF9587CA0's live 0.141.1)."
        ),
        "attributes": {
            "discovered_at": "2026-09-24",
            "discovered_by": "independent codebase research pass (2nd of 2 background agents), not in original z.ai hypothesis list",
            "fixed_by": PR257,
            "fix_status": "PR open, not yet merged as of registration",
        },
        "evidence": [
            (f"doc://{HANDOVER}", "2026-09-24 handover entry with full evidence trail"),
            (PR257, "PR #257: builder gap fixes including this one"),
        ],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE-BT-MAC-ADDRESS-COLLISION-20260924",
        "title": "Edge1 and Edge2 Bluetooth controllers report the identical MAC address (10:11:12:13:14:15)",
        "status": "open",
        "priority": "P2",
        "description": (
            "Live-verified via `hciconfig hci0` on both devices during PR #249 physical testing: "
            "Edge2 (TL-043EB9E72EFD)'s Bluetooth chip natively reports BD Address "
            "10:11:12:13:14:15 — almost certainly an unprogrammed vendor placeholder address for "
            "this UART-attached chip (common for cheap Realtek/Broadcom UART BT modules without "
            "an EEPROM-stored unique address). Edge1 (TL-C87FF9587CA0)'s raw hardware address is "
            "genuinely unique (2C:88:C9:35:A4:A2 per hciconfig), but its BlueZ layer has been "
            "separately configured to PRESENT the identical placeholder value "
            "(10:11:12:13:14:15) as its Controller identity — i.e. someone deliberately (or via "
            "copy-pasted config) made Edge1 collide with Edge2's default rather than the other "
            "way around. This is orthogonal to PR #249's dynamic-naming fix (Alias/LocalName now "
            "differ correctly between devices) but would break any technician workflow relying "
            "on BLE MAC-level identification/pairing rather than the advertised name — a field "
            "technician's phone scanning for 'the nearby camera' by address, or any pairing-key "
            "storage keyed by BD address, cannot distinguish the two devices."
        ),
        "attributes": {
            "discovered_at": "2026-09-24",
            "discovered_during": "PR #249 physical Bluetooth verification",
            "edge1_raw_hw_address": "2C:88:C9:35:A4:A2 (per hciconfig)",
            "edge1_bluez_reported_address": "10:11:12:13:14:15 (deliberately configured to match Edge2's default)",
            "edge2_native_address": "10:11:12:13:14:15 (likely unprogrammed vendor placeholder)",
            "related_pr": 249,
        },
        "evidence": [
            (f"doc://{HANDOVER}", "2026-09-24 handover entry with hciconfig output from both devices"),
        ],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE1-INSECURE-SSH-AND-PACKAGE-DRIFT-20260924",
        "title": "Edge1 (dev rig) has insecure global SSH config and ~70 unnecessary desktop/Samba/CUPS/NFS packages — confirmed device drift, not a builder defect",
        "status": "open",
        "priority": "P1",
        "description": (
            "Live-verified: Edge1's /etc/ssh/sshd_config has global `PermitRootLogin yes` + "
            "`PasswordAuthentication yes` (with a `Match User servicetekniker` override to "
            "key-only and a `Match User emergency` override re-enabling password auth for the "
            "break-glass account). Edge2's sshd_config is correctly hardened "
            "(`PermitRootLogin no` / `PasswordAuthentication no` globally) — confirmed via direct "
            "SSH to both devices. Independently, the builder's Dockerfile.edge explicitly sets "
            "PermitRootLogin no / PasswordAuthentication no (lines 47-48) — so this is confirmed "
            "Edge1-specific device drift, NOT something the builder produces; corroborated by a "
            "concurrent z.ai physical audit reporting the same ~42 desktop packages "
            "(xfce/firefox/lightdm/xorg) + ~27 samba/cups/nfs packages present only on Edge1. "
            "Edge1 also runs Ubuntu 24.04 (Noble) against a Jammy-targeting builder — already "
            "tracked separately as FIND-TL-C87FF9587CA0-UBUNTU-NOBLE-UNDOCUMENTED-OS-UPGRADE. "
            "Per Peter's explicit instruction, Edge1 must not be treated as a reference/golden "
            "device for remediation, and no packages were removed or SSH config changed in this "
            "session — this finding only documents current state for the Golden Edge Baseline "
            "effort's 'Edge1 drift' section."
        ),
        "attributes": {
            "discovered_at": "2026-09-24",
            "edge1_sshd_permitrootlogin": "yes (global)",
            "edge1_sshd_passwordauthentication": "yes (global)",
            "edge2_sshd_permitrootlogin": "no (correct)",
            "edge2_sshd_passwordauthentication": "no (correct)",
            "builder_produces": "PermitRootLogin no / PasswordAuthentication no (Dockerfile.edge:47-48) — confirmed correct",
            "cross_verified_with": "concurrent z.ai physical audit (Dokumentation/GOLDEN_EDGE_VERIFICATION_2026-09-24_ZAI.md, folded into this GRC entry)",
            "related_finding": "FIND-TL-C87FF9587CA0-UBUNTU-NOBLE-UNDOCUMENTED-OS-UPGRADE",
            "remediation_note": "requires governed change on Edge1 itself, not a builder fix — Edge1 is explicitly not to be used as the reference device",
        },
        "evidence": [
            (f"doc://{HANDOVER}", "2026-09-24 handover entry with sshd_config excerpts from both devices"),
        ],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE-BREAKGLASS-SETUP-SERVICE-MISSING-20260924",
        "title": "timelapse-breakglass-setup.service does not exist anywhere in the current repo — deliberately NOT recreated in this pass",
        "status": "open",
        "priority": "P1",
        "description": (
            "Confirmed via `git show origin/main:edge/scripts/timelapse-breakglass-setup.service` "
            "(and .sh) — path does not exist on main at all, not merely un-wired into the "
            "builder. Flagged by both the Z.ai hypothesis list and a concurrent z.ai physical "
            "audit as a P0 builder gap. NOT fixed in PR #257 alongside the other builder-wiring "
            "fixes (timesync/watchdog/network-manager/chrony/GPIO-udev/sudoers), despite meeting "
            "the same 'file exists elsewhere, just needs wiring' pattern on the surface — because "
            "HANDOVER_LOG documents this account's long, bug-ridden history (a break-glass "
            "account previously built without its key-delivery mechanism), and the underlying "
            "break-glass account creation already happens via a different, working mechanism "
            "(direct user/sudoers creation in inject_edge_image.py at flash time, confirmed "
            "present and correct). Enabling an unreviewed, never-git-committed service for a "
            "security-sensitive credential-delivery mechanism does not meet the 'safe and "
            "isolated' bar this closure pass required. Needs its own dedicated, reviewed scope: "
            "what should this service actually do that inject-time provisioning doesn't already "
            "cover, and does recreating it risk repeating the prior incomplete implementation."
        ),
        "attributes": {
            "discovered_at": "2026-09-24",
            "confirmed_absent_from": "origin/main (git show returns 'does not exist')",
            "related_working_mechanism": "break-glass account (user/sudoers) IS created at inject-time in inject_edge_image.py — confirmed present, this finding is only about the separate named service",
            "deliberately_not_fixed_reason": "documented bug-ridden history of this account's prior implementations; needs dedicated review, not a mechanical wiring fix",
            "flagged_by": ["Z.ai original 12-hypothesis list", "concurrent z.ai physical audit", "PR #257 (explicitly excluded, documented in commit message)"],
        },
        "evidence": [
            (f"doc://{HANDOVER}", "2026-09-24 handover entry"),
            (PR257, "PR #257 commit message explicitly documents this exclusion and why"),
        ],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-PR249-MERGED-BEFORE-PHYSICAL-TEST-RECONCILED-20260924",
        "title": "PR #249 (Bluetooth dynamic naming) was merged 2026-09-21 despite its own text stating physical hardware test was required first — reconciled 2026-09-24",
        "status": "closed",
        "priority": "P2",
        "description": (
            "PR #249's description explicitly listed 'Fysisk Edge-test (begge devices)' as "
            "outstanding under 'Hvad mangler / næste skridt', yet the PR was merged to main on "
            "2026-09-21 as part of a batch of four same-day merges, before that physical test was "
            "performed. Peter explicitly asked (2026-09-24) for this to be reconciled rather than "
            "silently accepted. Reconciliation: physical test performed 2026-09-24 on Edge1 "
            "(TL-C87FF9587CA0) — PASS with one known, by-design limitation (BLE advertisement "
            "LocalName drops the SSID for this specific SSID length, per the documented "
            "truncation policy). Edge2 (TL-043EB9E72EFD) physical test blocked pending formal "
            "artifact deployment (pending_updates #314, still awaiting admin approval as of "
            "2026-09-24) — Edge1's code was deployed ad-hoc (manual file copy, 2026-09-19), never "
            "through the actual signed-artifact pipeline PR #249 itself describes. Live WiFi<->AP "
            "transition test NOT performed on either device — see "
            "FIND-EDGE-WIFI-AP-FALLBACK-NONFUNCTIONAL-20260924 (AP fallback is non-functional on "
            "both physical edges right now, independent of PR #249; forcing a live transition "
            "test would risk stranding a production device)."
        ),
        "attributes": {
            "merged_at": "2026-09-21",
            "reconciled_at": "2026-09-24",
            "edge1_test_result": "PASS (with documented SSID-truncation limitation for this SSID length)",
            "edge2_test_result": "blocked — code not yet deployed via formal pipeline (pending_updates #314 unapproved)",
            "wifi_ap_transition_test": "not performed — see FIND-EDGE-WIFI-AP-FALLBACK-NONFUNCTIONAL-20260924",
            "related_pr": 249,
        },
        "evidence": [
            (f"doc://{HANDOVER}", "2026-09-24 handover entry with full physical test results"),
            (PR249, "PR #249 as merged"),
        ],
    },
]


def upsert_item(db, spec: dict) -> tuple[GrcItem, bool]:
    item = db.query(GrcItem).filter_by(
        item_type=spec["item_type"], external_id=spec["external_id"]
    ).first()
    if item:
        return item, False
    item = GrcItem(
        item_type=spec["item_type"],
        external_id=spec["external_id"],
        title=spec["title"][:300],
        description=spec["description"],
        status=spec["status"],
        priority=spec["priority"],
        source="import_grc_golden_edge_20260924.py",
        scope={"product": "timelapse-pro"},
        attributes=spec["attributes"],
        created_by=ACTOR,
        updated_by=ACTOR,
    )
    db.add(item)
    db.flush()
    return item, True


def add_evidence(db, item: GrcItem, uri: str, title: str) -> bool:
    if db.query(GrcEvidence).filter_by(item_id=item.id, uri=uri).first():
        return False
    db.add(GrcEvidence(
        item_id=item.id,
        evidence_type="governance_source",
        title=title[:300],
        uri=uri,
        collected_by=ACTOR,
        retention_class="grc_source_permanent",
    ))
    return True


def main() -> None:
    db = SessionLocal()
    created = evidence_added = 0
    try:
        for spec in ITEMS:
            item, was_created = upsert_item(db, spec)
            created += was_created
            for uri, ev_title in spec["evidence"]:
                evidence_added += add_evidence(db, item, uri, ev_title)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"GRC Golden Edge P0/P1: {created} nye items, {evidence_added} nye evidens-links "
          f"(af {len(ITEMS)} items i alt — idempotent)")


if __name__ == "__main__":
    main()
