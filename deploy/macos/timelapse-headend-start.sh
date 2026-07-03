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

wait_for_path "/Volumes/data-fast" 240
wait_for_path "$WORKDIR" 240
wait_for_tcp "127.0.0.1" "5432" 240

cd "$WORKDIR"
exec "$UVICORN" main:app --host 127.0.0.1 --port 8000 --log-level info
