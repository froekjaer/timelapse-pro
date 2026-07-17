# TimeLapse Pro — Headend Generator (script-baseret provisioning, v1)

**Dato:** 2026-07-16 · **Forfatter:** Claude (Cowork), implementering færdiggjort af Codex · **Status:** Fase 0-3 implementeret og kontrakttestet. IKKE endnu afprøvet end-to-end på en ny fysisk Mac.
**Relation:** Udvider `INSTALLATION_GUIDE_HEADEND_v1.md` (2026-07-05) med (a) den nye `bootstrap_headend_macos.sh`-generator og (b) det manglende CMDB-/config-control-trin, som v1 §9 eksplicit lod stå åbent. Følger ADR-001 (platform/payload) — provisioning er en **platform**-egenskab.
**Portpolitik:** `deploy/PORTS.md`, `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4, `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`.

---

## 1. Formål & princip

Vi vil kunne rejse en ny headend (staging/prod, og fremtidige prod-servere pr. kunde) på en **kontrolleret, reproducerbar** måde — analogt til den eksisterende **edge-generator** (`build_edge_disk_image.py` + `bootstrap_cli.py` + node-agent), men **uden en .ISO**. I stedet: et script der

1. **henter det nødvendige fra GitHub** som en *signeret, immutabel release* (ikke en løbende `git pull`),
2. **installerer** headend-stakken coexistence-sikkert (rører aldrig CrushFTP's porte),
3. **bringer maskinen under konfigurationskontrol** via node-agent + den signerede update-flow, og
4. **registrerer den i CMDB**, så den er synlig, versioneret og driftbar på linje med edge-noderne.

Hvorfor script frem for ISO: en headend er en macOS-maskine med eksisterende tjenester (CrushFTP), ikke en bare-metal edge vi selv flasher. Vi skal *tilpasse os* værten, ikke overskrive den. Et script kan preflighte værten, respektere det der allerede kører, og efterlade fuld evidens — en ISO kan ikke.

**Vigtigt (politik):** Claude/Codex får ALDRIG adgang til staging/prod (`MILJOE_ARKITEKTUR...` §5). Generatoren skal derfor kunne køres af Peter **helt uden agent-hjælp i selve udførelsen** — udførligt nok til at stå alene, med faldgruber fanget på forhånd.

---

## 2. Livscyklus — fire faser (+ løbende drift)

```
 Fase 0  PREFLIGHT   → læs-only: er værten klar? er 8443 fri? rører vi CrushFTP? (evidens-JSON)
 Fase 1  STAGE       → hent SIGNERET GitHub-release (git tag + GPG-verify + commit-SHA), dry-run install
 Fase 2  APPLY       → installér headend (venv, DB, UI-build, nginx:8443, launchd), TLS via DNS-01
 Fase 3  ENROLL      → node-agent på maskinen → self-register i CMDB + under config-control
 ────────────────────────────────────────────────────────────────────────────────────────────────
 Løbende  CONTROL    → software kun via signeret update-flow; node-agent heartbeat/inventory → CMDB
```

Sammenlignet med edge-generatoren:

| Trin | Edge | Headend |
|---|---|---|
| Artefakt | Disk-image (Orange Pi) | Signeret GitHub-release (macOS-vært) |
| Bootstrap | `bootstrap_cli.py` + zero-touch enrollment | `bootstrap_headend_macos.sh` (preflight/stage) |
| Install | Image flashes + first boot | `install_headend.sh` |
| Enrollment | `enroll_device` → device-token, HMAC, CMDB | `enroll_headend_cmdb.sh` → headend-token, HMAC, CMDB |
| Config-control | Signeret policy-pull (config-hierarki) | Signeret update-flow + node-agent |
| Identitet | device-token/HMAC (senere mTLS, #52) | Samme model bør genbruges (platform) |

---

## 3. Hvad findes allerede (og virker)

- **`deploy/install/bootstrap_headend_macos.sh`** — Fase 0+1. Preflight: skriver evidens-JSON (`schema: dk.froekjaer.timelapse.headend-preflight.v1`), tjekker at `TL_BACKEND_PORT` (default 8443) er fri, og **nægter 21/22/80/443** (CrushFTP). Stage: `git init` + fetch af signeret tag + `git verify-tag` (GPG) + commit-SHA-match + `install_headend.sh --dry-run`. Rører aldrig pakker/OS/eksisterende tjenester.
- **`deploy/install/install_headend.sh`** — Fase 2. Idempotent: `/etc/timelapse/headend.env` med unikt `JWT_SECRET` + `TIMELAPSE_ENV`, venv + `headend/requirements.txt`, Postgres DB/bruger, `npm run build`, launchd-service, nginx **kun på `TL_BACKEND_PORT`** (aldrig 80/443).
- **`deploy/install/example-{staging,prod}.conf`** — Fase 2-konfiguration (TL_ENV, TL_DOMAIN_BACKEND, TL_BACKEND_PORT=8443, TL_DATA_DIR ≠ R&D's volumen).
- **`node-agent/` (universel agent, edge + headend)** — Fase 3 + løbende. Samler hardware-/software-inventory + security events og poster til headend → CMDB. Installeres via `node-agent/install/macos.sh` (launchd).
- **Signeret update-flow** (change tickets, GPG-verificerede artifacts, rollback) — løbende CONTROL.
- **CMDB** (`headend/cmdb.py`): `POST /api/inventory/{device_id}` → `report_inventory()` → `DeviceInventory` + SBOM.

---

## 4. Fase 3 — enrollment i CMDB + config-control

Node-agent-installeren kræver nu eksplicit `--device-id`, `--headend-url` og
`--api-token-file`; der findes ingen R&D-defaults. `enroll_headend_cmdb.sh` kalder
zero-touch enrollment med `node_type=headend`, installerer agenten og fejler, hvis
der ikke kommer en ny autentificeret inventory-kvittering inden 60 sekunder.

For en staging/prod-headend skal disse være maskinens egne værdier, fx:
- `HEADEND_URL=https://127.0.0.1:8443` (agenten poster til sin EGEN headend lokalt) eller backend-domænet.
- `DEVICE_ID=TL-HEADEND-STAGING-1` / `TL-HEADEND-PROD-1` (stabil, miljø-navngiven identitet).

