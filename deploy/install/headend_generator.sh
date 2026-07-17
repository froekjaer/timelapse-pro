#!/bin/zsh
# TimeLapse Pro — Headend Generator: tynd orkestrator for de fire faser.
# Kæder preflight → stage (signeret release) → apply → enroll med eksplicitte
# bekræftelses-gates. Implementerer HEADEND_GENERATOR_v1.md §8.4.
#
# Faserne kan stadig køres enkeltvis med de underliggende scripts — dette
# script tilføjer kun rækkefølge, gates og fail-closed stop.
#
# VIGTIGT (trust-modellen): kun preflight/stage køres fra DENNE kopi af repoet.
# Apply og enroll køres fra den GPG-VERIFICEREDE release i --destination, så
# alt der ændrer maskinen stammer fra et signeret, immutabelt artefakt.
#
# Brug:
#   ./headend_generator.sh --config ~/timelapse-staging.conf \
#     --repo-url git@github.com:froekjaer/timelapse-pro.git \
#     --release-tag vX.Y.Z --expected-commit <40-tegns-sha> \
#     --destination ~/tl-staging-release \
#     --device-id TL-HEADEND-STAGING-1 \
#     --bootstrap-token-file /secure/bootstrap-token \
#     [--phase all|preflight|stage|apply|enroll] [--yes]
#
# --yes springer bekræftelses-prompts over (til gennemtestet, gentagen brug).

set -euo pipefail

log() { printf '[headend-generator] %s\n' "$*"; }
die() { printf '[headend-generator] ERROR: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="${0:A:h}"
CONFIG="" REPO_URL="" RELEASE_TAG="" EXPECTED_COMMIT="" DESTINATION=""
DEVICE_ID="" BOOTSTRAP_TOKEN_FILE="" PHASE="all" ASSUME_YES=0

while (( $# )); do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --release-tag) RELEASE_TAG="$2"; shift 2 ;;
    --expected-commit) EXPECTED_COMMIT="$2"; shift 2 ;;
    --destination) DESTINATION="$2"; shift 2 ;;
    --device-id) DEVICE_ID="$2"; shift 2 ;;
    --bootstrap-token-file) BOOTSTRAP_TOKEN_FILE="$2"; shift 2 ;;
    --phase) PHASE="$2"; shift 2 ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) sed -n '2,23p' "$0"; exit 0 ;;
    *) die "Ukendt argument: $1" ;;
  esac
done

[[ -n "$CONFIG" && -r "$CONFIG" ]] || die "--config skal pege på en læsbar miljøfil"
case "$PHASE" in all|preflight|stage|apply|enroll) ;; *) die "--phase skal være all|preflight|stage|apply|enroll" ;; esac

# shellcheck source=/dev/null
source "$CONFIG"
: "${TL_ENV:?TL_ENV mangler i config}"
: "${TL_DOMAIN_BACKEND:?TL_DOMAIN_BACKEND mangler i config}"
: "${TL_BACKEND_PORT:=8443}"

gate() {
  local msg="$1"
  (( ASSUME_YES )) && { log "GATE (auto-ja): $msg"; return 0; }
  printf '[headend-generator] GATE: %s\n' "$msg"
  printf '  Fortsæt? [ja/N] '
  local answer; read -r answer
  [[ "$answer" == "ja" ]] || die "Afbrudt af bruger ved gate: $msg"
}

run_preflight() {
  log "── Fase 0: PREFLIGHT (læs-only) ──"
  "$SCRIPT_DIR/bootstrap_headend_macos.sh" --mode preflight --config "$CONFIG"
}

run_stage() {
  [[ -n "$REPO_URL" && -n "$RELEASE_TAG" && -n "$EXPECTED_COMMIT" && -n "$DESTINATION" ]] \
    || die "stage kræver --repo-url, --release-tag, --expected-commit og --destination"
  log "── Fase 1: STAGE (signeret release → $DESTINATION) ──"
  "$SCRIPT_DIR/bootstrap_headend_macos.sh" --mode stage --config "$CONFIG" \
    --repo-url "$REPO_URL" --release-tag "$RELEASE_TAG" \
    --expected-commit "$EXPECTED_COMMIT" --destination "$DESTINATION"
}

require_verified_release() {
  [[ -n "$DESTINATION" ]] || die "--destination (den verificerede release) er påkrævet for denne fase"
  [[ -x "$DESTINATION/deploy/install/install_headend.sh" ]] \
    || die "Ingen verificeret release i $DESTINATION — kør stage-fasen først"
  if [[ -n "$EXPECTED_COMMIT" ]]; then
    local actual
    actual="$(git -C "$DESTINATION" rev-parse HEAD 2>/dev/null || true)"
    [[ "$actual" == "$EXPECTED_COMMIT" ]] \
      || die "Release i $DESTINATION er ikke på forventet commit ($actual ≠ $EXPECTED_COMMIT)"
  fi
}

run_apply() {
  require_verified_release
  gate "Fase 2 APPLY installerer/opdaterer headend-stakken (miljø: $TL_ENV, port: $TL_BACKEND_PORT). CrushFTP's porte (21/22/80/443) røres ALDRIG."
  log "── Fase 2: APPLY (fra verificeret release) ──"
  sudo "$DESTINATION/deploy/install/install_headend.sh" --config "$CONFIG"
  log "Husk: certifikat via DNS-01 + genkør apply for fuldt SSL-block (manual §5),"
  log "og Fase 2b SFTP-ingress 22222 er stadig et MANUELT trin (manual §7 / GEN-01)."
}

run_enroll() {
  require_verified_release
  [[ -n "$DEVICE_ID" ]] || die "enroll kræver --device-id (fx TL-HEADEND-STAGING-1)"
  [[ -n "$BOOTSTRAP_TOKEN_FILE" && -r "$BOOTSTRAP_TOKEN_FILE" ]] \
    || die "enroll kræver --bootstrap-token-file (genereres i UI: Backup → Headend generator)"
  gate "Fase 3 ENROLL registrerer $DEVICE_ID i CMDB via https://$TL_DOMAIN_BACKEND:$TL_BACKEND_PORT (fail-closed)."
  log "── Fase 3: ENROLL (CMDB + config-control) ──"
  sudo "$DESTINATION/deploy/install/enroll_headend_cmdb.sh" \
    --device-id "$DEVICE_ID" \
    --headend-url "https://$TL_DOMAIN_BACKEND:$TL_BACKEND_PORT" \
    --bootstrap-token-file "$BOOTSTRAP_TOKEN_FILE" \
    --repo-dir "$DESTINATION"
}

case "$PHASE" in
  preflight) run_preflight ;;
  stage)     run_preflight; run_stage ;;
  apply)     run_apply ;;
  enroll)    run_enroll ;;
  all)
    run_preflight
    gate "Preflight OK (evidens-JSON gemt). Fortsæt til STAGE (henter signeret release)?"
    run_stage
    run_apply
    run_enroll
    log "✅ Alle faser gennemført. Verificér jf. INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md §9."
    ;;
esac
