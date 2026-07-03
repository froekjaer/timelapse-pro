# TimeLapse Pro — Sessionssammendrag 13. juni 2026

Debugging- og verifikationssession på Mac Mini headend. Mål: bekræfte at opdateringsflowet og capture→upload-kæden virker, før maskinen sættes på internettet. Endte med at afdække og rette en reel produktionsfejl (upload 500) plus to arkitektoniske huller der skal lukkes før produktion.

Maskinen er **ikke** på internettet endnu (bevidst — først når alt er verificeret). CrushFTP er ikke installeret/startet endnu.

---

## 1. Løst i denne session

### 1.1 Edge image-upload returnerede HTTP 500 (LØST)

**Symptom:** Hver `POST /api/captures/TL-C87FF9587CA0/files` (5–6 MB multipart) gav `500` fra nginx (nginx' egen HTML-fejlside, ikke FastAPI-JSON). Små requests (heartbeat, config, policy, capture-metadata uden `/files`) virkede fint. Også ramt: `/api/siem/events/...` og `/api/admin/backup/edge-upload/...`.

**Rodårsag:** nginx' temp-mapper var ejet af `nobody:0700`, mens nginx-workers kører som `peter`. nginx kunne derfor ikke skrive disk-bufrede request-bodies → 500. Små requests buffres i RAM og rammer aldrig disk, derfor virkede de.

**Hvorfor `nobody`:** Levn fra et tidligere tidspunkt hvor nginx blev startet som root (fx `sudo nginx`). Uden et `user`-direktiv falder workers tilbage på compile-time default `nobody`, som ejede de temp-mapper der blev oprettet dengang. De blev aldrig ryddet op.

**Hvorfor `chown` alene ikke holdt:** En `sudo chown` til `peter` blev overskrevet ved næste `brew services restart`, fordi nginx genbrugte/genskabte de eksisterende mapper med `nobody`.

**Den varige løsning (udført):**
1. `brew services stop nginx`
2. Slet alle temp-mapper mens nginx er stoppet (`nginx-client-body-temp`, `nginx/{client_body_temp,proxy_temp,fastcgi_temp,scgi_temp,uwsgi_temp}`)
3. `brew services start nginx` (som peter) → mapperne genskabes med korrekt ejer

**Verificeret:** Uploads gik fra 500 → 200 fra kl. 08:19. Error-loggen viser nu kun harmløst `[warn] ... buffered to a temporary file`. 61 billeder fra 13. juni i databasen, nyeste id 24837 kl. 16:59.

**Regel fremover (til dokumentation):** Start aldrig nginx med `sudo nginx` på denne maskine. Brug altid `brew services {start,stop,restart} nginx` eller `nginx -s reload` (uden sudo). Holder master/workers/temp-mapper konsistent som `peter`. Passer også med kommende flytning til port 18443 (≥1024 kræver ikke root).

### 1.2 Mistaget parallel-CMDB oprydning (udført i tidligere session, bekræftet ren)

En tidligere session havde fejlagtigt bygget et parallelt CMDB-system. Det blev fjernet kirurgisk (3 main.py-patches fjernet, `headend/cmdb/`-dir + `cmdb_models.py` slettet) uden at røre Peters egen `headend/cmdb.py` (30 KB) og hans uforpligtede main.py-arbejde. `py_compile` OK. **Princip: Peters eksisterende CMDB/update-system er det autoritative — byg aldrig parallel infrastruktur.**

---

## 2. Verificeret som fungerende

**Backend er sundt.** Tidligere "hængninger" skyldtes test mod den eksterne port `:10443` (ikke konfigureret endnu), ikke kodefejl.

- uvicorn svarer lokalt på 3–5 ms på alle `/api/updates/*`
- `/api/updates/pending`, `/device-matrix`, `/artifacts`, `/{id}/flow-status` — alle 200 med korrekt JSON
- Login virker (HttpOnly cookie, MFA springes over når `mfa_enabled=false`)
- Capture→upload→database-kæde: hel og verificeret (61 billeder i dag)
- Backups gemmes (2,7 MB `.tar.gz`-arkiver i `/Volumes/data/backup/edge-backups/...`)

**OS-opdateringsflow — bevist end-to-end (trin 1–3):**
- Edge rapporterer OS-inventory → `device_inventory.os_packages` (64 KB, opdateret 03:00 nattligt)
- `POST /api/updates/os-catalog/import-apt-list` med ægte edge-pakker → reconcile grupperede korrekt 3 `os_security` (høj) + 3 `os_updates` (lav), skrev plan + katalog til `/var/lib/timelapse/update-{plans,catalogs}/`, genererede bundle-requests, opdaterede blocked updates id 3 + id 5 → status "updated"
- Design bekræftet korrekt: **edge må ikke køre `apt-get upgrade` selv**; OS-opdateringer er headend-styrede signerede offline-artefakter fra lab-mirror (CRA/supply-chain). Edge er kun installed-state-reporter.
- De 142 sikkerheds- + 62 funktionelle OS-opdateringer står korrekt `blocked` indtil bundle bygges (`build_os_bundle.py`).

---

## 3. Afdækkede arkitektoniske huller (skal løses før produktion)

### 3.1 config_version dækker ikke globale settings (IKKE rettet endnu)

`config_version = MD5(device.device_config)` — hashes kun over device-laget. Men den config edge henter via `get_config` indeholder **også** globale settings (`_get_setting`) og hierarkisk merge (Global→Kunde→Site→Device via `config_overrides` + `_deep_merge`).

**Konsekvens — to fejltyper:**
- **Falsk negativ:** Ændringer på Global/Kunde/Site-niveau ændrer ikke device_config-hashen → edge opdager dem aldrig → central styring (fx ISO) når ikke ud.
- **Tavs ændringsvej:** `PUT /api/admin/settings` (`update_settings`, linje 9959) bumper slet ikke config_version.

**Foreslået fix (kirurgisk, kun headend — edge skal ikke ændres):**
I `get_config` (linje ~2272), erstat:
```python
cfg["config_version"] = device.config_version or ""
```
med en frisk hash over hele den udleverede cfg (kanonisk, sorteret):
```python
import hashlib as _hl_cfgver
_cfg_for_hash = {k: v for k, v in cfg.items() if k != "config_version"}
cfg["config_version"] = _hl_cfgver.md5(_canonical_json(_cfg_for_hash).encode("utf-8")).hexdigest()
```
`_canonical_json` findes allerede (sort_keys, kompakt). Den lagrede `device.config_version` (linje 2324, 8273) bevares uændret — edge læser kun `config_version` fra cfg/data-dict'en (agent.py 955, 960, 1597-1598, 1720-1721), aldrig device-objektet direkte. Patch verificeret sikker via grep.

**Forudsætning før dette giver mening:** se 3.2 (rapport-data forurener hashen og gør den ustabil).

### 3.2 Rapporterings-data ligger i device_config og sendes unødigt til edge (IKKE rettet endnu)

`device_config` er **121 KB**, hvoraf `camera_params` alene er **115 KB** (en liste på 367 elementer = kameraets fulde capability-dump, alle Choice-værdier for shutter/iso/aperture/focus).

**Tre felter er edge→headend rapportering til UI-visning, IKKE headend→edge styring:**
- `camera_params` (115 KB) — edge læser dem **aldrig** (grep tomt). Skrives kun af LAB-endpoint `POST /api/lab/{device_id}/params` (linje 9459).
- `camera_profile` (~1,4 KB) — edge **vælger profil selv** ud fra detekteret kameramodel via indbyggede `CAMERA_PROFILES` i `gphoto2_driver.py`; dette felt er edge's rapport om hvad den valgte.
- `wifi_data` (~2 KB) — `{"type":"scan","networks":[...]}`, resultat af edge's lokale `nmcli`-scan, rapporteret op. Edge konfigurerer WiFi lokalt via `bootstrap_cli.py`, ikke fra dette felt.

**Bekræftet: ingen regression.** WiFi og kameraprofil håndteres bevidst lokalt på edge (nmcli-bootstrap + selvvalgt profil). De tre DB-felter er rapportering, ikke styringskanaler. Edge læser dem ikke tilbage — korrekt.

**Konsekvens:**
- De 115 KB sendes retur til edge ved **hvert config-poll** (hvert 5. min via `get_config` linje 240-242 `node_cfg = json.loads(device.device_config)`), selvom edge ikke bruger dem. På modem/mobilforbindelse: ~35 MB/døgn spildt.
- De forurener config_version-hashen og gør den ustabil (capabilities/scans svinger), hvilket underminerer "send kun ved ændring".

**Foreslået fix:** Udelad rapport-felterne (`camera_params`, `camera_profile`, `wifi_data` — bekræft endeligt hvilke) fra det `cfg` der sendes til edge OG fra hashen. Edge mister intet. Arkitektonisk renere på sigt: flyt disse rapport-felter helt ud af `device_config`-kolonnen til eget felt/tabel (de er rapporteret tilstand, ikke config).

**Fremtidssikring:** Hvis central WiFi- eller profil-styring ønskes senere, skal det være *separate ønskede-værdi-felter* (fx `wifi_config` med credentials der skal bruges), adskilt fra disse `*_data`/scan-rapporter.

### 3.3 "Send kun ved ændring" er ikke implementeret — edge henter altid hele config (IKKE rettet)

Edge's `fetch_config` (headend_client.py 137) kalder bare `GET /config/{id}` uden at sende sin nuværende version. Headend's `get_config` (linje 2008) tager ikke imod nogen version og har ingen 304-logik — returnerer altid hele config'en.

**Oprindeligt formål (Peter):** spare data ved kun at overføre når config faktisk er ændret. Dette er **ikke** opfyldt i nuværende kode.

**Foreslået fix — HTTP 304 Not Modified:**
- Headend: beregn config_version-hash tidligt, sammenlign med `If-None-Match`-header fra edge, returnér `304` med tom body hvis uændret (~200 bytes i stedet for 121 KB).
- Edge: send gemt `config_version` i `If-None-Match`, behandl 304 som "behold nuværende".
- **Godt nyt:** edge's `_get()` (headend_client.py) returnerer i dag `False, None` på alt der ikke er 200 — inkl. 304 → edge behandler det allerede sikkert som "behold config". 304 fra headend ville virke med det samme; pænere edge-håndtering (skelne 304 fra fejl i log) kan komme senere.

**Rækkefølge (aftalt):** 3.1 (config_version-hash over hele cfg) → derefter UI-toggle → derefter gennemgang af hvad UI ellers mangler. 3.2 (rensning af rapport-data) er forudsætning for at 3.1 giver en stabil hash. 3.3 (304) bygger oven på en korrekt, stabil hash.

**Afvist idé:** inter-frame billedkompression (kun sende pixel-delta mellem billeder). Forkert for denne use case: timelapse-frames 60 min fra hinanden deler næsten ingen pixels (delta ≈ fuldt billede), OG billederne er GDPR/CRA-beviser der hver især skal kunne verificeres uafhængigt (SHA-256, XMP) — en delta-kæde ødelægger den egenskab. Per-billede JPEG-kvalitet (eksisterende quality-thresholds) er den rigtige vej til billed-databesparelse.

---

## 4. Upload-koordinering / flow-kontrol (slot-mekanisme) — beslutning truffet, ikke implementeret

**Eksisterende mekanisme (fundet, fuldt designet, men slået FRA):**
- Headend (main.py 2040-2046): `upload_slot_cycle_seconds`=600, `upload_slot_window_seconds`=90, device-offset = `SHA256(device_id) % span` (deterministisk forskudt vindue pr. enhed, så enheder ikke kolliderer), `max_pending_per_window`=3, **`upload_slot_enforced`=false** (default).
- Edge (`_upload_slot_state`, agent.py 1685): beregner selv sit vindue ud fra uret (decentral, ingen round-trip). Uden for vindue → billeder **køes holdbart lokalt** (intet tabes), sendes i næste vindue. Når enforced=false returnerer den `(True, 0, 999999)` = altid tilladt.

**Det forklarer 08:19-bygen:** Da hele den ophobede billedkø ramte på én gang efter nginx-genstart, var slot ikke håndhævet → ukoordineret byge hamrede uvicorn → backup-request (kl. 08:21) nåede ikke frem inden for nginx' 60 s default-timeout (`/api/` har ingen eksplicit `proxy_read_timeout`).

**Status pr. nu:** capture-uploads er koblet på slot-mekanismen (agent.py 1631), men **backup går udenom** (agent.py 987 — `upload_edge_backup` tjekker ikke slot), og heartbeat går udenom (godt — liveness skal være fri).

**Peters beslutning:** Aktivér slot-kontrol, og udvid den til at omfatte **al** dataoverførsel — både op (capture, backup) og ned (artefakter, OS-bundles, apt-debs). Video får en **separat kanal senere**. Heartbeat forbliver sandsynligvis fri (bekræftes).

**Vigtig afhængighed:** Slot-aktivering kræver at config_version-hullet (3.1) er løst først, ellers når `enforced=true` aldrig ud til edge. Settings-feltet findes desuden ikke i UI endnu.

**Note om downloads:** Når slot udvides til downloads, skal en enhed der venter på en sikkerhedsopdatering ikke kunne blokeres af sit upload-vindue — kræver designovervejelse (separate kvoter for kritiske downloads).

**Note om nginx-timeout:** Den oprindeligt foreslåede `proxy_read_timeout 300s` på `/api/` blev IKKE udført — med korrekt flow-kontrol opstår bygerne ikke, så en stor timeout er en krykke. En moderat timeout (fx 120 s) kan stadig være et fornuftigt sikkerhedsnet. Bemærk: openwebui-serverblokken har 3600s timeouts (linje 90-91, 115-116), men timelapse `/api/` (linje 171) arver default 60 s.

---

## 5. uvicorn-driftsobservation (til senere)

uvicorn kører som **én proces, ingen `--workers`** (plist: `uvicorn main:app --host 0.0.0.0 --port 8000`, kører som root, PID skiftende). Ét event-loop. Både `/files` og backup bruger `await read()` med synkron `out.write(chunk)` — den synkrone disk-write blokerer event-loopet kortvarigt pr. bid. En byge serialiseres derfor og kan skabe kø.

**Forbedringer til senere (ikke akut):**
- Flere uvicorn-workers, ELLER (bedre for synkron disk-I/O) flyt `out.write()` til `await run_in_threadpool(...)` så uploads ikke blokerer event-loopet.
- Med slot-kontrol aktiveret reduceres behovet, da byger forhindres ved kilden.

---

## 6. Pre-internet checkliste (Peters mål: assessment før maskinen åbnes mod nettet)

Ikke påbegyndt — afventer ovenstående. Til senere assessment:
- nginx flyttes fra 80/443 → **18443** (router forwarder public:10443 → Mac:18443). Frigør 80/443/21/22 til CrushFTP.
- Cert til `timelapse-api.froekjaer.dk` (nuværende cert dækker kun `timelapse.froekjaer.dk` + `openwebui.froekjaer.dk`).
- CrushFTP installeres og sameksisterer på 80/443/21/22 (kører ikke endnu).
- Go/no-go assessment fra dette punkt.

---

## 7. Oprydning / løse ender

- **Test-bruger `claudetest`** (super_admin, mfa off, password `Test1234flow`) blev oprettet i PostgreSQL `timelapse_db` til flow-test. **Bør slettes** når testning er færdig: `DELETE FROM users WHERE username='claudetest';` (husk `DATABASE_URL=postgresql://timelapse@localhost/timelapse_db` hvis kørt fra script).
- **SQLite-rod ryddet:** mit testscript ramte ved en fejl sqlite-defaulten (`sqlite:///./timelapse_headend.db`) fordi `DATABASE_URL` ikke er sat i shell (kun i plist — bevidst, da config sættes i UI+DB, ikke .env). SQLite-filerne blev slettet. **Læring: sæt altid `DATABASE_URL=postgresql://timelapse@localhost/timelapse_db` foran scripts der køres fra shell.**
- nginx.conf-backups fra sessionen ligger i `/opt/homebrew/etc/nginx/nginx.conf.bak-*` (hvis config_version-patch m.m. køres, tag tilsvarende main.py-backup).

---

## 8. Konkret næste-skridt-rækkefølge (som aftalt)

1. **Løs config_version-hullet** (3.1) — hash hele den udleverede cfg kanonisk. Forudsat at rapport-data (3.2) renses ud først/samtidig, så hashen er stabil.
2. **Rens rapport-data** (3.2) — udelad `camera_params`/`camera_profile`/`wifi_data` fra edge-config + hash. Overvej at flytte dem ud af `device_config`-kolonnen.
3. **Implementér 304** (3.3) — opfylder "send kun ved ændring".
4. **UI-toggle** til upload-slot-settings + config_version-bump ved ændring.
5. **Gennemgå hvad UI ellers mangler.**
6. **Aktivér slot-kontrol**, start med rummeligt vindue, verificér på edge-log (`remaining_s` skifter fra 999999 til reelt tal), stram derefter.
7. **Udvid slot til backup + downloads** (edge-kodeændring; design kvoter for kritiske downloads).
8. **Pre-internet checkliste** + go/no-go.

---

## Nøglefakta / konstanter brugt i sessionen

- Repo: `/Users/peter/projects/timelapse-pro`
- Headend: uvicorn `main:app` på 127.0.0.1:8000 (via `/Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist`), `DATABASE_URL=postgresql://timelapse@localhost/timelapse_db` sat i plist
- nginx: brew-launchagent `~/Library/LaunchAgents/homebrew.mxcl.nginx.plist` (kører som peter), config `/opt/homebrew/etc/nginx/nginx.conf`, lytter pt. på 80 + 443
- Primær edge: `TL-C87FF9587CA0` (hostname timelapse0101, Ubuntu 24.04.4, app 2.8.0, environment=lab, LAN 192.168.86.134)
- Headend-device i CMDB: `TL-MACMINI-HEADEND-TEST-1`
- Backup-sti: `/Volumes/data/backup/edge-backups/<device_id>/`
- Kameraer: Canon EOS 1300D + Nikon Z30 (skiftevis)