Dertil mangler tre ting for at Fase 3 er en rigtig, kontrolleret enrollment (ikke bare "agent kører"):

1. **Parametrisering:** implementeret uden miljø-defaults.
2. **Autentificeret self-registration:** inventory kræver Bearer-token og HMAC-signatur med nonce/replaykontrol. Credential registreres som `headend`, ikke `edge`.
3. **Verifikation:** enroll-scriptet accepterer kun en ny succeslinje efter agentstart. Endelig fysisk accept skal desuden kontrollere CMDB, softwareinventar og SBOM i UI.

Se §7 for en reference-skitse af det parametriserede enroll-trin (spec — Codex ejer implementeringen i node-agent/provisioning-sporet).

---

## 5. Portmodel — flyt VORES porte væk fra CrushFTP

Peters direktiv: CrushFTP kører allerede på staging/prod — **flyt TimeLapse's porte væk fra den, rør den ikke.** Det er den valgte retning (ikke PORTS.md's alternative "fælles reverse proxy der ejer 80/443", som ville kræve at flytte CrushFTP).

| Port | Ejer | TimeLapse-brug |
|---|---|---|
| 21, 22, 80, 443 | **CrushFTP** (+ system-SSH på 22) | **Aldrig TimeLapse** — bootstrap afviser dem hårdt |
| **8443** | TimeLapse | nginx (TLS, DNS-01-cert), kundevendt UI/API |
| **22222** | TimeLapse | SFTP-upload fra edge (chroot, `sftp_*`-brugere) |
| 8000 | TimeLapse (loopback) | FastAPI bag nginx |
| 8080 | TimeLapse (loopback/internt) | Open WebUI — kun bag MFA/reverse-proxy |
| 5514 | TimeLapse (internt/lab) | Valgfri syslog-receiver (foretræk 5514 frem for privilegeret 514) |

TLS-cert via **DNS-01** (`certbot-dns-cloudflare`) — rører ingen port, netop fordi CrushFTP ejer 80. Marketingsite hostes **et andet sted** (ingen backend-afhængighed). Login-knapper peger på `https://<backend-domæne>:8443/` (med portnummer). Cloudflare "orange cloud"-proxy foran 8443 er valgfri.

**Fremtidssikring (fra PORTS.md):** hvis en kunde senere kræver kundevendt HTTPS på standard 443 (uden portnummer), er de rene mønstre: (a) egen public IP til TimeLapse, eller (b) én fælles reverse proxy der router 80/443 på hostname/SNI (`ftp.kunde.net` → CrushFTP, `timelapse.kunde.net` → 8443). Begge kræver en bevidst beslutning + egen ADR; default nu er 8443 direkte.

---

## 6. Sikkerhed & standarder

