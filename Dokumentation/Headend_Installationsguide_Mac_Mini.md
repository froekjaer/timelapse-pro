# TimeLapse Pro — Headend Installationsguide (Mac Mini)

**Version:** 2.9 | **Dato:** 2026-05-11 | **Platform:** macOS Sequoia (Apple Silicon)

---

## Forudsætninger

- Mac Mini med macOS Sequoia (Darwin 25+)
- Homebrew installeret
- GitHub SSH-adgang konfigureret
- Ekstern harddisk formateret som `data` (mountes automatisk som `/Volumes/data`)

---

## 1. PostgreSQL

```bash
brew install postgresql@16
brew services start postgresql@16

# Opret database og bruger
createdb timelapse_db
psql timelapse_db -c "CREATE USER timelapse WITH PASSWORD 'dit-password';"
psql timelapse_db -c "GRANT ALL PRIVILEGES ON DATABASE timelapse_db TO timelapse;"
psql timelapse_db -c "GRANT ALL ON SCHEMA public TO timelapse;"
```

> ⚠️ **Vigtigt:** På macOS er PostgreSQL superuseren dit eget login-navn (ikke `postgres`).
> Brug `psql -d timelapse_db` (uden `-U postgres`) til alle operationer.

### Efter nye migrationer — giv altid rettigheder:
```bash
psql -d timelapse_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO timelapse;"
psql -d timelapse_db -c "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO timelapse;"
```

---

## 2. Repository

```bash
mkdir -p ~/projects
cd ~/projects
git clone git@github.com:froekjaer/timelapse-pro.git
cd timelapse-pro
```

---

## 3. Python venv (headend)

```bash
cd ~/projects/timelapse-pro/headend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Database migrationer

Kør i rækkefølge:

```bash
cd ~/projects/timelapse-pro/headend
psql -d timelapse_db -f migrations/v2_8_cmdb.sql
psql -d timelapse_db -f migrations/v2_9_security.sql
```

---

## 5. Launchd plist

Opret `/Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dk.froekjaer.timelapse-headend</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/peter/projects/timelapse-pro/headend/venv/bin/python3</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/peter/projects/timelapse-pro/headend</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/timelapse-headend.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/timelapse-headend.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL</key>
        <string>postgresql://timelapse@localhost/timelapse_db</string>
        <key>JWT_SECRET</key>
        <string>GENERER-MED: python3 -c "import secrets; print(secrets.token_hex(32))"</string>
        <key>BREAK_GLASS_ENC_KEY</key>
        <string>GENERER-MED: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</string>
        <key>SFTP_BASE</key>
        <string>/Volumes/data/timelapse-incoming</string>
        <key>FFMPEG_PATH</key>
        <string>/opt/homebrew/bin/ffmpeg</string>
        <key>ALLOWED_ORIGIN</key>
        <string>https://timelapse.froekjaer.dk</string>
        <key>COOKIE_SECURE</key>
        <string>true</string>
        <key>WEBAUTHN_RP_ID</key>
        <string>timelapse.froekjaer.dk</string>
        <key>WEBAUTHN_ORIGIN</key>
        <string>https://timelapse.froekjaer.dk</string>
        <key>TIMELAPSE_REPO_DIR</key>
        <string>/Users/peter/projects/timelapse-pro</string>
    </dict>
</dict>
</plist>
```

```bash
sudo launchctl load /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
```

### Genindlæs efter ændringer:
```bash
sudo launchctl unload /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
sudo launchctl load   /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
```

### Log:
```bash
tail -f /var/log/timelapse-headend.log
```

---

## 6. Ekstern harddisk (SFTP-storage)

```bash
# Find disk UUID
diskutil info /Volumes/data | grep "Volume UUID"

# Tilføj til /etc/fstab for konsistent mount-punkt
echo "UUID=<DIN-UUID> /Volumes/data apfs rw" | sudo tee -a /etc/fstab

# Opret SFTP-mappe
sudo mkdir -p /Volumes/data/timelapse-incoming
sudo chown peter:staff /Volumes/data/timelapse-incoming
```

> ⚠️ **Diskskift:** Formatér ny disk med samme volumenavn `data` →
> monteres automatisk på `/Volumes/data` → ingen config-ændring nødvendig.

> ⚠️ **SIP (System Integrity Protection):** macOS tillader ikke `mv` eller `rm`
> på `/Users/Shared/` via terminal. Brug `rsync` til at kopiere data og
> opdatér `SFTP_BASE` i plist i stedet for at lave symlinks.

---

## 7. nginx

```bash
brew install nginx

# Kopiér konfiguration
sudo cp ~/projects/timelapse-pro/Dokumentation/nginx.conf \
        /opt/homebrew/etc/nginx/nginx.conf

# SSL-certifikater (Let's Encrypt via certbot)
brew install certbot
sudo certbot certonly --standalone -d timelapse.froekjaer.dk
sudo mkdir -p /opt/homebrew/etc/nginx/ssl
sudo cp /etc/letsencrypt/live/timelapse.froekjaer.dk/fullchain.pem \
        /opt/homebrew/etc/nginx/ssl/
