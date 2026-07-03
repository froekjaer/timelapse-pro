#!/usr/bin/env python3
"""Render site-scoped SSHD Match blocks for TimeLapse SFTP users.

The generated config makes SFTP deny-by-default and creates one allow block per
Site.sftp_user. On macOS, OpenSSH's ChrootDirectory is impractical for the
current mapped-volume layout, so this binds the user's starting directory with
internal-sftp -d and must be paired with filesystem permissions/ACLs on the
canonical customer/site directory.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Customer, SessionLocal, Settings, Site  # noqa: E402


def safe_segment(value: str | None, fallback: str = "unknown") -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[^A-Za-z0-9æøåÆØÅ_-]+", "_", text).strip("_")
    return text or fallback


def setting(db, key: str, fallback: str = "") -> str:
    row = db.query(Settings).filter_by(key=key).first()
    return row.value if row and row.value is not None else fallback


def render() -> tuple[str, list[dict]]:
    db = SessionLocal()
    rows: list[dict] = []
    try:
        root = Path(setting(db, "sftp_base", "/Volumes/data-fast/timelapse-incoming/canonical-images")).expanduser()
        sites = (
            db.query(Site)
            .filter(Site.sftp_user.isnot(None))
            .order_by(Site.name.asc())
            .all()
        )
        lines = [
            "# BEGIN TimeLapse Pro generated site-scoped SFTP RBAC",
            "# Generated from Headend DB. Do not hand-edit generated Match blocks.",
            "",
        ]
        for site in sites:
            user = (site.sftp_user or "").strip()
            if not user:
                continue
            if not re.fullmatch(r"sftp_[A-Za-z0-9_-]+", user):
                rows.append({"site": site.name, "sftp_user": user, "status": "skipped_invalid_user"})
                continue
            customer = db.query(Customer).filter_by(id=site.customer_id).first() if site.customer_id else None
            customer_name = customer.name if customer else site.customer_id or "unknown_customer"
            site_path = root / safe_segment(customer_name) / safe_segment(site.name)
            rows.append({
                "site": site.name,
                "customer": customer_name,
                "sftp_user": user,
                "path": str(site_path),
                "exists": site_path.exists(),
                "status": "rendered",
            })
            lines.extend([
                f"# {customer_name} / {site.name}",
                f"Match User {user} LocalPort 22222",
                f"    ForceCommand internal-sftp -d {site_path}",
                "    AllowTcpForwarding no",
                "    X11Forwarding no",
                "    PasswordAuthentication yes",
                "    KbdInteractiveAuthentication no",
                "    PubkeyAuthentication yes",
                "    PermitTTY no",
                "",
            ])
        lines.extend([
            "# Default deny for undeclared TimeLapse SFTP users.",
            "Match User sftp_* LocalPort 22222",
            "    ForceCommand /usr/bin/false",
            "    AllowTcpForwarding no",
            "    X11Forwarding no",
            "    PasswordAuthentication no",
            "    KbdInteractiveAuthentication no",
            "    PubkeyAuthentication no",
            "    PermitTTY no",
            "",
            "# END TimeLapse Pro generated site-scoped SFTP RBAC",
            "",
        ])
        return "\n".join(lines), rows
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/private/tmp/timelapse-sftp-rbac-sites.conf")
    parser.add_argument("--mkdir", action="store_true", help="Create rendered site directories if missing.")
    args = parser.parse_args()

    config, rows = render()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(config, encoding="utf-8")
    if args.mkdir:
        for row in rows:
            if row.get("status") == "rendered":
                Path(row["path"]).mkdir(parents=True, exist_ok=True)

    print(f"Rendered: {output}")
    for row in rows:
        print(row)
    print()
    print("Install with root privileges after reviewing:")
    print(f"  sudo cat {output} >> /etc/ssh/sshd_config")
    print("  sudo /usr/sbin/sshd -t -f /etc/ssh/sshd_config")
    print("  sudo launchctl kickstart -k system/com.openssh.sshd")
    print()
    print("Filesystem permissions/ACLs must allow each sftp_user only inside its rendered path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
