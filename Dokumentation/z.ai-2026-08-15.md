# z.ai — Samlet gennemgang: mission-framework + timelapse-pro (2026-08-15)

**Udført af:** z.ai (GLM-5.3), uafhængig session
**Omfang:** Fuld gennemlæsning af `froekjaer/mission-framework` + evaluering af `froekjaer/timelapse-pro`
(structure/dataflow, programmeringsfejl, cybersikkerhed, risikovurdering, acceptvurdering).
**Metode:** Klonede repos (shallow), gennemlæsning af kernedokumenter, målrettet kodereview af
headend/edge/UI/deploy/CI med tre parallelle gennemgange, efterfølgende **egen efterverifikation af alle
topfund direkte i koden** (fil:linje citeret og kontrolleret). Severity-klassifikation følger
mission-frameworks egen standard (`review-kit/severity-classification.md`: Critical/Major/Minor/Observation,
Impact 1–4 × Likelihood 1–4).

> **Vigtigt om kontekst:** Timelapse-pro-repoet er **offentligt tilgængeligt på GitHub** (verificeret).
> Dette påvirker alvorsgraden af alle fund, der eksponerer infrastruktur-/credential-detaljer.

---

## 0. Executive konklusion

**Er Timelapse Pro på vej mod en acceptabel tilstand? Ja — retningen og arkitektur­beslutningerne er
rigtige, men systemet er IKKE acceptabelt til Internet-eksponering endnu, og der findes fortsat
verificerede Critical/Major-fund, som hverken er lukket eller risk-accepted.**

Kort vurdering i forhold til projektets egen RC1-definition
(`TIMELAPSE_PRO_RELEASE_CONVERGENCE_PLAN_2026-08.md` §7):

| Dimension | Vurdering |
|---|---|
| Styrende baseline (WP-0) | **Stærk** — Locked Architecture Decisions + Convergence Plan er entydige og velmotiverede |
| Sikkerhedsarkitektur (mål) | **Stærk på papiret** — Trust Service, DMZ, EdgeServiceGrant, fail-closed principper |
| Sikkerhedsarkitektur (implementering) | **Ujævn** — nye trust-moduler er gode, men legacy-stier (private nøgler i DB, provision-package) er stadig aktive og bryder egne låste beslutninger #7/#12 |
| Kodekvalitet headend | **Moderat** — auth-kernen er veldesignet, men monolit (18.653 linjer, 234 endpoints) + verificerede auth-huller i perifere API'er |
| Kodekvalitet edge | **Moderat** — usædvanlig disciplineret subprocess-håndtering, men verificerede døde logik-stier (update-signatur, ping-URL, retry-cap) |
| Dokumentation/evidens | **Usædvanlig stærk** — men offentlig eksponering af interne detaljer er i sig selv en risiko |
| Konklusion | **"Approaching acceptable" — nej til go-live, ja til fortsat konvergens mod RC1** |

Efter mission-frameworks review-standard: **højeste udestående severity = Critical → anbefaling =
"Changes required"**. Systemet er acceptabelt som LAB/pre-production (hvad README selv angiver), men
ikke til fuld Internet-eksponering.

---

## Del A — Gennemlæsning af mission-framework

### A.1 Hvad er det, og hvor godt er det?

Mission-framework er et semantisk kerne-framework for Collaborative Intelligence-programmet: normative
definitioner (GLOSSARY.md som kanonisk kilde), Mission Loop (Reality → Need → Mission → … → Outcome →
Learning → Reality), evidence-model, trust-begreber ("Trust by Design", trust er purpose-relativ og
skal være *begrundet*, ikke antaget), engineering continuity + independent outcome verification, samt
en hel review-kit med severity-standard, evidensstandard, review-template og beslutningsstandard.

**Styrker (filreferencer):**

- **Severity-classification** (`review-kit/severity-classification.md`) er umiddelbart anvendelig og
  velafbalanceret: risikobaseret klassifikation (impact × likelihood-matrix), eksplicitte
  klassifikationsregler ("positive observations SHALL NOT offset blocking findings"), krav om
  rationale + evidence + confidence, samt opsigelses-/accept-regler. **Jeg har anvendt den i Del D.**
