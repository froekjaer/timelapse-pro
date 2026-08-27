# Headend `main.py` — Modulariserings-status

**Dato:** 2026-08-26
**Forfatter:** Claude (Sonnet 5), på Peters anmodning
**Relateret:** Fuld plan i `/Users/peter/.claude/plans/twinkling-toasting-treehouse.md`
(kun tilgængelig i Claudes plan-lager, ikke i repoet — dette dokument er den
repo-forankrede status-optegnelse over samme arbejde)

## Hvorfor

`headend/main.py` var vokset til 18.661 linjer / 235 direkte routes —
**begge dele præcis på loftet** for arkitektur-ratchetten
(`tests/architecture_baseline.json` + `tests/test_architecture_ratchet.py`),
ingen buffer på nogen af dimensionerne. Enhver ny endpoint, tilføjet af en
hvilken som helst af de samtidigt arbejdende AI-sessioner i dette repo
(Claude/Codex/ChatGPT/Kimi/Gemini, jf. `CLAUDE.md`), ville øjeblikkeligt
sprænge route-loftet. Samtidig havde ~15 allerede-udtrukne router-moduler
akkumuleret **to konkurrerende, ad-hoc måder** at omgå den samme cirkulære
import-hindring (main.py↔modul) på — hverken ren eller konsistent.

Peter bad om en plan for at opdele `main.py` i mindre moduler med en ren
snitflade. Dette dokument er status efter første nats arbejde på den plan.

## Tal — før og efter

| | Linjer | Direkte routes |
|---|---:|---:|
| **Før** (start af arbejdet) | 18.661 | 235 |
| **Nu** | **17.049** | **219** |
| Ændring | −1.612 (−8,6 %) | −16 (−6,8 %) |

Ratchet-baseline (`tests/architecture_baseline.json`) er sænket i takt med
hver udtrækning — aldrig hævet, jf. repoets egen politik.

## Den arkitektoniske kerne-fix: `headend/auth.py`

Før: `main.py` importerer hvert router-modul ved indlæsning for at montere
det, så de modulerne kunne IKKE importere main.py's auth-hjælpere på
modul-scope uden cirkularitet. To workarounds havde bredt sig:

1. **Lazy import** — `from main import X` INDE I en funktionskrop, gentaget
   ordret (samme 5-navns-tupel: `_ROLE_HIERARCHY`, `_mfa_required_for_user`,
   `_session_is_mfa_verified`, `_session_payload`, `get_current_user`) på
   tværs af 8+ filer.
2. **Factory-funktioner** — `create_X_router(require_role, ...)`, afhængigheder
   sendt som eksplicitte argumenter ved montering i main.py.

`headend/auth.py` (419 linjer) er den egentlige fix: hele det
selvstændige session/token/MFA-politik/RBAC-kompleks
(`get_current_user`, `require_role`, `_ROLE_HIERARCHY`, cookie/JWT-
primitiver, session-politik-hierarki-resolver, M-05 agent-lockdown,
first-boot admin-bootstrap) flyttet ordret til ét modul, der **ikke
afhænger af main.py eller noget andet router-modul** — kun af
`database.py` og tredjeparts-libs. Både `main.py` og ethvert router-modul
kan nu skrive `from auth import require_role, get_current_user` direkte på
modul-scope, ligesom de allerede gør med `database.py`.

Alle 8 gamle lazy-import-filer (`cmdb.py`, `siem.py`, `local_access.py`,
`itim.py`, `technician_keys.py`, `commissioning_key.py`, `redaction_api.py`)
plus **flere flere end oprindeligt fundet** (`headend/api/*.py`-modulerne,
`ai/settings_api.py`) er retrofittet til at bruge `auth.py` direkte.

**Bevidst IKKE flyttet til `auth.py`** (separat "tenant scoping"-anliggende,
kandidat til en fremtidig fast-follow): `_is_platform_admin`,
`_visible_device_query`, `_visible_camera_query`, `_verify_device_token`,
`_ensure_capture_device_access`.

## Nye/udvidede moduler denne nat

| Modul | Linjer | Domæne |
|---|---:|---|
| `headend/auth.py` | 419 | Session/RBAC/MFA-kerne (se ovenfor) |
| `headend/dict_merge.py` | 31 | Delt `_deep_merge`-hjælper (auth.py + main.py) |
| `headend/api/edge_disk_image_api.py` | 808 | Edge disk-image build + WiFi-injektion (7 routes + 1 allerede-lokal DELETE) |
| `headend/api/ai_batch_api.py` | 474 | Gemini Batch API — bulk AI-genanalyse (2 routes + baggrundstråd) |
| `headend/api/admin_settings_api.py` | 219 | Password-politik + notifikationer + generisk settings CRUD (7 routes) |

