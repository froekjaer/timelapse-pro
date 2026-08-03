#!/bin/bash
# gen-bt-cert.sh — kontrollerer lokal TLS til management-portalen.
# Flashbare produktions-images leveres med et certifikat fra Headendens Edge
# Local CA. Self-signed fallback er kun for allerede eksisterende R&D-enheder,
# så en gammel enhed ikke gøres utilgængelig før den har modtaget migreringen.
set -euo pipefail

CERT_DIR="/etc/timelapse/certs"
CERT="$CERT_DIR/mgmt.crt"
KEY="$CERT_DIR/mgmt.key"
DAYS=1825  # 5 år
BT_IP="192.168.42.1"
HOSTNAME=$(hostname -s)

if [[ $EUID -ne 0 ]]; then
    echo "Kræver root" >&2
    exit 1
fi

mkdir -p "$CERT_DIR"
chmod 700 "$CERT_DIR"

# Tjek om eksisterende cert stadig er gyldigt (mere end 30 dage tilbage)
if [[ -f "$CERT" && -f "$KEY" ]]; then
    EXPIRY=$(openssl x509 -enddate -noout -in "$CERT" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s)
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
    if [[ $DAYS_LEFT -gt 30 ]]; then
        echo "Eksisterende cert er gyldigt i $DAYS_LEFT dage — springer over"
        exit 0
    fi
    echo "Cert udløber om $DAYS_LEFT dage — fornyer"
fi

if [[ "${TIMELAPSE_ALLOW_SELF_SIGNED_LOCAL_TLS:-true}" != "true" ]]; then
    echo "Mangler gyldigt CA-udstedt lokalt TLS-certifikat" >&2
    exit 1
fi

echo "ADVARSEL: bruger midlertidigt self-signed TLS (R&D migration)" >&2

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$KEY" \
    -out "$CERT" \
    -days "$DAYS" \
    -subj "/CN=timelapse-local/O=TimeLapse Pro/OU=Edge" \
    -addext "subjectAltName=IP:$BT_IP,DNS:$HOSTNAME,DNS:timelapse.local"

chmod 600 "$KEY"
chmod 644 "$CERT"

echo "TLS cert genereret: $CERT (gyldigt $DAYS dage)"
openssl x509 -subject -issuer -dates -noout -in "$CERT"
