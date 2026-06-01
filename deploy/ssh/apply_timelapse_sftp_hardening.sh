#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-/etc/ssh/sshd_config}"
BLOCK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/timelapse-sshd-sftp.conf"
BACKUP="${CONFIG}.timelapse.$(date +%Y%m%d%H%M%S).bak"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

cp "${CONFIG}" "${BACKUP}"

python3 - "${CONFIG}" "${BLOCK}" <<'PY'
from pathlib import Path
import sys

config = Path(sys.argv[1])
block = Path(sys.argv[2]).read_text(encoding="utf-8").rstrip() + "\n"
text = config.read_text(encoding="utf-8")
lines = text.splitlines()

out = []
skip = False
for line in lines:
    stripped = line.strip()
    if stripped == "# TimeLapse Pro SFTP — isolation via ForceCommand (ingen ChrootDirectory på macOS)":
        skip = True
        continue
    if stripped == "# BEGIN TimeLapse Pro SFTP hardening":
        skip = True
        continue
    if skip and stripped in {
        "# TimeLapse Pro — SSH Tunnel konfiguration",
        "# END TimeLapse Pro SFTP hardening",
    }:
        skip = False
        if stripped == "# TimeLapse Pro — SSH Tunnel konfiguration":
            out.append(line)
        continue
    if skip:
        continue
    if stripped == "Port 2222":
        continue
    out.append(line)

rendered = "\n".join(out).rstrip() + "\n\n"
rendered += "# BEGIN TimeLapse Pro SFTP hardening\n"
rendered += block
rendered += "# END TimeLapse Pro SFTP hardening\n"
config.write_text(rendered, encoding="utf-8")
PY

/usr/sbin/sshd -t -f "${CONFIG}"

echo "Updated ${CONFIG}"
echo "Backup: ${BACKUP}"
echo "Reload the dedicated TimeLapse socket:"
echo "  sudo launchctl bootout system /Library/LaunchDaemons/ssh-2222.plist 2>/dev/null || true"
echo "  sudo launchctl bootstrap system /Library/LaunchDaemons/ssh-2222.plist"
