#!/bin/bash
# breakglass_shell_wrapper.sh — login shell for the "emergency" break-glass
# account. Records the FULL session (commands AND their output, not just
# keystrokes — output matters for judging whether an attempted action
# actually succeeded) and announces start/end to Headend SIEM via the
# agent's existing authenticated event-forward cycle.
#
# See edge/scripts/timelapse-breakglass-setup.sh for how this gets wired up
# as emergency's shell, and edge/agent.py::_forward_breakglass_events for
# how the queued start/end events actually reach Headend.
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
  # Interactive login — record the full session transcript.
  _emit_event "breakglass_session_start" ",\"log_file\":\"$(basename "$SESSION_LOG")\""
  # -f: flush output as it's written, so a crashed/killed session still
  #     leaves a usable partial transcript for later review.
  # -q: quiet, no "Script started/done" chatter mixed into the transcript.
  script -f -q -c "$REAL_SHELL -l" "$SESSION_LOG"
  RC=$?
  _emit_event "breakglass_session_end" ",\"log_file\":\"$(basename "$SESSION_LOG")\",\"exit_code\":$RC"
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