Alle fem er **nye filer** skrevet denne nat. Ingen eksisterende moduler blev
omskrevet — kun main.py's import-linjer og de 8 lazy-import-filers
top-of-file imports blev rettet.

## Etablerede mønstre (til fremtidige udtrækninger)

1. **Auth**: `from auth import require_role, get_current_user, ...` på
   modul-scope. Ingen lazy import, ingen factory-argument-threading —
   begge ældre mønstre er nu overflødige for nye udtrækninger.
2. **Main.py-brede, ikke-auth hjælpefunktioner** (fx `_get_setting`,
   `_repo_root`, `_headend_api_url`, `_git_text` — bruges 10-40+ steder
   spredt i main.py, ikke domænespecifikke): fortsat lazy-importeret pr.
   funktion i det nye modul. Samme idiom som `importer.py` og
   `headend_generator_api.py` allerede brugte.
3. **Baggrundstråde**: domænemodulet ejer sin egen `start_X_background_
   loop()`-funktion (selve `threading.Thread(...)`-opstarten bor der);
   main.py's `startup()` kalder den ÉN gang, i PRÆCIS samme
   try/except-blok og position som den gamle inline tråd-opstart sad i.
   Mønsteret var allerede bevist af `itim.py`s `start_itim_collector()`
   — nu generaliseret og fulgt eksplicit i `ai_batch_api.py`.
4. **Ratchet-disciplin**: `tests/architecture_baseline.json` sænkes i
   SAMME commit som udtrækningen, beregnet mod en frisk `git fetch
   origin main` (ikke en potentielt forældet lokal branch — relevant når
   flere sessioner arbejder parallelt).
5. **Verifikation, hver PR**: fuldt CI-batteri lokalt →
   `test_route_auth_coverage.py` + `test_architecture_ratchet.py`
   eksplicit → efter deploy, `curl` mod MINDST ét flyttet endpoint (ikke
   kun `/api/health`) for at fange en glemt `include_router(...)`-linje,
   som er HELT STILLE ellers (routen forsvinder bare, testen ser den
   aldrig, fordi den kun tjekker det der faktisk er monteret).

## Hvad står stadig i `main.py` — grov oversigt

Ikke udtømmende, men de største grupper (route-antal er `@app.*`-tællinger,
linjetal er groft):

| Domæne | Routes | Note |
|---|---:|---|
| **Updates/artifacts/releases** | 26 | Størst. Egne baggrundstråde (git-tag poller, os-bundle poller, headend-self-update). Planlagt SIDST, splittet i 2 PR'er — det er selve headendens self-update-maskine. |
| **Lab/WebRTC device-tuning** | 30 | Flest routes af noget domæne. Real-time signalering, per-device `asyncio.Lock`-dict populeret ved runtime. |
| **Device CRUD (`/api/admin/devices/*`)** | 17 | Tæt koblet til CMDB/tenant-scoping. |
| **Auth/session/MFA/WebAuthn (routes selv)** | 15 | De 235 routes der BRUGER `auth.py`'s kerne — ikke flyttet, kun deres afhængigheder er det. |
| **OpenWebUI-integration** | 10 | Selvstændig, egen baggrundstråd. God kandidat. |
| **Backup** | 9 | Egne baggrundstråde + status-dicts. |
| **Cameras (`/api/admin/cameras/*`)** | 8 | God, adskilt kandidat — IKKE samme som `local_access.py` (BT-TOTP-resolution). |
| **Key management/PKI** | 6 | Sikkerhedskritisk — tjek overlap med allerede-udtrukne `trust_service_api.py`/`edge_local_pki_api.py` først. |
| **Users/RBAC (CRUD)** | 6 | |
| **Customers / Sites** | 5 + 5 | Naturlig kandidat til at flytte ind i `cmdb.py` (samme konceptuelle domæne). |
| **Retention** | 5 | Del af samme cluster som Backup + `_resolve_config_hierarchy`. |
| **Timelapse-rendering** | 5 | 2 af dens routes er blandt de 8 hardkodede high-risk-stier i `test_high_risk_admin_surfaces_use_role_authentication` — pas på ved udtrækning. |
| **Captures (`/api/captures/*` + `/api/admin/captures/*`)** | 10 | Delvist koblet til post-processing/thumbnail-maskineri. |
| **AI ops/QA/natural-search** | 5 | Spredt over 4 forskellige steder i filen — IKKE én sammenhængende klynge (modsat ai-batch, som var det). |
| **Change tickets** | 4 | Refererer Pending Updates — bør flyttes SAMMEN med Updates-domænet, ikke isoleret. |
| **Compliance/GRC (`/api/compliance/*`, `/api/grc/dashboard`)** | 4 | **Undersøgt og bevidst UDSAT** — se nedenfor. |
| **Node/multi-camera** | 3 | Lille, kandidat til at folde ind i Cameras-modulet. |
| **SSH-tunnel (inline, reverse-tunnel status)** | 4 | **Bekræftet IKKE dødt kode** — anden funktion end den allerede-udtrukne `ssh_tunnel_terminal_api.py` (browser-terminal/WebSocket). Reverse-tunnel-livscyklus-sporing, stadig aktivt brugt. |
| Diverse mindre (config-resolution, device-enrollment/bootstrap, edge-telemetri, site-look) | ~15-20 | Se "Vigtige opdagelser" nedenfor. |

