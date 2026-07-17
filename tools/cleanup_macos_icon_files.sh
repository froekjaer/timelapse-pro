#!/usr/bin/env bash
set -euo pipefail

# Remove macOS custom icon metadata files named "Icon\r".
# These files can appear inside .git and break ref/object scans, for example:
#   fatal: bad object refs/Icon?

root="${1:-}"
if [[ -z "$root" ]]; then
  if root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    :
  else
    root="$(pwd)"
  fi
fi

if [[ ! -d "$root" ]]; then
  echo "Path does not exist: $root" >&2
  exit 2
fi

icon_name=$'Icon\r'
removed=0

remove_matches() {
  local search_root="$1"
  shift

  [[ -d "$search_root" ]] || return 0

  while IFS= read -r -d '' path; do
    rm -f "$path"
    removed=$((removed + 1))
  done < <(find "$search_root" "$@" -name "$icon_name" -type f -print0 2>/dev/null)
}

# Inside .git these files are never valid Git metadata, so remove all of them.
remove_matches "$root/.git"

# Outside .git, delete only empty Finder icon placeholders to avoid removing
# intentionally customized folder icons with payload data.
while IFS= read -r -d '' path; do
  rm -f "$path"
  removed=$((removed + 1))
done < <(
  find "$root" \
    -path "$root/.git" -prune -o \
    -path "$root/.venv" -prune -o \
    -path "$root/venv" -prune -o \
    -path "$root/headend/venv" -prune -o \
    -path "$root/node_modules" -prune -o \
    -path "$root/timelapse-ui/node_modules" -prune -o \
    -path "$root/timelapse-ui/dist" -prune -o \
    -path "$root/.pytest_cache" -prune -o \
    -path "$root/.mypy_cache" -prune -o \
    -path "$root/.ruff_cache" -prune -o \
    -name "$icon_name" -type f -size 0 -print0 2>/dev/null
)

echo "Removed $removed macOS Icon metadata file(s) from $root"
