#!/bin/bash
# timelapse-breakglass-setup.sh — Provisions the "emergency" break-glass
# account on first boot.
#
# Deliberately independent of normal enrollment/bootstrap: break-glass
# access must exist even on a device that never successfully enrolled with
# Headend, or whose normal config/TOTP/SSH-key layers are broken — that is
# the entire point of a break-glass path. See HANDOVER_LOG 2026-08-05
# (Peter: "Break-The-Glass virkelig er hvad ordet siger. Ingen
# begrænsninger, så man kan komme på enheden").
#
# The account itself is PUBKEY-ONLY (password login locked) — CMDB-issued
# public keys are the actual delivered credential (see
# edge/agent.py::_apply_break_glass_keys, headend/main.py::get_config
# "security.break_glass_public_keys"). This sidesteps the unsolved
# password-delivery problem entirely (a password would need to reach an
# unreachable device somehow, which is circular) and matches how per-device
# operator SSH keys already work (2026-08-04 hardening).
#
# Every session through this account is recorded in full (commands AND
# output) via breakglass_shell_wrapper.sh, forwarded to Headend SIEM as
# soon as the agent's next event-forward cycle runs. See that script for
# the recording mechanism.
set -euo pipefail

MARKER=/etc/timelapse/.breakglass-provisioned
EMERGENCY_USER=emergency
WRAPPER=/opt/timelapse/edge/scripts/breakglass_shell_wrapper.sh
LOG_DIR=/var/log.hdd/timelapse/breakglass

if [ -f "$MARKER" ]; then
  echo "[breakglass-setup] allerede provisioneret ($MARKER findes) — springer over"
  exit 0
fi

echo "[breakglass-setup] opretter $EMERGENCY_USER-konto..."

if ! id "$EMERGENCY_USER" >/dev/null 2>&1; then
  useradd --create-home --shell "$WRAPPER" --comment "TimeLapse Pro break-glass emergency access" "$EMERGENCY_USER"
fi

# Lock password auth entirely — pubkey via authorized_keys is the only way in.
passwd -l "$EMERGENCY_USER" >/dev/null

# Full sudo, no restrictions — Peter's explicit instruction: break-glass
# must genuinely let someone onto the device with no gates in the way once
# they hold a valid key. The compensating control is detective, not
# preventive: full session recording (below) + SIEM visibility, not access
# limits.
cat > /etc/sudoers.d/timelapse-breakglass <<'EOF'
# TimeLapse Pro break-glass account — full, unrestricted sudo by design.
# Compensating control is full session recording, not access restriction.
# See edge/scripts/timelapse-breakglass-setup.sh
emergency ALL=(ALL) NOPASSWD:ALL
EOF
chmod 0440 /etc/sudoers.d/timelapse-breakglass
visudo -cf /etc/sudoers.d/timelapse-breakglass

# authorized_keys starts empty — populated by the agent from Headend-issued
# break-glass public keys (edge/agent.py::_apply_break_glass_keys). An
# empty/absent authorized_keys means the account exists but nothing can
# actually log in yet, which is the correct default state (creating the
# account is not the same as activating access — a CMDB break-glass
# checkout is what actually authorizes a key).
install -d -m 700 -o "$EMERGENCY_USER" -g "$EMERGENCY_USER" "/home/$EMERGENCY_USER/.ssh"
install -m 600 -o "$EMERGENCY_USER" -g "$EMERGENCY_USER" /dev/null "/home/$EMERGENCY_USER/.ssh/authorized_keys"

# Session-recording log directory. root:root 700 — these are forensic
# transcripts of emergency access, not general logs; only root/sudo should
# ever read them.
install -d -m 700 -o root -g root "$LOG_DIR"
install -d -m 700 -o root -g root "$LOG_DIR/sessions"
install -m 600 -o root -g root /dev/null "$LOG_DIR/pending_events.jsonl"

chmod +x "$WRAPPER" 2>/dev/null || true

touch "$MARKER"
echo "[breakglass-setup] færdig — konto oprettet, ingen nøgler autoriseret endnu"