- **Eksplicit adskillelse af semantisk kerne vs. implementering** (`README.md`: "Implementations may
  extend, test or challenge the framework, but they should not silently redefine canonical meaning") og
  en defineret returkanal (`docs/FRAMEWORK_FINDINGS.md`).
- **Ærlig status:** Foundation v1.0 gør ikke krav på empirisk validering (`README.md` §"Foundation and
  review status"), og `review/KNOWN_LIMITATIONS.md`/`KNOWN_OPEN_QUESTIONS.md` findes.
- **Continuity + independent verification** (`docs/ENGINEERING_CONTINUITY_AND_INDEPENDENT_VERIFICATION.md`)
  er en sjældent ekspliceret disciplin ("detect absence as a first-class quality condition") som passer
  præcist til Timelapse Pros situation med AI-assisteret udvikling på tværs af Claude/Codex/z.ai-sessioner.

**Svagheder / egne fund i frameworket (Minor/Observation):**

1. **Minor — dublerede review-synteser:** `reviews/REVIEW-SYNTHESIS.md` OG `reviews/REVIEW_SYNTHESIS.md`
   eksisterer side om side (verificeret med `ls`). To næsten identiske filnavne med forskellig
   bindestregskonvention skaber tvivl om, hvilken der er autoritativ — i strid med frameworkets eget
   krav om entydig kilde.
2. **Minor — review-mappestrukturen er vokset organisk:** `review/` (ældre v0.2-materiale), `reviews/`
   (per-AI-mappe: chatgpt/claude/codex/mistral/z-ai + human) og `pilot-reviews/` med tre delvist
   overlappende invitation-/template-sæt. Frameworket prædiker "reduce unnecessary complexity" —
   review-infrastrukturen lever ikke helt op til det selv.
3. **Observation — mappen `reviews/zai/`** (uden bindestreg) afviger fra `reviews/z-ai/` (med bindestreg):
   `reviews/zai/MIAR-ORGANISATION-INTRODUCTION.md` ligger adskilt fra `reviews/z-ai/`. Samme
   navnekonventions-problem som punkt 1.
4. **Observation — frameworket er stadig assertion-tungt:** de centrale dokumenter (PRINCIPIA MISSIONIS,
  MISSION_THEORY, COMPUTATIONAL_TRUST_ENGINEERING) er velargumenteret men endnu ikke udfordret af
   referenceimplementeringer. Det erkendes selv (ROADMAP: "vertical slice via Mission Solar Eclipse first").
   Det bør forblive sådan — ingen anbefaling om mere teori før empiri.

**A.2 Anvendelse:** Timelapse-pro er kandidat-reference-mission ("Mission Timelapse" nævnes i README).
De dele af frameworket, der kan anvendes direkte på timelapse-pro i dag, er: severity-standarden,
evidence-kravene (fund skal være traceable til fil:linje — gjort i denne rapport), "trust by design"
-spørgsmålet ("er tilliden til X begrundet under de oplyste betingelser?") og
continuity/verification-disciplinen. Det er denne linse, rapporten anvender i Del D–F.

---

## Del B — Timelapse Pro: struktur og dataflow

### B.1 Faktisk dataflow (verificeret i kode)

```
[Billede]
Edge (_do_capture_cycle, agent.py) → gphoto2-driver → QA-check + .qa.json sidecar
  → lokal SQLite (utils/database.py, WAL) 
  → HeadendClient.upload_capture_files (multipart, signeret manifest, sha256, idempotens)
  → valgfri sekundær SFTP (upload/sftp.py, known_hosts-pinning i prod)

[Konfiguration/kommandoer — pull-model, ingen inbound]
Edge polling: config hvert 5. min (_pull_config) ← headend
Heartbeat + lab-kommandoer (_lab_tick) → clear via POST

[Lokal adgang på edge]
BT PAN (auto-pairing, bt-autoagent.py) → iptables TL_MGMT-kæde (8443 + DHCP/DNS)
  → TOTP-login (totp-service.py) → IP-whitelist i iptables → management-UI/WebSocket-shell

[Upload/update]
Headend → edge via reverse SSH-tunnel (edge/tunnel/ssh_manager.py)
Update-artifacts: sha256 + manifest verificeret — men se D-fund om signatur

[Headend]
FastAPI (main.py, 18.653 linjer, 234 endpoints) + PostgreSQL + nginx + React-UI
Nye moduler: trust/ (Trust Service), api/ (routers), services/ — router-fabrik-monster
```

### B.2 Strukturvurdering

**Styrker:**
- Klart målrettet adskillelse under opbygning: `headend/trust/` (provisioning, grants, policy, audit),
  `headend/api/*` router-fabrikker, `headend/services/*` — det er WP-2/WP-7-retningen, og den er rigtig.
- Edge er pænt lagdelt (hal/, camera/drivers/, capture/, upload/, tunnel/, diagnostics/) med HAL-abstraktion
  til flere boards (orangepi, rpi, jetson, generic).
- Tests: repo-niveau `tests/` (~100 filer) med governance-gates i koden
  (`test_architecture_ratchet.py` + `architecture_baseline.json`; `test_route_auth_coverage.py`) —
  ratchet-princippet (baseline må kun sænkes) er en stærk mekanisme mod yderligere forfald.

**Fund — struktur/gæld (Minor med mindre andet angives):**

| ID | Fund | Sted | Severity |
|---|---|---|---|
| S-01 | `main.py`-monolit: 18.653 linjer, 234 endpoints; nye endpoints lander fortsat der (mod ADR-001 og Locked Decision #16) | `headend/main.py` | Minor (kendt, P2-01/planlagt WP-7) |
| S-02 | Cirkulære afhængigheder: api-moduler laver lazy `from main import …` (capture_access_api.py:15, storage_api.py:16, redaction_api.py:52, customer_risk_api.py:21, siem.py:55-67, cmdb.py:105+, itim.py:796+) — main↔api-kredsen gør udtræk af auth-hjælpere nødvendigt før WP-7 kan fuldføres | `headend/api/*` | Minor |
| S-03 | `sprint_c/` er død kode: engangs-patch-scripts der muterer kildefiler + ældre kopi af `ssh_manager.py` (mangler `apply_config`). Intet importerer den. Bør slettes/arkiveres | `sprint_c/` | Minor |
| S-04 | `site_look_config_api.py` selv helt uden auth — reddes KUN af `dependencies=[require_role("super_admin")]` ved mount (main.py:17121); en kommentar indrømmer det ("formerly declared no authentication dependencies"). Skrøbelig kobling | `headend/api/site_look_config_api.py` | Minor |
| S-05 | Tekniker-sessioner i in-memory dict (`_pending_technician_sessions`, main.py:1727) — brydes ved multi-worker/restart; konflikt med production-uvicorn-konfiguration | `headend/main.py` | Minor |
| S-06 | ESLint-baseline accepterer 166 errors + 20 warnings (`.eslint-baseline.json`); ratchet-gate er god, men gælden er reel i live UI | `timelapse-ui/.eslint-baseline.json` | Minor (kendt VPEN-2026-004) |
| S-07 | Offentligt repo eksponerer ~92 interne runbooks med domæner, porte, serienumre, IP-range (192.168.86.0/24 i fail2ban-konfig), personnavne, personlige stier og dokumenterede åbne sårbarheder — en læsbar angrebsplan | `Dokumentation/` samlet | **Major** (se R-ZAI-10) |

### B.3 Dataflow-fund (programmeringsfejl, verificerede)

| ID | Fund | Sted | Severity |
|---|---|---|---|
| P-01 | `ping()` rammer `/api/api/health` — `_base_url` inkluderer allerede `/api`. Konsekvens: `api_ok` er altid False → API-loss-logik og `auto_on_api_loss` i tunnel-manager er **død kode** | `edge/upload/headend_client.py:582` vs. `edge/tunnel/ssh_manager.py:225-245` | **Major** (sikkerhedsfunktion virker ikke) |
| P-02 | `upload_attempts` inkrementeres aldrig → MAX_UPLOAD_ATTEMPTS-cap er død logik; permanent fejlende SFTP-upload genprøves uendeligt uden backoff | `edge/upload/sftp.py:166`, `edge/utils/database.py:61` | Major (drift) / Minor (kode) |
| P-03 | SSH-tunnel: stderr-pipe drænes aldrig ved langvarig proces → >64 KB stderr blokerer ssh-proces; tunnel går i stå men ses som "levende". FD-læk pr. reconnect. Korrekt mønster findes i `live_video.py:170-177` | `edge/tunnel/ssh_manager.py:330-339` | Major (driftssikkerhed) |
| P-04 | ServicePlatform: cross-process read-modify-write af delt JSON-tilstand uden fillås (kun atomisk rename) — agent + totp-service + service_operations kan erhverve samme lease/overskrive hinanden | `edge/service_platform.py:357-379, 480-483` | Minor |
| P-05 | SIEM journal-forwarding: `-n max_events` returnerer kun de nyeste N; cursor rykkes frem → ældre ulæste events **tabes** ved høj logaktivitet | `edge/agent.py:584-619` | Minor |
| P-06 | LAB-tilstand: `_lab_tick` sender aldrig heartbeat/sync/SIEM → headend ser enheden som offline under lange LAB-sessioner; 1 s config-poll er ressource tungt | `edge/agent.py:2289-2754` | Minor |
| P-07 | Ny `requests.Session` pr. API-kald bygges og lukkes aldrig (FD-pres, især ved 1 s LAB-poll) | `edge/upload/headend_client.py:127-129` | Minor |
| P-08 | node-agent: `security_interval=60` men `security_lookback=120` og ingen cursor → alle SSH/sudo-events rapporteres **dobbelt**; ingen store-and-forward (events droppes ved netværksfejl) | `node-agent/config.py:20,26`, `node-agent/collectors/security.py:348-371` | Minor |
| S-08 | POST med i Retry-policy (`allowed_methods=["GET","POST"]`) — clear-kommandoer/events kan eksekveres dobbelt; delvist kompenseres af headend-dedup, men ikke idempotent per design | `edge/upload/headend_client.py:38-44` | Minor |
| P-09 | `redaction_api.py`: `new_status = "redacted" if auto_approve else "redacted"` (parameter uden effekt); `approve_capture` skriver intet ("I mere avanceret version…"-kommentar) — falsk godkendelsesspor; manuel redaktion tilskrives `redacted_by="auto"` i GDPR-sporet | `headend/redaction_api.py:337, 341, 355-382` | **Major** (GDPR-evidens) |
| P-10 | Tidssynkronisering: ukritisk `date -s` fra headend-tid + manuel `timedatectl` fra teknikker; store spring kan give missede capture-slots (slot-claim beskytter mod dubletter, ikke mod glippede) | `edge/agent.py:2144-2172` | Minor |
| P-11 | SFTP-docstring lover "SHA-256 verified post-upload" — der verificeres intet efter `sftp.put`; ukendt upload-target mappes stiltiende til `uploaded_secondary` | `edge/upload/sftp.py:20-21,199`; `edge/utils/database.py:424-433` | Minor (doc/impl-mismatch) |
| P-12 | `lab pending_params` ryddes selv når `set_config` fejler — headend ved aldrig at parameteren ikke blev anvendt | `edge/agent.py:2464-2473` | Minor |
| P-13 | `TechnicianAuth.confirm_session` har ingen produktionskaldere (kun tests) — QR-flowets headend-callback eksisterer ikke; hvis genaktiveret skal callback være headend-signeret (challenge i QR-URL beviser intet alene) | `edge/technician_auth.py` | Minor |
| P-14 | Root-rod: `TimeLapse_SourceCode_Inventory*.md` ×3 versioner i rod, `PRIORITIZED_BACKLOG.md.bak`, forældet `ISSUES.md` (00_START_HER selv markerer den) | repo-rod | Observation |

---

## Del C — Verificerede sikkerhedsfund (headend, edge, UI/deploy)

Alle fund nedenfor er **efterverificerede direkte i koden af denne session** (ikke kun agent-rapporteret).
Severity efter mission-frameworks matrix.

### C.1 CRITICAL / MAJOR — auth- og adgangskontrol

**SEC-ZAI-01 [CRITICAL] — Path traversal i LAB preview-endpoints.**
`headend/main.py:16070-16091`: `filename` interpoleres uindskrænket i stien
(`path = _sftp_base_path() / "_lab" / device_id / filename`). Ingen `_sanitize_filename()`/`basename()`
— i modsætning til `get_image` (main.py:11992-12000), der gør det rigtige. Percent-dekodet `../` (eller
absolut sti efter `Path /`-semantik) lader en **viewer** læse vilkårlige filer på headend
(JWT_SECRET fra headend.env, DB-credentials, billeder på tværs af kunder). Verificeret.
Impact 4 × Likelihood 3 (kræver kun en gyldig viewer-session) = **Critical**.

**SEC-ZAI-02 [CRITICAL] — Redaction-API uden tenant-/rolletjek (IDOR + originalfil-overskrivning).**
`headend/redaction_api.py` — alle 5 endpoints (`analyze:185-190`, `redact:275-282`, `approve:355-359`,
`status:385-389`, `pending:411-415`) kræver kun `get_required_user`; docstrings hævder "operator eller
derover", men koden tjekker det aldrig — heller ikke `customer_id`. `redact_capture` overskriver
**originalfilen** (`cv2.imwrite`, linje 334), og originalen efterlades som `.original.jpg` ved siden af
(implementeringsdetalje der svækker GDPR-sletning, linje 330-331). Enhver autentificeret bruger
(viewer) kan på tværs af kunder analysere, overskrive og liste captures (`get_pending` lister alle).
Verificeret. I direkte modstrid med main.py's ellers omhyggelige `_capture_tenant_clause`-isolation.
Impact 3-4 × Likelihood 3 = **Critical** (GDPR + integritet + fortrolighed).

**SEC-ZAI-03 [MAJOR→Critical betinget] — Reflected XSS i teknikker-loginflow.**
`headend/main.py:1949`: `{session.get('device_id', 'Ukendt')}` interpoleres i HTML uden escaping;
`device_id` kommer ukontrolleret fra det uautentificerede `/api/technician/auth/start`
(main.py:1741-1774; model-validering bevidst fravalgt linje 1758). En attacker opretter session med
`device_id=<script>…>` og lokker teknikeren til `/technician/auth/{session_id}`. XSS i selve
sikkerhedsflowet for felt-support. Impact 3 × Likelihood 2-3 = **Major**.

**SEC-ZAI-04 [MAJOR] — `assign-site` uden rolle- og tenant-tjek.**
`headend/main.py:2482-2530`: `current_user=Depends(get_current_user)` — ingen `require_role`;
`Site`-opslag uden `_ensure_customer_access`. En viewer hos kunde A kan tildele en enhed til kunde B's
site (flytter `device.customer_id`). Verificeret. Impact 3 × Likelihood 2 = **Major**.

**SEC-ZAI-05 [MAJOR] — Private SSH-nøgler hentbare på tværs af lejere + lagret i klartekst.**
`headend/main.py:5139-5159`: `GET /api/admin/cameras/{camera_id}/ssh-key` — `require_role("super_admin","admin")`
med tenant-scopedede admins, intet customer-tjek; returnerer `ssh_private_key` som PlainText.
Bryder Locked Decision #7 ("`devices.ssh_private_key` er legacy og skal pensioneres"). Samme bypass-mønster
i `get_camera_bt_totp_qr` (main.py:5288-5293). Impact 3 × Likelihood 2 = **Major**.

**SEC-ZAI-06 [MAJOR] — Trust-API: hardcoded MFA-påstand + manglende edge-tenant-binding.**
`headend/api/trust_service_api.py:39-60`: `principal_from_legacy_user(user, mfa_verified=True)` — grantens
audit vidner MFA uanset faktisk sessionstilstand (linje 45); `edge_id` valideres ikke mod principalens
tenant (policy-tjekket sammenligner kun principal vs. request-tenant, ikke edge'ens ejer). Desuden er
`token_once`-navnet misvisende — genbrug tilladt med nye challenge-id'er (`trust/grants.py:170-172`).
Impact 3 × Likelihood 2 = **Major**. (Samme `mfa_verified=True`-mønster i `trust/technician.py:17`.)

**SEC-ZAI-07 [MAJOR] — `GET /api/admin/settings` lækker hemmeligheder i klartekst.**
`headend/main.py:16876-16880`: returnerer hele settings-tabellen umaskeret — inkl. `email.password` og
`sms.api_token`, som `/api/admin/notifications` (main.py:16825-16826) ellers omhyggeligt maskerer.
Verificeret. Impact 3 × Likelihood 3 (kun admin — men admin-token i localStorage via SEC-ZAI-12 gør det reelt) = **Major**.

**SEC-ZAI-08 [MAJOR] — Trust-grants: svag signerings-default og nøglegenbrug.**
`headend/trust/grants.py:25-27`: fallback `"timelapse-dev-trust-service-secret-change-me"`; default
signeres grants med **samme nøgle som session-JWTs** (ingen key separation), uden prod-vrågen (sml.
JWT_SECRET-tvangen main.py:86-90). Desuden valideres kun `sorted(request.capabilities)[0]` mod politikken
(grants.py:64) — resten smugles forbi policy. Impact 3 × Likelihood 2 = **Major**.

**SEC-ZAI-09 [MAJOR] — Sessioner kan ikke tilbagekaldes; absolut levetid håndhæves ikke.**
Logout sletter kun cookien (main.py:1695-1702); stateless JWT gyldig op til 30 dage; password-skift
invaliderer ikke tokens (main.py:1704-1720); `/api/auth/me` fornyer rullende **uden** at håndhæve
`absolute_max_days: 90` (main.py:1990-2005 vs. policy 862). Stjålet cookie kan holdes i live på ubestemt
tid. Impact 2-3 × Likelihood 2 = **Major**.

### C.2 MAJOR — edge

**SEC-ZAI-10 [MAJOR] — Update-artifact-signatur verificeres aldrig kryptografisk.**
`edge/security.py:142-143`: `if not artifact.get("signature"): return False` — tjekker kun at feltet er
ikke-tomt. `signer_fingerprint` er data i selve payload og matches blot mod lokal liste. Manifest- og
fil-sha256 verificeres, men en kompromitteret headend kan forge "signerede" artifacts med vilkårlig
fingerprint-streng. Koden indrømmer det selv ("does not yet perform OpenPGP verification"). Bryder
efterfølgelig hele kæden i R06 (ondsindet opdatering) — den reelle tillid er i dag transport-trust
(TLS+JWT), ikke artefakt-trust. Impact 3 × Likelihood 2 = **Major** (opgraderes mod Critical ved
Internet-eksponering).

**SEC-ZAI-11 [MAJOR] — Bluetooth-pairing auto-accepterer alt.**
`edge/scripts/bt-autoagent.py:29-60`: `RequestConfirmation→CONFIRM`, `RequestPinCode→"0000"`,
`AuthorizeService→ACCEPT alle`. Enhver BT-enhed i rækkevidde kan forbinde NAP'et; Just Works er
MITM-sårbar. Hele lokal sikkerhed hviler derefter på TOTP + iptables. Impact 3 × Likelihood 2
(fysisk nærhed krævet) = **Major**.

**SEC-ZAI-12 [MAJOR] — LAB SFTP-fallback deaktiverer host-key-verifikation.**
`edge/agent.py:2902-2903`: `AutoAddPolicy()` — i modstrid med `upload/sftp.py:346-364`, som er korrekt.
MITM kan opsnappe SFTP-credentials og billeder. Impact 2-3 × Likelihood 2 = **Major** (LAB-only bag
env-flag, men flaget er globalt).

**SEC-ZAI-13 [MAJOR] — e2e_test.sh: committet standard-credentials + deaktiveret verifikation.**
`e2e_test.sh:7-19`: `orangepi/orangepi` hardcoded, `StrictHostKeyChecking=no`, sudo-password via
kommandolinje (synlig i `ps`), `curl -sk` (TLS-verifikation slået fra) mod
`https://timelapse-api.froekjaer.dk:10443/api` med reelt token. **Offentligt repo.** Impact 3 ×
Likelihood 3 = **Major** (trojanske detaljer: port 2201, prod-URL).

**SEC-ZAI-14 [MAJOR] — iptables-whitelist lækker ved gentagne TOTP-logins.**
`edge/scripts/totp-service.py:322-331, 306-318`: hver login indsætter `-I TL_MGMT 1 -s <ip> -j ACCEPT`;
oprydning kun ved genbrug af samme token; ingen dedup/tidsbegrænsning. Klient-IP forbliver whitelisted
(fuld adgang inkl. SSH-port) ud over sessionstid, potentielt til reboot. Impact 2-3 × Likelihood 3 = **Major**.

**SEC-ZAI-15 [MAJOR] — Provision-package genererer stadig private nøgler på headend.**
`headend/main.py:10952-11002`: `/api/admin/provision-package` genererer tunnel+SFTP Ed25519-nøgler og
zippers ukrypteret ud — bryder Locked Decision #3/#12 og `trust/provisioning.py:496`'s egen kontrakt
(`"must_not_create_new_operational_private_keys_on_headend": True`). Impact 2-3 × Likelihood 3
(aktiv sti) = **Major** (arkitekturkontrakt-brud).

### C.3 MELLEM (uddrag — komplet liste i agentsporene)

| ID | Fund | Sted |
|---|---|---|
| SEC-ZAI-16 | Bootstrap-tokens i klartekst i DB + returneres rå via API (modsat secret_hash-mønsteret i edge_lifecycle) | `database.py:899`, `main.py:10914-10928` |
| SEC-ZAI-17 | SSH host-key-trust er display-only: DB-fingerprint pins ikke `client.connect` — reelt grundlag er brugerens known_hosts (TOCTOU) | `api/ssh_tunnel_terminal_api.py:236-259` |
| SEC-ZAI-18 | Race ved forbrug af bootstrap-token/challenge-replay (check-then-act uden lås) | `trust/provisioning.py:215-217`, `trust/grants.py:170-174` |
| SEC-ZAI-19 | CSR-enhedsbinding via substring-match: kort device-id matcher fremmede SAN-navne (`tl123456` ⊆ `tl123456.attacker.com`) | `trust/provisioning.py:342-344` |
| SEC-ZAI-20 | `totp.enabled=false` slår hele auth fra på edge-portal (fail-open); bør kræve secret != "" | `totp-service.py:505-506, 537-538` |
| SEC-ZAI-21 | HMAC-signatur bruger Bearer-token som nøgle (signaturnøgle = credential; headend kan forge edge-signaturer) | `edge/security.py:40`, `node-agent/transport.py:35` |
| SEC-ZAI-22 | Legacy git-update-sti: `git pull origin main` + restart uden signaturverifikation; global env-toggle | `edge/agent.py:1563-1624` |
| SEC-ZAI-23 | Edge-backup-arkiv med SFTP-password lægger i /tmp world-readable, uden oprydning | `edge/agent.py:1293-1311` |
| SEC-ZAI-24 | SSH-tunnel TOFU (`accept-new`) i stedet for provisioneret host-key | `edge/tunnel/ssh_manager.py:313` |
| SEC-ZAI-25 | Backup default **ukrypteret** (`ENCRYPT_BACKUP=false`) på trods af indhold af JWT_SECRET + admin-password; nøgle via `-k` på kommandolinje | `deploy/scripts/backup.sh:30-31, 302-307` |
| SEC-ZAI-26 | Restore udpakker persondata-DB + env til world-readable /tmp; `PGPASSWORD` på kommandolinje | `deploy/scripts/restore.sh:29, 277` |
| SEC-ZAI-27 | fail2ban-jail er illusorisk: `iptables-multiport` findes ikke på macOS (PF), og logpath peger på en anden fil end nginx skriver | `deploy/fail2ban-timelapse-pro.conf:21-46` vs. nginx-conf |
| SEC-ZAI-28 | CI: actions ikke SHA-pinned; **ingen** dependency-/sårbarhedsscanning (npm audit/pip-audit/CodeQL); prod-deploy bruger `npm install` (ikke reproducerbar), self-hosted runner med sudo launchctl | `.github/workflows/ci.yml:17-19, 66-68, 144-150` |
| SEC-ZAI-29 | UI: `bootstrapToken` lagrer admin-API-token i XSS-læsbar localStorage (httpOnly-cookie omgås); manglende `credentials:'include'` + rå deviceId-interpolation på SSH-tunnel-sider | `timelapse-ui/src/api/client.ts:29-38`, `SshTunnelPage.tsx:14-21, 98` |
| SEC-ZAI-30 | `.env.local` er tracked i git (indhold i dag harmløst — verificeret i historik — men fælde: `.gitignore` dækker kun `.env`) | `timelapse-ui/.env.local`, `.gitignore` |
| SEC-ZAI-31 | Nginx: `unsafe-inline` i style-src, ingen cipher-restriktion/OCSP/server_tokens; `/api/import/` tillader 1 GB upload | `deploy/nginx/timelapse.froekjaer.dk.conf:64, 117-120, 151` |
| SEC-ZAI-32 | `fix_schema.sh` undertrykker migreringsfejl (`|| true`) — kan maskere delvist anvendte migreringer | `fix_schema.sh:9-13` |
| SEC-ZAI-33 | "auditor"-rollen findes ikke i rollehierarkiet — død rollelogik i capture_access_api | `api/capture_access_api.py:42` vs. `main.py:1103-1108` |

---

## Del D — Risikovurdering (nye risici, koblet til eksisterende register)

Nedenstående nye risici foreslås tilføjet GRC-registret / næste version af RISK_ASSESSMENT.
Eksisterende register (R01-R21, VPEN-2026-*) er gennemlæst; fundene her er **nytillagte eller
eskaleringer**.

| ID | Risiko | Impact | Likelihood | Severity | Kobling |
|---|---|---|---|---|---|
| **R-ZAI-01** | Vilkårlig fillæsning på headend via LAB preview (SEC-ZAI-01) | 4 | 3 | **Critical** | Ny; relaterer til R02 |
| **R-ZAI-02** | Cross-tenant GDPR-krænkelse: viewer kan analysere/overskrive/liste alle kunders billeder (SEC-ZAI-02) | 4 | 3 | **Critical** | Ny; eskalerer R12/R16 |
| **R-ZAI-03** | Artifact-forging ved headend-kompromittering — signaturverifikation mangler (SEC-ZAI-10) | 3 | 2 | **Major** | Eskalerer R06 (kontrol mangler) |
| **R-ZAI-04** | Edge-lokal kompromittering via BT auto-pairing + lakkende iptables-whitelist (SEC-ZAI-11+14) | 3 | 2 | **Major** | Eskalerer R05/R10 |
| **R-ZAI-05** | Fortroligheds-læk via admin-API: settings i klartekst + token i localStorage (SEC-ZAI-07+29) | 3 | 3 | **Major** | Ny |
| **R-ZAI-06** | Falsk sikkerhedsevidens: MFA-påstande hårdkodede, redaction-approve no-op, "signeret" uden verifikation (SEC-ZAI-06, P-09, SEC-ZAI-10) | 3 | 3 | **Major** | Ny klasse — rammer tilliden til selve evidenssystemet |
| **R-ZAI-07** | Backup-kompromittering: ukrypteret default, nøgle på kommandolinje, /tmp-udpakning (SEC-ZAI-25/26) | 3 | 2 | **Major** | Eskalerer R09 |
| **R-ZAI-08** | Bruteforce-beskyttelse illusorisk (fail2ban ikke-funktionel på macOS) (SEC-ZAI-27) | 2 | 4 | **Major** | Ny; underminerer kompenserende kontrol nævnt i R06/VPEN |
| **R-ZAI-09** | Supply-chain: ingen afhængighedsscanning, upinned actions, ikke-reproducerbar prod-deploy (SEC-ZAI-28) | 3 | 2 | **Major** | Ny |
| **R-ZAI-10** | OSINT-eksponering: offentligt repo afslører infrastruktur, credentials-mønstre, åbne sårbarheder (SEC-ZAI-13, S-07) | 2-3 | 4 | **Major** | Ny |
| R-ZAI-11 | Session-hijack med lang holdbarhed (SEC-ZAI-09) | 2 | 2 | Minor-Major | Udvider R02 |

**Samlet risikobillede:** De to Critical (R-ZAI-01/02) er begge **hurtige at rette** (hhv. to liniers
sanitering og genbrug af eksisterende tenant-tjek-hjælpere) — de blokerer go-live per
GO_LIVE_CHECKLIST-logikken, men ikke konvergensplanen. Risici i klassen R-ZAI-06 (falsk evidens) er
strategisk de vigtigste, fordi de underminerer systemets egen trust-model: et system hvis audit-spor
vidner MFA, der ikke er verificeret, og hvis "signaturer" ikke verificeres, opfylder ikke
"Trust by Design" (mission-framework) og ikke egne Locked Decisions #10/#15.

---

## Del E — Overensstemmelse med Locked Architecture Decisions & Convergence Plan

| Låst beslutning / WP | Status i kode | Vurdering |
|---|---|---|
| #6 `devices.api_token` skal ikke være creation path | `edge_credential_inventory` + secret_hash implementeret (edge_lifecycle.py:144-161) | **På sporet** |
| #7 Edge ejer SSH-nøgle; `devices.ssh_private_key` pensioneres | Nøgler stadig i klartekst i DB + aktivt download-endpoint (SEC-ZAI-05) | **Brud — aktiv legacy-sti** |
| #3 Trust Service ejer issuance | Modulgrænse etableret (`trust/`), men grants-signering deler JWT-nøgle + dev-fallback (SEC-ZAI-08) | **Delvis** |
| #10 EdgeServiceGrant: MFA-state aware | `mfa_verified=True` hardcodet (SEC-ZAI-06) | **Brud — kontraktens kerne** |
| #12 Ingen pre-baked/permanent private nøgler; envelope one-time | provision-package genererer nøgler på headend (SEC-ZAI-15); bootstrap-tokens klartekst (SEC-ZAI-16); envelope-race (SEC-ZAI-18) | **Delvis — WP-4 uafsluttet** |
| #14 Retain-until-explicit-disposition | capture_deletion_service med audit+rollback er god; men redaction `.original.jpg`-praksis + no-op approve (P-09) | **Delvis** |
| #16 Ingen nye endpoints i main.py | Nye endpoints lander fortsat i main.py (LAB preview, provision-package) | **Brud — ratchet hjælper, discipl mangler** |
| WP-2/WP-3 (policy gateway, grant) | Router-fabrikker + trust/-modul på plads; ad hoc-auth i perifere API'er (redaction, assign-site) | **I gang — hullerne er præcis WP-2's pointe** |
| WP-8 restore-drill / SIEM | node-agent duplikerer events (P-08), SIEM forwarding taber events (P-05), fail2ban død (SEC-ZAI-27) | **Ikke klar** |

**Fortolkning:** Konvergensplanens diagnose ("byggestenene findes, men spænder over flere
arkitekturgenerationer") er **korrekt og bekræftet af dette review**. De verificerede fund samler sig
netop om legacy-stierne, som WP-1/WP-2/WP-4 var designet til at pensionere. Planen er den rigtige medicin —
problemet er, at nogle af stierne stadig er *aktive standardstier*, ikke migreringsrester.

---

## Del F — Styrker (der bør bevares og fremhæves)

1. **Auth-kernen (headend):** bcrypt, JWT-tvang i prod med minimumslængde, HttpOnly/SameSite/Secure-cookies,
   rollehierarki med per-rolle-MFA i `require_role`, rate-limited login, M-05 agent-spærre.
2. **CORS fail-closed** i staging/prod (single origin).
3. **Capture-upload og artifact-download er mønstereksempler:** device-id-sanitering, filename-allowlist,
   streaming SHA-256 med `hmac.compare_digest`, atomisk `os.replace`, manifest-whitelist + root-confinement.
4. **Tenant-isolation på captures** (`_capture_tenant_clause`): fryser customer_id på optagelsestidspunkt —
   usædvanlig gennemtænkt, inkl. fail-closed for brugere uden kunde.
5. **Edge-subprocess-disciplin:** list-args overalt, timeouts, check=False med returkoder — ingen
   shell=True fundet i edge-kode; OS-update-runner med shlex.quote, offline-only bundle, forbidden-command-scanning.
6. **Capture-idempotens** via slot-claim i DB; Ed25519-signering med atomic O_EXCL/0600-nøgleskrivning;
   O_NOFOLLOW+fsync+readback på receipts.
7. **TOTP-portal:** ingen fabriks-hemmelighed ("unprovisioned" låser), brute-force lockout,
   httponly/secure/samesite=strict-cookie, CLI-flag-allowlist, shell fail-closed bag eksplicit flag,
   stistærk `_safe_image_from`.
8. **Deploy-hygiejne:** install-scripts genererer friske secrets (openssl rand), genbruger aldrig,
   chmod 640; bootstrap kræver GPG verify-tag + SHA-pinning; Restic-nøgle i Keychain.
9. **Governance-gates i koden** (architecture-ratchet + route-auth-sweep) — mekanismen bør udvides (se anbefaling 8).
10. **Dokumentationskultur:** usædvanligt ærlig og sporbar — men se R-ZAI-10 om offentlighed.

---

## Del G — Anbefalinger (rækkefølge efter risiko/indsats)

**Umiddelbart (dage, før ny kode):**
1. Saniter `filename` i de to LAB preview-endpoints (SEC-ZAI-01) — genbrug `_sanitize_filename`.
2. HTML-escape `device_id` + input-validering i technician-flowet (SEC-ZAI-03).
3. Tilføj tenant-/rolletjek i `redaction_api.py` via `_ensure_capture_device_access`/`_capture_tenant_clause` (SEC-ZAI-02).
4. `require_role("admin")` + `_ensure_customer_access` på assign-site, ssh-key, bt-totp (SEC-ZAI-04/05).
5. Fjern hardcodet `mfa_verified=True`; valider edge-tenant-binding i trust-API (SEC-ZAI-06).
6. Masker hemmeligheder i `GET /api/admin/settings`; fjern `bootstrapToken` fra client.ts (SEC-ZAI-07/29).
7. Rotér + fjern `orangepi`-credentials; omskriv e2e_test.sh til nøglebaseret SSH uden `-k` (SEC-ZAI-13).
8. Gør backup-kryptering default TIL med nøgle uden for proceslisten (SEC-ZAI-25).

**Kort sigt (uger — indpas i WP-1..WP-4):**
9. Kryptografisk signaturverifikation af update-artifacts på edge (SEC-ZAI-10) — den enkeltændring der
   størst løfter kædens reelle trust-model; kræver verifikation mod GPG/offentlig nøgle, ikke payload-felt.
10. Ret `ping()`-URL (P-01) og beslut om `auto_on_api_loss` skal leve; attempts-tæller/backoff på SFTP (P-02);
    stderr-dræntråd i tunnel-manager (P-03, genbrug live_video.py-mønsteret).
11. Dedup/tidsbegræns iptables-whitelist; fail-closed TOTP-enabled (SEC-ZAI-14/20); BT-agent-begrænsning (SEC-ZAI-11).
12. Ret fail2ban til PF + faktisk logpath, og **verificér at den bannere** (SEC-ZAI-27) — ellers stryg den
    som kompenserende kontrol i risikoregisteret.
13. Slet/arkivér `sprint_c/`, `ISSUES.md`, `.bak`, gamle inventory-filer (S-03, P-14).
14. Fjern provision-package-nøglegenerering (SEC-ZAI-15) eller flyt bag flag som WP-4-explicit.

**Mellem sigt (konvergensperiode):**
15. SHA-pin CI-actions + tilføj pip-audit/npm-audit/CodeQL; `npm ci` i deploy (SEC-ZAI-28).
16. Session-revocation (token-version pr. bruger eller denylist) + absolut levetid (SEC-ZAI-09).
17. Adskil trust-grant-signeringsnøgle fra JWT_SECRET + prod-vråning ved fallback; valider alle
    capabilities mod policy (SEC-ZAI-08).
18. Gør repoet privat **eller** flyt `Dokumentation/`-interne detaljer (domæner, porte, serienumre,
    åbne sårbarheder) ud af det offentlige repo (R-ZAI-10). Alternativ: public documentation-set separat
    fra driftsdetaljer.
19. Udvid route-auth-sweep til at dække *tenant*-tjek, ikke kun auth-tilstedeværelse (SEC-ZAI-02/04/05
    var alle "authentificeret men ikke autoriseret").
20. Overvej at bruge mission-frameworks Framework Findings-processen til at returnere erfaringen
    "ad hoc authorization i endpoints er den systematiske fejlkilde" — det er præcis en implementation→framework-observation.

---

## Del H — Samlet acceptvurdering

Anvendt mission-framework review-outcome-model ("højeste udestående severity → normal anbefaling"):

| Spørgsmål | Svar |
|---|---|
| Klar til fuld Internet-eksponering / production? | **Nej.** 2 verificerede Critical + ~14 Major udestående. |
| Klar til fortsat LAB/staging-drift med kendte risici? | **Ja, betinget** — Critical-fundene (R-ZAI-01/02) bør rettes straks alligevel; de er billige at lukke og findes i aktive stier. |
| Er konvergensplanen (WP-0..9) det rigtige næste skridt? | **Ja.** Reviewet bekræfter planens diagnose; fundene koncentrerer sig i de legacy-stier, WP-1/2/4 pensionerer. |
| Er arkitekturmålet (Trust Service, DMZ, grants) realistisk implementeret i kodebasen? | **Ja, delvist** — nye moduler er veldesignede; vigtigste gap er at egne låste kontrakter (#7, #10, #12, #16) brydes af aktive stier. |
| Mere review eller mere byg? | **Byg.** Planens "review phase is complete enough to build" står ved magt — med tilføjelsen at Critical-fundene hører under "unresolved implementation defects", som planen selv tillader review af. |
| Trust by Design (mission-framework-linsen)? | **Ikke endnu opfyldt**: audit-spor der vidner MFA uden verifikation og signaturer uden verifikation er trust-påstande uden belæg — præcis det frameworket kalder "authority by declaration". |

**Endelig karakter:** Timelapse Pro bevæger sig mærkbart mod acceptabel tilstand. Fundamentet
(arkitekturbeslutninger, auth-kerne, edge-disciplin, dokumentation) er over gennemsnittet for systemer i
denne klasse — men accept koster: Critical-fundene lukkes, falske evidens-spór rettes (MFA/signatur),
og de aktive legacy-stier (private nøgler i DB, provision-package) pensioneres som planlagt i WP-1..WP-4.

---

## Bilag — Metode og begrænsninger

- **Kilder:** klonede repos 2026-08-15 (shallow, depth 50 — ældre git-historik ikke gennemgået,
  men `.env.local`-historik spot-tjekket). Mission-framework: alle rod-dokumenter + docs/ + review-kit
  gennemlæst (3.719 linjer kerne + review-mapper). Timelapse-pro: alle styrings-/plan-/risikodokumenter
  (v10 + 2026-08-dokumenter), fuldt kodereview af headend (main.py i fuld længde, trust/, api/, services/),
  edge (agent, security, tunnel, upload, totp, bt, node-agent), UI/deploy/CI/website.
- **Verifikation:** Alle fund i Del C/D med "verificeret" er efterkontrolleret direkte i koden af
  hovedsessionen (sed-udsnit citeret og matchet). Agent-fund uden egen efterverifikation er markeret
  med kildehenvisning og bør behandles som Medium-confidence til de bekræftes.
- **Ikke omfattet:** dynamisk test/kørsel (ingen kode er eksekveret), git-historik-forensik,
  afhængigheds-CVE-matching, fysisk hardware, driftsmiljøet på Mac Mini/Orange Pi.
- **Confidence:** High for verificerede fund (direkte, reproducerbar kildecode-evidens); Medium for
  agent-rapporterede detaljer uden egen efterverifikation; usikkerhed er ikke brugt til at sænke severity.
- **Disclosure:** Rapporten er skrevet til repoets egen konvention (intern håndtering via
  HANDOVER_LOG-modellen), men pointer på, at repoet er offentligt — se R-ZAI-10.
