# TimeLapse Pro — Services & Drift (fælles kilde til sandhed)

**Formål:** ét autoritativt driftsdokument som **Claude, Codex og Peter** alle arbejder ud fra,
så vi ikke gætter, genudleder eller modsiger hinanden om services, porte, stier og genstart.
Opdateres når noget ændres. Sidst rørt: 2026-07-03.

> Rollefordeling vi har erfaret: **Claude** kører i en sandbox uden adgang til selve Mac'en
> (kan ikke nå launchd, Postgres, volumener eller taste i Terminal) → laver kode, analyse,
> scripts og diagnose. **Codex** kan røre OS-laget → genstart, volumen-/diskfix, sudo.
> Peter eksekverer/godkender. Del derfor: Claude skriver kommandoen, Codex/Peter kører den.

---

## 1. Services og hvor de bor

| Service | Hvor | Port/bind | Noter |
|---|---|---|---|
| Headend (FastAPI/uvicorn) | system LaunchDaemon `dk.froekjaer.timelapse-headend` | `127.0.0.1:8000` | Starter via `/usr/local/sbin/timelapse-headend-start`, venv `~/.venvs/timelapse-headend` |
| PostgreSQL | system LaunchDaemon `dk.froekjaer.timelapse-postgresql` | `localhost:5432` | DB `timelapse_db`, brugere `timelapse` / `peter` |
| UI dev server | system LaunchDaemon `dk.froekjaer.timelapse-ui` | `127.0.0.1:5173` | Vite dev server; nginx proxyer normalt offentlig trafik |
| WiFi watchdog | system LaunchDaemon `dk.froekjaer.timelapse-wifi-ensure` | — | Tjekker hvert minut WiFi `en1`, router `192.168.86.1`, SSID `p-froekjaer` |
| Ollama (lokal vision) | bruger-service `homebrew.mxcl.ollama` | `127.0.0.1:11434` | Model `qwen2.5vl:7b`; starter pt. efter bruger-login |
| nginx | system LaunchDaemon `dk.froekjaer.timelapse-nginx` | `80/443` (mål: Cloudflare Tunnel) | Serverer UI, proxy `/api` → `127.0.0.1:8000` |
| Log | fil | — | `~/Library/Logs/timelapse-headend.log` |
| Captures/billeder | volumen | — | `sftp_base`-setting = `/Volumes/data-fast/timelapse-incoming/canonical-images` |
| Headend runtime-env | lokal systemfil | — | `/etc/timelapse/headend.env` (`root:staff`, ikke i Git) |

---

## 2. Genstart og "efter ændringer"

```bash
# Foretrukken genstart (frisk proces, indlæser ny kode):
sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend

# Fuld af-/genindlæsning (brug hvis kickstart ikke tager):
sudo launchctl bootout system /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist

# Efter FRONTEND-ændringer skal UI bygges:
cd ~/projects/timelapse-pro/timelapse-ui && npm run build && cd ..

# Verificér ALTID bagefter:
curl -s -o /dev/null -w "headend: %{http_code}\n" http://127.0.0.1:8000/api/health   # vil have 200
launchctl print system/dk.froekjaer.timelapse-headend | grep -E "state = |pid = |last exit"
```

Tolkning: `state = running` + ny `pid` + `headend: 200` = oppe med ny kode.
`state = xpcproxy` + `headend: 000` lige efter = stadig under opstart — vent 20-30 sek og tjek igen.

**Vigtigt:** En kørende headend bruger den kode der blev indlæst ved opstart. Kode-ændringer på
disken slår først igennem efter genstart. Undtagelse: separate CLI-scripts (`backfill.py`,
`camera_profile.py`, `compare_ollama_gemini.py`) starter en frisk proces og bruger derfor
**altid** koden på disken — de kræver ikke genstart.

## 2b. Mac Mini autostart efter crash/strøm

Status 2026-07-03:

- `sudo systemsetup -getrestartpowerfailure` = **On**.
- `sudo systemsetup -getrestartfreeze` = **On**.
- `pmset`: system sleep = `0`, disk sleep = `0`, WOL/tcpkeepalive = `1`.
- Headend, PostgreSQL, nginx og UI er flyttet fra bruger-LaunchAgents til system-LaunchDaemons,
  så de kan starte uden Peters GUI-session, når macOS først er bootet.
- WiFi er sat først i netværksservice-rækkefølgen, og
  `dk.froekjaer.timelapse-wifi-ensure` kører ved boot og hvert 60. sekund. Den slår WiFi til,
  forsøger re-join til `p-froekjaer`, fornyer adresse og power-cycler WiFi ved behov.

**Vigtig begrænsning:** FileVault er **On**. Efter et rigtigt strømudfald eller hårdt reboot kan
macOS stoppe i FileVault/pre-boot unlock, før normal WiFi, launchd-systemservices og volumes er
tilgængelige. Fuld unattended recovery kræver enten kablet net + en strategi for FileVault-unlock
eller at FileVault bevidst slås fra på den produktions-Mac, hvis fysisk risiko er acceptabel.

---

## 3. Det tilbagevendende data-fast I/O-problem (HØJ prioritet)

**Symptom:** `Bootstrap failed: 5: Input/output error` ved genstart; og når volumenet er ramt:
login fejler (401/`webauthn-begin` 404 fordi DB/filer ikke kan nås), korrupte/grå/blanke frames
(tagget `unusable_image`), og services der ikke kan loade.

**Hurtig Codex/Peter-diagnose:**
```bash
diskutil info /Volumes/data-fast | sed -n '1,25p'
diskutil verifyVolume /Volumes/data-fast
log show --last 2h --predicate 'eventMessage CONTAINS[c] "data-fast" OR eventMessage CONTAINS[c] "I/O"' --style compact
```

