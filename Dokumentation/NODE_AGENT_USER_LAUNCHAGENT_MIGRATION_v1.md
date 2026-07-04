# Node-agent — migrering fra root-LaunchDaemon til bruger-LaunchAgent (v1)

**Dato:** 2026-07-04 (nat)
**Forfatter:** Claude (mens Peter sov)
**Lukker:** R13 i `RISK_ASSESSMENT_v10.md` ("Node-agent nede på Headend")
**Status:** Forberedt, IKKE eksekveret.

---

## 0. Baggrund (bekræftet ved kodegennemgang)

- `node-agent/install/macos.sh` installerer i dag agenten som en **root-ejet
  LaunchDaemon** (`/Library/LaunchDaemons/dk.froekjaer.timelapse-node-agent.plist`,
  filer i `/opt/timelapse-node-agent`, kører som root).
- Ifølge `QA_SABSA_Reassessment_2026-06-22.md` er dette allerede identificeret som et
  konkret problem: root-ejerskabet forhindrede en rutinemæssig hotfix i at blive
  appliceret på den installerede kopi (kode-drift mellem repo og deployed agent).
  Agenten stoppede 2026-06-22 07:46 og har ikke kørt siden.
- Agenten (`node-agent/agent.py` + `collectors/inventory.py`/`security.py`) kræver
  ikke root — den læser CPU/RAM/disk-status, Homebrew-pakkeliste og OS-patch-niveau,
  alt sammen læsbart som almindelig bruger. Faktisk fungerer Homebrew-kald (`brew list`,
  `brew outdated`) BEDRE som bruger `peter` end som root, da Homebrew af design nægter
  visse operationer kørt som root.
- **Anbefaling (allerede i risikoregisteret):** genetabler som bruger-LaunchAgent under
  `peter`, ikke som root-LaunchDaemon.

## 1. Ny installationssti (bruger-ejet, ingen root nødvendig for selve agenten)

| Formål | Gammel (root) | Ny (bruger) |
|---|---|---|
| Installationsmappe | `/opt/timelapse-node-agent` (root:wheel) | `$HOME/timelapse-node-agent` (peter:staff) |
| Plist | `/Library/LaunchDaemons/...plist` | `~/Library/LaunchAgents/...plist` |
| Log | `/var/log/timelapse-node-agent.log` | `$HOME/Library/Logs/timelapse-node-agent.log` |
| Konfiguration | `/etc/timelapse/node-agent.conf` | Uændret — kun læses, tjek at den er læsbar for `peter` (se trin 3) |

## 2. Udførelsesplan

**Trin 1 — stop og fjern den gamle root-installation:**
```bash
sudo launchctl bootout system/dk.froekjaer.timelapse-node-agent 2>/dev/null || \
  sudo launchctl unload /Library/LaunchDaemons/dk.froekjaer.timelapse-node-agent.plist
sudo rm /Library/LaunchDaemons/dk.froekjaer.timelapse-node-agent.plist
sudo rm -rf /opt/timelapse-node-agent
```

**Trin 2 — bekræft konfigurationsfilen er læsbar for din bruger (ingen sudo herfra):**
```bash
ls -l /etc/timelapse/node-agent.conf
cat /etc/timelapse/node-agent.conf   # skal kunne læses uden sudo
```
Hvis `cat` fejler med "Permission denied": kør i stedet
`sudo chmod 644 /etc/timelapse/node-agent.conf` én gang (kræver stadig sudo denne ene
gang, men selve agenten skal aldrig køre som root bagefter).

**Trin 3 — installer agent-filer som din egen bruger (ingen sudo):**
```bash
mkdir -p "$HOME/timelapse-node-agent/collectors"
cp "$HOME/projects/timelapse-pro/node-agent/agent.py"                "$HOME/timelapse-node-agent/"
cp "$HOME/projects/timelapse-pro/node-agent/config.py"               "$HOME/timelapse-node-agent/"
cp "$HOME/projects/timelapse-pro/node-agent/transport.py"            "$HOME/timelapse-node-agent/"
cp "$HOME/projects/timelapse-pro/node-agent/collectors/inventory.py" "$HOME/timelapse-node-agent/collectors/"
cp "$HOME/projects/timelapse-pro/node-agent/collectors/security.py"  "$HOME/timelapse-node-agent/collectors/"
touch "$HOME/timelapse-node-agent/collectors/__init__.py"

python3 -m venv "$HOME/timelapse-node-agent/venv"
"$HOME/timelapse-node-agent/venv/bin/pip" install --quiet --upgrade pip
```

**Trin 4 — ny bruger-LaunchAgent-plist:**
```bash
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$HOME/Library/LaunchAgents/dk.froekjaer.timelapse-node-agent.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dk.froekjaer.timelapse-node-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/timelapse-node-agent/venv/bin/python3</string>
        <string>$HOME/timelapse-node-agent/agent.py</string>
        <string>--config</string>
        <string>/etc/timelapse/node-agent.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/timelapse-node-agent.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/timelapse-node-agent.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
```

**Trin 5 — indlæs og verificér (ingen sudo — LaunchAgents kører altid som den bruger
der indlæser dem, i modsætning til LaunchDaemons):**
```bash
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/dk.froekjaer.timelapse-node-agent.plist"
sleep 3
launchctl print gui/$(id -u)/dk.froekjaer.timelapse-node-agent | grep -E "state|pid"
tail -20 "$HOME/Library/Logs/timelapse-node-agent.log"
```
Forventet: `state = running`, en gyldig `pid`, og logs der viser vellykkede POST'er til
`/inventory/{device_id}` uden fejl.

**Trin 6 — bekræft i CMDB:** åbn CMDB-siden i UI'en for enheden (formentlig
`TL-MACMINI-HEADEND-TEST-1`, jf. den gamle installations-scripts default `DEVICE_ID`)
og tjek at "sidst set"/inventory-tidsstemplet nu er friskt (inden for
`inventory_interval`, default 300 sekunder).

## 3. Opfølgning — ret selve install-scriptet

`node-agent/install/macos.sh` bør opdateres til at følge samme mønster fremover (dropper
`sudo`-kravet og skriver til bruger-stier fra start), så en fremtidig geninstallation
ikke falder tilbage i root-mønsteret. Dette er IKKE gjort her — kun selve
genetableringen på den kørende Mac Mini. Foreslår at Codex eller jeg tager
script-opdateringen som en separat, lille opgave, når I er klar.

## 4. Rollback

Hvis noget går galt: den gamle root-installation er kun fjernet i trin 1, ikke
destrueret andre steder — hvis I har en backup af `/opt/timelapse-node-agent` og
plist-filen, kan de genskabes og genindlæses med `sudo launchctl load`. Da agenten kun
LÆSER systemdata og POSTer til headend (ingen skriveoperationer på selve Mac'en udover
sin egen logfil), er der minimal risiko for skade ved fejl undervejs.
