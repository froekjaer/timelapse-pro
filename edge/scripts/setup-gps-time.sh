#!/bin/bash
# setup-gps-time.sh — configure GPS time after an offline Headend OS bundle.
# Package installation is deliberately not performed here.
set -euo pipefail

GPS_DEVICE="${GPS_DEVICE:-/dev/ttyS3}"
GPS_BAUD="${GPS_BAUD:-9600}"
HEADEND_NTP_HOST="${HEADEND_NTP_HOST:-}"
CHRONY_CONF="/etc/chrony/chrony.conf"
GPSD_CONF="/etc/default/gpsd"

for tool in gpsd chronyc; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Manglende $tool. Installer GPS-afhængigheder via et Headend-signeret offline OS-bundle."
        exit 2
    fi
done

if [[ -n "$HEADEND_NTP_HOST" && ! "$HEADEND_NTP_HOST" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "HEADEND_NTP_HOST har ugyldigt format"
    exit 2
fi

echo "=== TimeLapse Pro: GPS-tidskonfiguration ==="
cat > "$GPSD_CONF" <<EOF
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$GPS_DEVICE"
USBAUTO="true"
GPSD_SOCKET="/var/run/gpsd.sock"
EOF

if [[ -e "$GPS_DEVICE" ]]; then
    stty -F "$GPS_DEVICE" "$GPS_BAUD" raw
fi

HEADEND_NTP_LINE=""
if [[ -n "$HEADEND_NTP_HOST" ]]; then
    HEADEND_NTP_LINE="server $HEADEND_NTP_HOST iburst minpoll 4 maxpoll 6"
fi
cat > "$CHRONY_CONF" <<EOF
# TimeLapse Pro: GPS is primary; optional Headend NTP is offline-site fallback.
refclock SHM 0 offset 0.5 delay 0.2 refid GPS noselect
refclock SHM 1 offset 0.0 delay 0.005 refid PPS prefer
$HEADEND_NTP_LINE
makestep 1.0 3
driftfile /var/lib/chrony/chrony.drift
logdir /var/log.hdd/timelapse
log tracking measurements statistics
allow 192.168.42.0/24
local stratum 10
EOF

systemctl enable gpsd chrony
systemctl restart gpsd chrony
echo "GPS-tidskonfiguration anvendt. Ingen Edge-internetkilde er konfigureret."
