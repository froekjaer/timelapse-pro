#!/bin/bash
# setup-gps-time.sh — GPS tidssynkronisering via gpsd + chrony
# Fallback: headend API → pool.ntp.org
#
# GPS hardware: typisk tilsluttet via UART (f.eks. /dev/ttyS3 på OrangePi 4 Pro)
# Konfigurer GPS_DEVICE herunder efter faktisk hardware
set -euo pipefail

GPS_DEVICE="${GPS_DEVICE:-/dev/ttyS3}"
GPS_BAUD="${GPS_BAUD:-9600}"
HEADEND_URL="${HEADEND_URL:-http://192.168.86.125:8000}"
CHRONY_CONF="/etc/chrony/chrony.conf"
GPSD_CONF="/etc/default/gpsd"

echo "=== TimeLapse Pro: GPS tidssynkronisering setup ==="

# 1. Installer pakker
echo "[1/5] Installerer gpsd + chrony..."
apt-get update -qq
apt-get install -y gpsd gpsd-clients chrony python3-gps

# 2. Konfigurer gpsd
echo "[2/5] Konfigurerer gpsd..."
cat > "$GPSD_CONF" <<EOF
# gpsd konfiguration — TimeLapse Pro
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$GPS_DEVICE"
USBAUTO="true"
GPSD_SOCKET="/var/run/gpsd.sock"
EOF

# Sæt baudrate via stty (GPS-modul kræver det)
if [[ -e "$GPS_DEVICE" ]]; then
    stty -F "$GPS_DEVICE" "$GPS_BAUD" raw
    echo "  GPS device: $GPS_DEVICE @ ${GPS_BAUD} baud"
else
    echo "  ADVARSEL: $GPS_DEVICE ikke fundet — GPS vil ikke virke"
    echo "  Konfigurer GPS_DEVICE korrekt og kør igen"
fi

# 3. Konfigurer chrony
echo "[3/5] Konfigurerer chrony..."
HEADEND_IP=$(echo "$HEADEND_URL" | sed 's|http://||; s|:.*||')

cat > "$CHRONY_CONF" <<EOF
# chrony.conf — TimeLapse Pro GPS tidssynkronisering
# Prioritet: GPS (SHM) → headend NTP → pool.ntp.org → local RTC

# GPS via gpsd shared memory (primær kilde)
# SHM 0 = rå NMEA, SHM 1 = PPS (hvis tilgængeligt)
refclock SHM 0 offset 0.5 delay 0.2 refid GPS noselect
refclock SHM 1 offset 0.0 delay 0.005 refid PPS prefer

# Headend som NTP-kilde (fallback når GPS ikke er tilgængeligt)
# pool-weight 1 = lav prioritet
server $HEADEND_IP iburst minpoll 4 maxpoll 6

# Internet NTP fallback (kræver netværk)
pool pool.ntp.org iburst minpoll 6 maxpoll 10

# Tillad store tidsspring ved første sync (vigtigt ved koldstart uden RTC)
makestep 1.0 3

# Gem tidsoffset til fil så chrony starter hurtigt ved genstart
driftfile /var/lib/chrony/chrony.drift

# Log til /var/log.hdd/timelapse/ (ikke zram)
logdir /var/log.hdd/timelapse
log tracking measurements statistics

# Tillad lokal klienter at hente tid (BT PAN klienter)
allow 192.168.42.0/24

# Lokal ur som absolut fallback (stratum 10 = meget lav præcision)
local stratum 10
EOF

echo "  Headend NTP: $HEADEND_IP"

# 4. Aktiver og start services
echo "[4/5] Aktiverer services..."
systemctl enable gpsd chrony
systemctl restart gpsd
sleep 2
systemctl restart chrony

# 5. Status
echo "[5/5] Status..."
echo ""
echo "=== gpsd ==="
systemctl status gpsd --no-pager -l | head -20

echo ""
echo "=== chrony tracking ==="
sleep 3
chronyc tracking || true

echo ""
echo "=== chrony sources ==="
chronyc sources -v || true

echo ""
if [[ -e "$GPS_DEVICE" ]]; then
    echo "GPS device tilgængeligt. Vent 1-2 minutter på GPS lock..."
    echo "Tjek GPS: gpsmon $GPS_DEVICE"
else
    echo "Ingen GPS — synkroniserer fra headend/internet NTP"
fi
