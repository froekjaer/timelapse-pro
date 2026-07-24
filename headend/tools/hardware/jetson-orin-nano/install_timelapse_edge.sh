#!/usr/bin/env bash
# TimeLapse Pro — fail-closed offline installer for NVIDIA Jetson Orin Nano.
#
# JetPack/L4T installeres først med NVIDIAs kontrollerede proces. TimeLapse Pro
# installeres derefter fra en GPG-verificeret, detached Git-release og et
# Headend-genereret wheelhouse. Scriptet foretager ingen netværksinstallation.

set -euo pipefail

log() { printf '[jetson-installer] %s\n' "$*"; }
die() { printf '[jetson-installer] ERROR: %s\n' "$*" >&2; exit 1; }

HEADEND_URL=""
TOKEN_FILE=""
RELEASE_DIR=""
RELEASE_TAG=""
EXPECTED_COMMIT=""
WHEELHOUSE=""
START_NOW=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --headend-url) HEADEND_URL="$2"; shift 2 ;;
        --bootstrap-token-file) TOKEN_FILE="$2"; shift 2 ;;
        --release-dir) RELEASE_DIR="$2"; shift 2 ;;
        --release-tag) RELEASE_TAG="$2"; shift 2 ;;
        --expected-commit) EXPECTED_COMMIT="$2"; shift 2 ;;
        --wheelhouse) WHEELHOUSE="$2"; shift 2 ;;
        --start-now) START_NOW=1; shift ;;
        -h|--help)
            sed -n '2,8p' "$0"
            exit 0
            ;;
        *) die "Ukendt argument: $1" ;;
    esac
done

[[ "$EUID" -eq 0 ]] || die "Kør med sudo/root"
[[ -f /etc/nv_tegra_release || -f /etc/nv_jetson_release ]] \
    || die "JetPack/L4T blev ikke detekteret"
[[ "$HEADEND_URL" =~ ^https://[A-Za-z0-9.-]+:[0-9]+(/api)?$ ]] \
    || die "--headend-url skal være en eksplicit HTTPS-URL med port"
[[ -r "$TOKEN_FILE" ]] || die "--bootstrap-token-file mangler eller kan ikke læses"
[[ -d "$RELEASE_DIR/.git" ]] || die "--release-dir skal være en Git-release"
[[ -n "$RELEASE_TAG" ]] || die "--release-tag mangler"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "--expected-commit skal være 40 hex-tegn"
[[ -d "$WHEELHOUSE" ]] || die "--wheelhouse mangler"

for command in git gpg python3 rsync systemctl; do
    command -v "$command" >/dev/null || die "Påkrævet værktøj mangler: $command"
done

git -C "$RELEASE_DIR" verify-tag "$RELEASE_TAG" >/dev/null \
    || die "Release-taggets GPG-signatur kan ikke verificeres"
TAG_COMMIT="$(git -C "$RELEASE_DIR" rev-list -n1 "$RELEASE_TAG")"
HEAD_COMMIT="$(git -C "$RELEASE_DIR" rev-parse HEAD)"
[[ "$TAG_COMMIT" == "$EXPECTED_COMMIT" && "$HEAD_COMMIT" == "$EXPECTED_COMMIT" ]] \
    || die "Release-tag, HEAD og forventet commit matcher ikke"
[[ -z "$(git -C "$RELEASE_DIR" status --porcelain --untracked-files=no)" ]] \
    || die "Release-kataloget har ændrede tracked filer"
[[ -r "$RELEASE_DIR/edge/requirements.txt" ]] || die "Edge requirements mangler i releasen"

BOOTSTRAP_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
[[ "$BOOTSTRAP_TOKEN" =~ ^[A-Za-z0-9._~-]{8,512}$ ]] \
    || die "Bootstrap-tokenfilen indeholder ugyldige data"

INSTALL_BASE="/opt/timelapse"
AGENT_DIR="$INSTALL_BASE/edge"
VENV_DIR="$INSTALL_BASE/venv"
CONFIG_DIR="/etc/timelapse"

if ! id timelapse >/dev/null 2>&1; then
    useradd --create-home --shell /usr/sbin/nologin timelapse
fi
passwd -l timelapse >/dev/null 2>&1 || true

install -d -m 0750 -o timelapse -g timelapse \
    "$INSTALL_BASE" "$AGENT_DIR" /data /run/timelapse
install -d -m 0700 -o root -g root "$CONFIG_DIR"

rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install \
    --no-index \
    --find-links "$WHEELHOUSE" \
    --requirement "$RELEASE_DIR/edge/requirements.txt"

rsync -a --delete \
    --exclude api_token.txt \
    --exclude bootstrap.yaml \
    --exclude config.yaml \
    --exclude keys \
    "$RELEASE_DIR/edge/" "$AGENT_DIR/"
chown -R timelapse:timelapse "$INSTALL_BASE"

cat > "$CONFIG_DIR/bootstrap.yaml" <<EOF
headend_url: "${HEADEND_URL%/}"
bootstrap_token: "${BOOTSTRAP_TOKEN}"
source_release: "${RELEASE_TAG}"
source_commit: "${EXPECTED_COMMIT}"
EOF
chmod 0600 "$CONFIG_DIR/bootstrap.yaml"
chown root:root "$CONFIG_DIR/bootstrap.yaml"

for unit in timelapse-edge timelapse-bootstrap timelapse-bt-pan timelapse-bt-agent timelapse-captive timelapse-totp; do
    source_unit="$RELEASE_DIR/edge/scripts/${unit}.service"
    [[ -r "$source_unit" ]] || continue
    install -m 0644 -o root -g root "$source_unit" "/etc/systemd/system/${unit}.service"
done
[[ -r /etc/systemd/system/timelapse-bootstrap.service ]] \
    || die "timelapse-bootstrap.service mangler i den signerede release"

systemctl daemon-reload
systemctl enable timelapse-bootstrap.service

log "Offline installation gennemført fra $RELEASE_TAG ($EXPECTED_COMMIT)"
log "Ingen apt-, pip-internet- eller GitHub-installation er udført på Edge."
if [[ "$START_NOW" == "1" ]]; then
    systemctl start timelapse-bootstrap.service
    systemctl --no-pager --full status timelapse-bootstrap.service
else
    log "Start med: systemctl start timelapse-bootstrap.service"
fi