- **IEC 62443 (secure provisioning):** signeret, immutabel release + GPG-verify + commit-SHA-pinning = leverandør-til-vært-integritet. Preflight = ingen ukontrollerede ændringer af værten.
- **CRA:** SBOM pr. node (node-agent rapporterer software-inventory → CMDB), signerede opdateringer, rollback.
- **Agent-lockout (M-05/R19):** generatoren køres af Peter; ingen AI-credential må nå staging/prod. `TIMELAPSE_ENV=staging|prod` aktiverer default-deny for `role="agent"` og fail-fast på manglende `ALLOWED_ORIGIN` (Codex' CORS-guard).
- **Least privilege:** node-agent kører som almindelig bruger (ikke root) hvor muligt (jf. Codex' `test_node_agent_privilege_contract.py` — igangværende). CMDB-inventory-endpointet skal være auth-beskyttet.
- **Config-control:** efter Fase 2 må software KUN ændres via den signerede update-flow — aldrig `git pull`/manuel kopi på en prod-headend.

---

## 7. Reference-skitse: parametriseret enroll-trin (SPEC — Codex ejer implementeringen)

Ikke et committet script (node-agent er Codex' aktive lane). Skitse til at lukke §4-hullet:

```bash
# deploy/install/enroll_headend_cmdb.sh
# Kør EFTER install_headend.sh, som del af Fase 3.
#   sudo ./enroll_headend_cmdb.sh --device-id TL-HEADEND-STAGING-1 \
#        --headend-url https://staging.timelapse-pro.dk:8443 \
#        --bootstrap-token-file /secure/bootstrap-token --repo-dir /path/to/signed/release
#
# 1) Parametrisér node-agent (i stedet for hardcoded R&D-værdier):
#      device_id  = <arg>            # stabil, miljø-navngiven
#      headend_url= <arg>            # maskinens egen backend (lokalt)
#      + agent-credential/HMAC hentet fra den kontrollerede install (ikke i Git)
# 2) Installér node-agent via node-agent/install/macos.sh (parametriseret)
# 3) Vent på første inventory-post; verificér i CMDB:
#      curl -sk https://127.0.0.1:8443/api/cmdb/ | grep TL-HEADEND-STAGING-1
# 4) Fail-closed: hvis registrering/verifikation fejler → exit non-zero + tydelig log
```

Krav til implementeringen (action items i §8): device_id/headend_url som argumenter, agent-auth mod CMDB-endpointet, verifikationstrin, fail-closed, og en launchd-plist der ikke er hardcoded til R&D.

---

## 8. Action items

**Implementeret af Codex:**
1. Parametriseret `node-agent/install/macos.sh` uden R&D-defaults. ✅
2. Bekræftet Bearer/HMAC/replay-beskyttelse og tilføjet eksplicit headend-credential. ✅
3. Implementeret fail-closed `deploy/install/enroll_headend_cmdb.sh`. ✅
4. Tynd UI-/CLI-orkestrator med bekræftelses-gates er fortsat næste forbedring; de fire faser kan allerede køres separat og kontrolleret.

**Peter (beslutninger):**
5. Bekræft device-ID-navngivning for staging/prod (`TL-HEADEND-STAGING-1` / `TL-HEADEND-PROD-1`?).
6. Bekræft at 8443-direkte er den ønskede prod-portmodel (vs. fremtidig fælles-reverse-proxy — §5).

**Claude (docs — kan tages nu):**
7. Skriv addendum til `INSTALLATION_GUIDE_HEADEND_v1.md` der integrerer bootstrap-generatoren + peger på Fase 3 (erstatter v1 §9's "node-agent ikke dækket"). ✅ (se separat commit).
8. Når Fase 3-koden er på plads: opdater denne v1 → v2 med testede kommandoer.

---

## 9. End-to-end (sådan ser det ud når hullet er lukket)

```bash
# Fase 0 — preflight (læs-only, evidens)
deploy/install/bootstrap_headend_macos.sh --mode preflight --config ~/timelapse-staging.conf

# Fase 1 — stage (hent signeret release fra GitHub, dry-run)
deploy/install/bootstrap_headend_macos.sh --mode stage --config ~/timelapse-staging.conf \
  --repo-url git@github.com:froekjaer/timelapse-pro.git \
  --release-tag v<X.Y.Z> --expected-commit <40-char-sha> --destination ~/tl-staging-release

# Fase 2 — apply (install; kør igen efter DNS-01-cert, jf. install-guiden §6)
sudo ~/tl-staging-release/deploy/install/install_headend.sh --config ~/timelapse-staging.conf

# Fase 3 — enroll i CMDB + config-control
sudo deploy/install/enroll_headend_cmdb.sh --device-id TL-HEADEND-STAGING-1 \
  --headend-url https://staging.timelapse-pro.dk:8443 \
  --bootstrap-token-file /secure/bootstrap-token --repo-dir ~/tl-staging-release

# Verificér: headend synlig i CMDB, health grøn
curl -sk https://<backend-domæne>:8443/api/health
curl -sk https://127.0.0.1:8443/api/cmdb/ | grep TL-HEADEND-STAGING-1
```

Herefter er maskinen under konfigurationskontrol: al software via signeret update-flow, løbende inventory/security → CMDB, og synlig på linje med edge-flåden.
