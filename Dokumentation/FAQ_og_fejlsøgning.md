# TimeLapse Pro — FAQ & fejlsøgning (selvbetjening)

**Til Peter** (når du selv vil løse noget) **og til Claude/Codex** (så vi giver samme svar på
tværs af sessioner). Symptom → hurtig diagnose → løsning. Detaljer i
`SERVICES_OG_DRIFT_kilde_til_sandhed.md`. Sidst rørt: 2026-07-03.

> **Fælles regel:** dette er kanonisk i `Dokumentation/` (git-sporet, begge assistenter
> opdaterer her). En **nød-kopi** ligger på boot-drevet (`~/Claude/Projects/Timelaps/`),
> så den kan læses selv når `data-fast` er nede.

> **Når noget ændres:** opdatér først den kanoniske fil i repoet. Kopiér derefter FAQ'en til
> nød-kopien på boot-drevet:
> ```bash
> cp Dokumentation/FAQ_og_fejlsøgning.md ~/Claude/Projects/Timelaps/FAQ_og_fejlsøgning_NØDKOPI.md
> ```

---

## "Jeg kan ikke logge ind"

**Hurtig diagnose — kør:**
```bash
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```

- **`health: 200`** → backend kører. Så er det login-stien, ikke systemet:
  - Brugte du **Touch ID-knappen**? Den fejler hvis du ikke har en registreret passkey
    (`webauthn-begin` → 404). **Brug i stedet den blå "Log ind"** med brugernavn + adgangskode.
  - Får du afvist adgangskoden (401)? Tjek brugernavn/adgangskode. Se rigtige brugere:
    ```bash
    psql -U timelapse timelapse_db -c "SELECT username, role, is_active FROM users ORDER BY id;"
    ```
- **`health: 000` eller `502`** → backend er **nede**. Gå til afsnittet "UI/headend svarer ikke".

---

## "UI'et / headenden svarer ikke" (health 000/502)

```bash
# Genstart (foretrukket):
sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
sleep 25
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```

- **Bliver 200** → oppe igen.
- **`Bootstrap failed: 5: Input/output error`** eller bliver hængende → det er
  **data-fast-volumenet** (se nederst). Codex/Peter kører workaround'en, derefter genstart.

---

## "Tags på billederne ser dårlige ud"

Tjek i rækkefølge — det er som regel billedet, ikke modellen:

1. **Er billedet faktisk fint?** Åbn det i galleriet. Hvis det er gråt/blankt/korrupt →
   det er capture-/disk-problem (ofte data-fast I/O), ikke AI. `unusable_image` er så korrekt.
2. **Kører den nye kode?** Headenden skal være **genstartet** efter kodeændringer
   (CLI-scripts kræver det ikke, men den løbende worker/UI-batch gør).
3. **Sparsomme tags (kun vejr)?** Var symptomet før billedopløsning + scene-prompt blev rettet.
   Re-tag billedet og se: `backfill.py --ids <id> --force --strategy cloud_only`.
4. **Falsk `unusable_image` på et fint billede?** Var en for aggressiv regel — nu strammet.
   Re-tag for at bekræfte.

---

## "Hvordan genstarter jeg / efter kodeændringer?"

```bash
# Efter FRONTEND-ændringer: byg UI først
cd ~/projects/timelapse-pro/timelapse-ui && npm run build && cd ..
# Genstart headend (indlæser ny backend-kode)
sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
sleep 25
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```
CLI-scripts (`backfill.py`, `camera_profile.py`, `compare_ollama_gemini.py`,
`normalize_existing_tags.py`) bruger altid koden på disken — de kræver **ikke** genstart.

---

## "Hvordan re-tagger jeg billeder?"

- **Få billeder / test (synkron, frisk kode):**
  ```bash
  SFTP_BASE=$(psql -U timelapse timelapse_db -tA -c "SELECT COALESCE((SELECT value FROM settings WHERE key='sftp_base'),'/Volumes/data')") \
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/backfill.py --limit 10 --force --strategy cloud_only
  ```