## Vigtige opdagelser undervejs (ændrer den oprindelige plans rækkefølge)

Tre domæner, oprindeligt vurderet som lette/isolerede ud fra deres
sti-præfiks alene, viste sig ved faktisk kodelæsning at være markant
dybere koblet end antaget:

- **`/api/compliance/cockpit`** kalder DIREKTE ind i key-management-,
  resilience/backup- og AIOps-domænerne som almindelige Python-funktions-
  kald (ikke HTTP) — en ægte "roll-up"-endpoint der læser næsten alt andet.
  Kan først udtrækkes sikkert EFTER de domæner den læser fra selv er
  udtrukket og har stabile grænseflader.
- **`/api/admin/edge-provisioning/prepare`** og **`/api/bootstrap`/`/api/
  devices/enroll`** er tæt koblet til `KeyCredential`-udstedelse og
  `_reconcile_edge_lifecycle` — hører reelt til Key management/PKI-domænet,
  ikke til en isoleret "device enrollment"-boks.
- **`/api/admin/config-defaults`/`config-resolution`** er dybt koblet til
  `_resolve_config_hierarchy`/`_merge_missing_defaults`/
  `_FACTORY_CONFIG_DEFAULTS` — samme store, delte maskine som
  Backup/Retention, ikke en lille selvstændig "settings"-side (selvom den
  oprindeligt lå i samme mentale bucket som password-policy/notifications).

Disse tre er derfor UDSAT til senere i planen, efter de domæner de
afhænger af er ryddet op — ikke sprunget over, men bevidst sekventeret om.

## Verifikation — hvordan hver ændring blev bekræftet

Ikke kun enhedstests. For hver af de 4 PR'er i nat:
1. `main.py` importeret end-to-end lokalt (`import main; len(main.app.routes)`)
2. Fuldt CI-batteri (1144 passed, 4 skip, 4 kendte urelaterede pre-eksisterende fejl — konsistent hele natten)
3. `test_route_auth_coverage.py` + `test_architecture_ratchet.py` eksplicit
4. Efter reelt deploy til Mac mini-headenden: ny proces bekræftet kørende,
   `curl` mod mindst ét FLYTTET endpoint (401 uden session — ikke 500/404),
   og for baggrundstråd-ændringen specifikt: log-linjen der bekræfter
   tråden faktisk startede (`"AI batch-job poller startet"`), ikke kun at
   routen er monteret.

## Næste skridt

Se plandokumentet for fuld sekventering. Kort opsummeret, i risiko-orden:
Cameras → Customers/Sites (ind i `cmdb.py`) → Capture/storage/thumbnails
(med bonus-oprydning af `importer.py`s lazy imports) → OpenWebUI → Key
management (efter tjek af overlap med `trust_service_api.py`) → Backup/
Retention/config-resolution (med varsomhed omkring `resilience_assessment`s
tvær-domæne state-læsning) → Lab/WebRTC (størst route-gevinst, men mest
runtime-state-risiko) → Updates/artifacts/releases (sidst, 2 PR'er, det er
selve self-update-maskinen) → Compliance/GRC-cockpit (allersidst, efter alt
den læser fra er udtrukket).