sudo cp /etc/letsencrypt/live/timelapse.froekjaer.dk/privkey.pem \
        /opt/homebrew/etc/nginx/ssl/

# Test og start
sudo nginx -t
brew services start nginx
```

---

## 8. UI (React/TypeScript)

```bash
cd ~/projects/timelapse-pro/timelapse-ui
npm install
npm run build
# dist/ serveres af nginx
```

---

## 9. Node Agent (SIEM + CMDB inventar)

```bash
sudo bash ~/projects/timelapse-pro/node-agent/install/macos.sh
```

Konfigurationsfil: `/etc/timelapse/node-agent.conf`

```ini
[agent]
device_id          = TL-MACMINI-HEADEND-TEST-1
headend_url        = https://timelapse.froekjaer.dk
inventory_interval = 300
security_interval  = 60
security_lookback  = 120
```

Log: `tail -f /var/log/timelapse-node-agent.log`

---

## 10. SSH logging (macOS Sequoia)

> ⚠️ **macOS Sequoia begrænsning:** SSH auth-events (`Failed password`,
> `Accepted publickey`) er ikke tilgængelige via `log show` eller klassiske
> logfiler. `SyslogFacility AUTH` og `LogLevel VERBOSE` i `sshd_config`
> har ingen effekt på Sequoia.
>
> SIEM-collectoren bruger i stedet:
> - `last` kommandoen for succesfulde SSH-logins
> - nginx access log for HTTP/HTTPS security events

Aktiver nginx access log (allerede i nginx.conf):
```
access_log /var/log/nginx-timelapse-access.log timelapse;
error_log  /var/log/nginx-timelapse-error.log warn;
```

---

## 11. GitHub Actions self-hosted runner

```bash
# Følg GitHub's vejledning under:
# Settings → Actions → Runners → New self-hosted runner (macOS)
```

CI-workflowen (`deploy-macmini`) kræver at runneren kan:
```bash
sudo launchctl stop/start dk.froekjaer.timelapse-headend
```

Tilføj til `/etc/sudoers` (via `sudo visudo`):
```
peter ALL=(ALL) NOPASSWD: /bin/launchctl
```

---

## 12. SFTP-bruger til edge

```bash
# Opret dedikeret SFTP-bruger
sudo dscl . -create /Users/sftpuser
sudo dscl . -create /Users/sftpuser UserShell /usr/bin/false
sudo dscl . -create /Users/sftpuser NFSHomeDirectory /Volumes/data/timelapse-incoming
sudo dscl . -passwd /Users/sftpuser <password>

# Tilføj til sshd_config
sudo bash -c 'cat >> /etc/ssh/sshd_config << EOF
Match User sftpuser
    ChrootDirectory /Volumes/data/timelapse-incoming
    ForceCommand internal-sftp
    AllowTcpForwarding no
EOF'
```

---

## Verifikation

```bash
# Headend kører
curl -s http://localhost:8000/health | python3 -m json.tool

# CMDB API
curl -s http://localhost:8000/api/cmdb/ | python3 -m json.tool

# SIEM API
curl -s http://localhost:8000/api/siem/summary | python3 -m json.tool

# Node agent kører
sudo launchctl list | grep timelapse-node-agent

# Ekstern disk monteret
ls /Volumes/data/timelapse-incoming/
```

---

## Nøglegenerering (reference)

```bash
# JWT_SECRET
python3 -c "import secrets; print(secrets.token_hex(32))"

# BREAK_GLASS_ENC_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Kendte problemer

| Problem | Årsag | Løsning |
|---------|-------|---------|
| `role "postgres" does not exist` | macOS bruger login-navn som PG superuser | Brug `psql -d timelapse_db` uden `-U` |
| `permission denied for table device_inventory` | Nye tabeller mangler GRANT | `GRANT ALL ON ALL TABLES TO timelapse;` |
| `mv: Operation not permitted` på `/Users/Shared/` | macOS SIP | Brug `rsync` + opdatér `SFTP_BASE` |
| SSH auth events mangler i SIEM | macOS Sequoia logger ikke til klassiske filer | Brug nginx access log + `last` |
| `inventory.py` fejler med `/sys/class/net` | Linux-kode på macOS | Platform-check i `_primary_interface()` |
| `DB_USER` fejler i migrations-script | macOS har ikke `postgres` bruger | Kør `DB_USER=peter bash script.sh` eller brug `psql` direkte |
---

## 13. Full Disk Access (macOS krav)

LaunchDaemon-processer har IKKE automatisk adgang til bruger-monterede volumes (ekstern disk, NAS).

**Påkrævet for at headend kan tilgå billeder på ekstern disk:**
Systemindstillinger → Beskyttelse og sikkerhed → Fuld diskadgang
→ Klik + → Navigér til:
/Users/peter/projects/timelapse-pro/headend/venv/bin/python
→ Tilføj

Genstart headend efter tilføjelse:
```bash
sudo launchctl stop dk.froekjaer.timelapse-headend
sudo launchctl start dk.froekjaer.timelapse-headend
```

> ⚠️ Uden Full Disk Access fejler `glob()` og `iterdir()` på externe diske
> med `[Errno 1] Operation not permitted` — selv for root-processer.