**Midlertidig workaround (Codex' fix - kræver sudo):**
```bash
sudo xattr -rd com.apple.quarantine ~/projects/timelapse-pro ~/.venvs/timelapse-headend
sudo mdutil -i off /Volumes/data-fast
```
**Ægte fix (udestår):** volumen-/diskhelbred. `diskutil verifyVolume /Volumes/data-fast`,
tjek Console/`log show` for I/O-fejl. Overvej at flytte venv/home væk fra volumenet hvis det er
en fejlende/flaky disk. Indtil dette er løst er genstarter og UI-batch upålidelige.

**Codex-regel:** hvis en genstart fejler med I/O-fejl, så lav først et kort health-check og notér
fund i `Dokumentation/HANDOVER_LOG.md`. Ret ikke samtidig applikationskode; hold OS-/diskfix og
kodeændringer adskilt, så Claude/Peter kan skelne drift fra funktion.

---

## 4. Kendte faldgruber

- **WebAuthn/Touch ID giver 404** (`/api/auth/webauthn/login-begin`) = brugeren har ingen
  registreret passkey (eller findes ikke). Det er rutens egen besked, ikke en manglende rute.
  Løsning: log ind med adgangskode (blå "Log ind"), ikke Touch ID-knappen.
- **Login 401** = forkert brugernavn/adgangskode (eller `is_active=false`) — IKKE backend nede.
- **JWT_SECRET** skal være stabilt i LaunchAgent på tværs af genstarter (ellers invalideres
  sessioner). En gyldig session kan mønstres fra `JWT_SECRET` (cookie `tl_session`).
- **Manglende modul `exifread`** = harmløs advarsel; `pip install exifread` i venv.

---

## 5. AI-tagging — services og kørsel

- **Strategi pr. kunde/site** (`ai_strategy`): `cloud_only` (Gemini), `local_only` (Ollama,
  privacy/pris), `local_then_cloud` (Ollama først, eskalér de svære til Gemini), `technical_only`.
- **Billedbudget:** Gemini 4 MB/3072 px (`TIMELAPSE_GEMINI_MAX_IMAGE_*`); Ollama 1024 px/1,5 MB,
  justerbart via DB-settings `ollama_max_image_edge` / `ollama_max_image_bytes`.
- **Re-tag i bulk:**
  - CLI (frisk kode, synkron, fuld pris): `backfill.py --all --force --strategy cloud_only`.
  - UI/Batch API (`/api/admin/ai-batch/start`, ~50% pris, async): **kræver at headenden kører
    den nye kode** (genstart først!) og `force_ai=true` for at re-tagge alt.
- **Selvlærende baseline:** `camera_profile.py --all --apply` lærer "normalt for dette kamera"
  af tag-historikken (static vs dynamic). Kør efter en ren re-tag for bedst resultat; gerne på
  natligt skema.
- **Værktøjer (CLI, ingen genstart krævet):** `backfill.py`, `camera_profile.py`,
  `normalize_existing_tags.py`, `compare_ollama_gemini.py` — alle i `headend/ai/`.

---

## 6. Arbejdsdeling Claude ⇄ Codex (forslag)

- **Claude:** kode, AI/prompt, dataanalyse, scripts, diagnose ud fra logs/DB-output Peter indsætter.
  Kan IKKE: nå Mac'en, køre launchd/psql/sudo, taste i Terminal.
- **Codex:** OS-/drift-lag — genstart, volumen/disk, sudo, netværk.
- **Fælles regel:** når noget ved services/porte/stier/genstart ændres, opdatér **dette dokument**
  så begge assistenter (og Peter) deler samme billede. Claude skriver kommandoer; Codex/Peter kører.

## 7. Checkpoints, Git og backup

- Kodeændringer bør ske på branches med tydeligt ejerskab, fx `codex/...` eller `claude/...`.
- Hvis arbejdstræet er beskidt, må Codex ikke lave bred `git add .`; brug konkrete filer eller
  et separat Git-index ved checkpoints.
- Ved større drifts-/AI-ændringer: lav patch-backup i `/private/tmp/timelapse-ai-backups/` før push.
- Push checkpoints undervejs på lange forløb, så Peter kan rulle tilbage uden at rekonstruere chat.
- Dokumentationsfilerne her er fælles sandhed. Ændringer i dem bør være små, daterede og konkrete.

## 8. Driftsovervågning og Edge QA signaler

Claude bygger headendens drifts-/observability-system. Codex leverer Edge QA/NPU-signalerne og
kontrakten, som overvågningen skal bruge. Se også
`HANDOVER_Claude_Codex_arbejdsdeling.md` §8 og `Codex_Edge_AI_NPU_Modes_2026-06-28.md`.

Headend-overvågningen bør aggregere og alarmere på felter fra capture/sidecar, ikke genklassificere
billedkvalitet fra pixels som primær logik. Minimumssignaler:

- `quality_flag`, `quality_passed`, `probable_cause`, `confidence`, `quality_dimension`
- `autonomous_optimizer.score`, `autonomous_optimizer.recommendations`,
  `autonomous_optimizer.control_plan`
- `npu.available`, `npu.engine`, `npu.model_path`, `npu.label`, `npu.confidence`

Manglende Edge QA-felter i gamle billeder skal vises som `unknown`/`not_available`, ikke som
driftsfejl. Reelle fejl er fx stigende andel `quality_flag=error`, mange `hash_mismatch`, gentagne
`snow_or_dirt_on_lens`, vedvarende under-/overeksponering eller `npu.available=false` på kameraer,
der er konfigureret til `npu_first`.
