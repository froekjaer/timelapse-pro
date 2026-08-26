#!/bin/bash
# breakglass_shell_wrapper.sh — login shell for the "emergency" break-glass
# account. Announces start/end of every session to Headend SIEM via the
# agent's existing authenticated event-forward cycle.
#
# Recovered 2026-08-25 from an abandoned, never-merged branch
# (codex/edge-terminal-renderer, closed PR #9) where this script was
# originally written for a pubkey-only account design. Peter chose to keep
# the password-based BreakGlassAccount design instead (2026-08-25) — this
# script is unchanged either way, since session auditing doesn't depend on
# how the account authenticates. Wired up as emergency's shell by
# edge/agent.py::_repair_emergency_breakglass_account(), which also creates
# the account itself if missing. Queued events in pending_events.jsonl are
# picked up and forwarded to Headend SIEM by
# edge/agent.py::_collect_breakglass_events_for_sync(), folded into the same
# consolidated sync poll as every other SIEM event — not a separate
# round-trip.
#
# 2026-08-25 (live, Peter's real login, same night as the two log-dir
# ownership fixes above): interactive sessions used to be wrapped in
# `script -f -q -c "$REAL_SHELL -l" "$SESSION_LOG"` to capture a full
# keystroke+output transcript — a second pty relayed between sshd's pty and
# a plain login shell. That double-pty relay is what broke: the terminal
# came up (banner visible, password auth fine), but every keystroke echoed
# one character then scrolled many lines — classic symptom of the inner
# pty starting with the wrong window size / echo mode, something util-linux
# `script` doesn't reliably get right for every terminal/client combination.
# servicetekniker's login shell is plain /bin/bash with no such relay and
# has been confirmed working end-to-end all night. Rather than keep
# debugging a pty relay neither of us can iterate on quickly (every attempt
# needs a live SSH round-trip from Peter), the interactive path now runs
# the real shell directly, with no relay — full transcript recording is
# dropped for now in exchange for a terminal that actually works.
# Start/end events (who, when, exit code) still go to SIEM either way, and
# non-interactive commands (scp, `ssh emergency@host cmd`) still get their
# command + output logged below, since that path never touched `script`.
set -u

LOG_DIR=/var/log.hdd/timelapse/breakglass
SESSIONS_DIR="$LOG_DIR/sessions"
EVENTS_FILE="$LOG_DIR/pending_events.jsonl"
SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
SESSION_LOG="$SESSIONS_DIR/session-$SESSION_ID.log"
REAL_SHELL=/bin/bash

_json_escape() {
  # Minimal JSON string escaping — no external deps (jq may not be present
  # on every target image), good enough for the fixed set of fields we emit.
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\n'
}

_emit_event() {
  local event_type="$1" extra="$2"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    printf '{"event_type":"%s","severity":"critical","session_id":"%s","occurred_at":"%s","ssh_client":"%s"%s}\n' \
      "$event_type" "$SESSION_ID" "$ts" "$(_json_escape "${SSH_CLIENT:-unknown}")" "$extra"
  } >> "$EVENTS_FILE" 2>/dev/null || true
}

if [ -t 0 ]; then
  # Interactive login — no pty relay (see 2026-08-25 note above), so the
  # real shell talks directly to sshd's own pty, exactly like
  # servicetekniker's already-working login. Start/end still logged.
  _emit_event "breakglass_session_start" ",\"transcript\":\"disabled\""
  "$REAL_SHELL" -l
  RC=$?
  _emit_event "breakglass_session_end" ",\"exit_code\":$RC"
  exit $RC
else
  # Non-interactive invocation (e.g. `ssh emergency@host 'command'`, legacy
  # scp). `script` is designed to wrap an interactive TTY, not pass binary
  # data through cleanly, so wrapping it here risks corrupting scp/file
  # transfers. Still fully audit the attempted command and its output —
  # just without the pty-emulation layer.
  CMD="${2:-}"
  _emit_event "breakglass_noninteractive_command" ",\"command\":\"$(_json_escape "$CMD")\""
  {
    echo "=== breakglass non-interactive command, session=$SESSION_ID, $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo "+ $CMD"
  } >> "$SESSION_LOG" 2>/dev/null
  eval "$CMD" >> "$SESSION_LOG" 2>&1
  RC=$?
  _emit_event "breakglass_noninteractive_command_end" ",\"command\":\"$(_json_escape "$CMD")\",\"exit_code\":$RC"
  exit $RC
fi
