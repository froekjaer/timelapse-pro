#!/bin/zsh
set -euo pipefail

ENV_FILE="${TIMELAPSE_HEADEND_ENV_FILE:-/etc/timelapse/headend.env}"
WORKDIR="${TIMELAPSE_HEADEND_WORKDIR:-/Volumes/data-fast/peter-home/projects/timelapse-pro/headend}"
UVICORN="${TIMELAPSE_HEADEND_UVICORN:-/Users/peter/.venvs/timelapse-headend/bin/uvicorn}"
LOG_PREFIX="[timelapse-headend-start]"

export HOME="${HOME:-/Users/peter}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

if [[ -r "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

wait_for_path() {
  local path="$1"
  local timeout="${2:-180}"
  local waited=0
  while [[ ! -e "$path" && "$waited" -lt "$timeout" ]]; do
    echo "$LOG_PREFIX waiting for $path ($waited/$timeout)"
    sleep 5
    waited=$((waited + 5))
  done
  [[ -e "$path" ]]
}

wait_for_tcp() {
  local host="$1"
  local port="$2"
  local timeout="${3:-180}"
  local waited=0
  while ! /usr/bin/nc -z "$host" "$port" >/dev/null 2>&1; do
    if [[ "$waited" -ge "$timeout" ]]; then
      return 1
    fi
    echo "$LOG_PREFIX waiting for $host:$port ($waited/$timeout)"
    sleep 5
    waited=$((waited + 5))
  done
}

# check_port_occupation checks if a port is in use and returns info about the process
# Returns: 0 if port is free, 1 if occupied by headend, 2 if occupied by other process
# Output: PID and command name if occupied
check_port_occupation() {
  local port="$1"
  local output
  output=$(/usr/sbin/lsof -i ":$port" -sTCP:LISTEN -P -n 2>/dev/null || true)

  if [[ -z "$output" ]]; then
    return 0  # Port is free
  fi

  # Extract PID and command
  local pid cmd
  pid=$(echo "$output" | tail -n +2 | awk '{print $2}' | head -n1)
  cmd=$(echo "$output" | tail -n +2 | awk '{print $1}' | head -n1)

  echo "$pid $cmd"

  # Check if it's a headend process
  if echo "$cmd" | grep -qE '(uvicorn|python|timelapse-headend)'; then
    return 1  # Occupied by headend
  else
    return 2  # Occupied by other process
  fi
}

# terminate_old_headend gracefully terminates a previous headend instance
# Logs to stdout and SIEM for SABSA compliance
terminate_old_headend() {
  local pid="$1"
  local cmd="$2"
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')

  echo "$LOG_PREFIX [STARTUP_GUARD] Port 8000 occupied by headend process (PID=$pid, CMD=$cmd)"
  echo "$LOG_PREFIX [STARTUP_GUARD] Attempting graceful termination (SIGTERM)..."

  # Log to SIEM if SIEM collector is available
  if command -v logger >/dev/null 2>&1; then
    logger -t timelapse-headend-start "STARTUP_GUARD: Terminating old headend PID=$pid CMD=$cmd - port 8000 occupied"
  fi

  # Try SIGTERM first (graceful)
  if kill -TERM "$pid" 2>/dev/null; then
    echo "$LOG_PREFIX [STARTUP_GUARD] SIGTERM sent to PID=$pid, waiting for shutdown..."

    # Wait up to 5 seconds for graceful shutdown
    local waited=0
    while /usr/sbin/lsof -i ":8000" -sTCP:LISTEN -P -n >/dev/null 2>&1 && [[ "$waited" -lt 5 ]]; do
      sleep 1
      waited=$((waited + 1))
    done

    if ! /usr/sbin/lsof -i ":8000" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
      echo "$LOG_PREFIX [STARTUP_GUARD] Old headend terminated gracefully (${waited}s)"
      logger -t timelapse-headend-start "STARTUP_GUARD: Old headend PID=$pid terminated gracefully (${waited}s)"
      return 0
    fi
  fi

  # If still running, use SIGKILL (force)
  echo "$LOG_PREFIX [STARTUP_GUARD] Graceful shutdown failed, using SIGKILL..."
  if kill -KILL "$pid" 2>/dev/null; then
    sleep 1
    echo "$LOG_PREFIX [STARTUP_GUARD] Old headend force-terminated (SIGKILL)"
    logger -t timelapse-headend-start "STARTUP_GUARD: Old headend PID=$pid force-terminated (SIGKILL)"
    return 0
  fi

  echo "$LOG_PREFIX [STARTUP_GUARD] ERROR: Failed to terminate old headend"
  return 1
}

# ensure_port_available ensures port 8000 is available before starting
# Implements SABSA accountability by logging all process termination
ensure_port_available() {
  local max_attempts=3
  local attempt=0

  while [[ "$attempt" -lt "$max_attempts" ]]; do
    attempt=$((attempt + 1))
    local info
    local pid cmd

    info=$(check_port_occupation 8000) || true
    local status=$?

    case $status in
      0)
        echo "$LOG_PREFIX [STARTUP_GUARD] Port 8000 is available"
        return 0
        ;;
      1)
        # Occupied by headend - try to terminate
        pid=$(echo "$info" | awk '{print $1}')
        cmd=$(echo "$info" | awk '{print $2}')
        if terminate_old_headend "$pid" "$cmd"; then
          # Give system time to release port
          sleep 2
          continue
        else
          echo "$LOG_PREFIX [STARTUP_GUARD] ERROR: Failed to clear port 8000"
          logger -t timelapse-headend-start "STARTUP_GUARD: Failed to clear port 8000 - aborting startup"
          return 1
        fi
        ;;
      2)
        # Occupied by other process - fatal error
        pid=$(echo "$info" | awk '{print $1}')
        cmd=$(echo "$info" | awk '{print $2}')
        echo "$LOG_PREFIX [STARTUP_GUARD] ERROR: Port 8000 occupied by NON-HEADEND process (PID=$pid, CMD=$cmd)"
        echo "$LOG_PREFIX [STARTUP_GUARD] Headend cannot start. Please investigate and resolve manually."
        logger -t timelapse-headend-start "STARTUP_GUARD: Port 8000 occupied by non-headend PID=$pid CMD=$cmd - aborting startup"
        return 1
        ;;
    esac
  done

  echo "$LOG_PREFIX [STARTUP_GUARD] ERROR: Port 8000 still occupied after $max_attempts attempts"
  logger -t timelapse-headend-start "STARTUP_GUARD: Port 8000 still occupied after $max_attempts attempts - aborting startup"
  return 1
}

wait_for_path "/Volumes/data-fast" 240
wait_for_path "$WORKDIR" 240
wait_for_tcp "127.0.0.1" "5432" 240

# Ensure port 8000 is available before starting headend
# This prevents restart loops when a previous instance didn't shut down cleanly
if ! ensure_port_available; then
  echo "$LOG_PREFIX FATAL: Cannot start headend - port 8000 unavailable"
  logger -t timelapse-headend-start "FATAL: Headend startup aborted - port 8000 unavailable"
  exit 1  # Non-zero exit prevents launchctl from restarting immediately
fi

cd "$WORKDIR"
exec "$UVICORN" main:app --host 127.0.0.1 --port 8000 --log-level info