- **Alle (~26.000), billigst:** via UI → **AI-batch** med `force` (kræver headend på ny kode).
- **Specifikke id'er:** `backfill.py --ids 26406,26410 --force --strategy cloud_only`.
- **Spredt over perioden + resultatfil:** `--site "..." --limit 50 --spread --out <fil>.json`.

---

## "Hvordan opdaterer jeg de selvlærende baselines?"

```bash
~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all          # dry-run
~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all --apply  # gem
```
Bedst kørt **efter** en ren re-tag. Kan sættes på natligt skema.

---

## "Ollama vs Gemini — hvad bruger jeg hvornår?"

- `cloud_only` (Gemini): bedst kvalitet. `local_only` (Ollama): privacy/pris, billeder forlader
  ikke huset. `local_then_cloud`: Ollama tager de nemme, eskalerer de svære til Gemini.
- Sammenlign selv: `compare_ollama_gemini.py --sites "..." --per-site 5 --out <fil>`.

---

## Data-fast volumen-problemet (rod til login/genstart/korrupte billeder)

**Symptom:** `Bootstrap failed: 5: Input/output error`, login der fejler, grå/blanke frames.
**Workaround (Codex/Peter, sudo):**
```bash
sudo xattr -rd com.apple.quarantine ~/projects/timelapse-pro ~/.venvs/timelapse-headend
sudo mdutil -i off /Volumes/data-fast
sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
```
**Ægte fix (udestår):** `diskutil verifyVolume /Volumes/data-fast` + tjek Console for I/O-fejl;
overvej at flytte venv/home væk fra volumenet hvis disken er flaky.

## "Mac Mini startede ikke rigtigt efter crash/strøm"

Status 2026-07-03: systemet er sat op til serverdrift:

```bash
sudo systemsetup -getrestartpowerfailure
sudo systemsetup -getrestartfreeze
pmset -g custom
launchctl print system/dk.froekjaer.timelapse-headend
launchctl print system/dk.froekjaer.timelapse-postgresql
launchctl print system/dk.froekjaer.timelapse-nginx
launchctl print system/dk.froekjaer.timelapse-wifi-ensure
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```

Forventet: `Restart After Power Failure: On`, `Restart After Freeze: On`, `sleep 0`,
`disksleep 0`, og `health: 200`.

Hvis maskinen står stille før login efter strømudfald: tjek FileVault. FileVault er sikkerhed,
men forhindrer fuld unattended boot, fordi macOS kan kræve unlock før normal WiFi/services.

WiFi-watchdoggen kan tjekkes med:

```bash
tail -n 50 /var/log/timelapse-wifi-ensure.log
networksetup -listnetworkserviceorder
sudo wdutil info
```

Forventet: WiFi er service nr. 1, `Primary IPv4` er `en1`, og loggen siger at routeren er
reachable.

---

## Hvor ligger tingene (hurtig reference)

| Hvad | Hvor |
|---|---|
| Repo / kode | `~/projects/timelapse-pro` |
| Python venv | `~/.venvs/timelapse-headend` |
| Headend-log | `~/Library/Logs/timelapse-headend.log` |
| Billeder (sftp_base) | `/Volumes/data-fast/timelapse-incoming/canonical-images` |
| DB | `psql -U timelapse timelapse_db` |
| Headend | `127.0.0.1:8000` · UI `127.0.0.1:5173` · Ollama `127.0.0.1:11434` · Postgres `5432` |
| Systemservices | `/Library/LaunchDaemons/dk.froekjaer.timelapse-*.plist` |
| Runtime-env | `/etc/timelapse/headend.env` |
| WiFi-watchdog | `/usr/local/sbin/timelapse-wifi-ensure`, `/etc/timelapse/wifi.env`, `/var/log/timelapse-wifi-ensure.log` |

---

## "Claude og Codex siger noget forskelligt"

Brug denne rækkefølge:

1. Tjek `SERVICES_OG_DRIFT_kilde_til_sandhed.md` for services, porte, stier og genstart.
2. Tjek `HANDOVER_LOG.md` for seneste faktiske handlinger/testoutput.
3. Hvis dokumenterne ikke dækker situationen: kør en lille diagnose/dry-run og opdatér dokumentet
   med resultatet bagefter.

Regel: empiri og dokumenteret output vinder over hukommelse fra chat.
