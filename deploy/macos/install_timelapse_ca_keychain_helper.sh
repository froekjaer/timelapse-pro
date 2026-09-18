#!/usr/bin/env bash
# Install/verify the TimeLapse Pro System-keychain reader used for the
# Headend API mTLS CA passphrase. This script never creates a Keychain item
# and never receives the passphrase.
set -euo pipefail

HELPER_DST="/usr/local/libexec/timelapse-ca-keychain"
APP_DIR="/Library/Application Support/TimeLapse Pro"
PKI_DIR="${APP_DIR}/pki"
CA_DIR="${PKI_DIR}/headend-api-mtls-ca"
HEADEND_USER="peter"
HEADEND_GROUP="staff"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="${SCRIPT_DIR}/timelapse-ca-keychain.c"

log() { printf '[install-ca-keychain-helper] %s\n' "$*"; }
die() { printf '[install-ca-keychain-helper] FEJL: %s\n' "$*" >&2; exit 1; }

MODE="${1:---verify-only}"
case "$MODE" in
  --install|--verify-only) ;;
  *) die "usage: $0 --install|--verify-only" ;;
esac

[[ "$(uname -s)" == "Darwin" ]] || die "macOS-only helper"
[[ -f "$SOURCE" ]] || die "missing source: $SOURCE"

if [[ "$MODE" == "--verify-only" ]]; then
  log "source: present"
  if [[ -x "$HELPER_DST" ]]; then
    stat -f 'helper: %N owner=%Su group=%Sg mode=%Sp (%OLp)' "$HELPER_DST"
  else
    log "helper: not installed"
  fi
  if [[ -d "$CA_DIR" ]]; then
    stat -f 'ca-dir: %N owner=%Su group=%Sg mode=%Sp (%OLp)' "$CA_DIR"
    /usr/bin/tmutil isexcluded "$CA_DIR" 2>/dev/null || true
  else
    log "ca-dir: not provisioned"
  fi
  log "verify-only complete — no Keychain access and no mutation performed"
  exit 0
fi

[[ "$(id -u)" == 0 ]] || die "--install requires root"
id "$HEADEND_USER" >/dev/null 2>&1 || die "runtime user '$HEADEND_USER' does not exist"
[[ -x /usr/bin/clang ]] || die "/usr/bin/clang missing"

TMP_BIN="$(mktemp /tmp/timelapse-ca-keychain.XXXXXX)"
trap 'rm -f "$TMP_BIN"' EXIT

/usr/bin/clang \
  -O2 -Wall -Wextra \
  -framework Security -framework CoreFoundation \
  "$SOURCE" -o "$TMP_BIN"

install -d -o root -g wheel -m 0755 /usr/local/libexec
install -o root -g wheel -m 0755 "$TMP_BIN" "$HELPER_DST"
install -d -o root -g wheel -m 0755 "$APP_DIR"
install -d -o root -g wheel -m 0755 "$PKI_DIR"
install -d -o "$HEADEND_USER" -g "$HEADEND_GROUP" -m 0700 "$CA_DIR"
/usr/bin/tmutil addexclusion -p "$CA_DIR"

log "installed root-owned helper: $HELPER_DST"
log "provisioned root-owned PKI parent and 0700 live CA directory: $CA_DIR"
log "excluded live CA directory from routine Time Machine backup"
log "Keychain item was NOT created or modified"
log "next gate is a separate dummy System-keychain ACL/probe test"
