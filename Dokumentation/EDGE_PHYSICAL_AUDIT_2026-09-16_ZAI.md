# Edge Physical/Runtime Audit 2026-09-16 — Edge1 + Edge2 + Builder-reconciliering

**Udført af:** z.ai (GLM-5.3), 2026-09-16, på Peters mandat ("evidence-first physical/runtime audit").
**Metode:** Uafhængig SSH-audit af begge fysiske Edge-enheder via verificerede reverse tunnels (2201/2204, headend-nøgle), headend-Postgres/CMDB-krydsreferencer, og repo-verifikation mod `origin/main @ 8452c5ef`. Intet ændret på enhederne under auditet (evidence-first overholdt; ingen remedieringer eksekveret — se §6). Ingen hemmeligheder eksponeret; følsomme felter er maskeret.

---

## 1. Executive status

| Domæne | Edge1 `TL-C87FF9587CA0` | Edge2 `TL-043EB9E72EFD` | Builder |
|---|---|---|---|
| Overordnet | **PARTIALLY VERIFIED** | **CAPABILITY VERIFIED WITH DOCUMENTED GAPS** | **REPRODUCIBLE WITH GAPS** |
| Kort | Portal/agent/tid/LAN adgang verificeret; men: `qrcode` mangler i venv, OS (Noble) kan ikke genbygges af Builder, kamera ikke tilstede | Live produktion (capture minutter før audit); gaps: VERSION-fil staler, watchdog-unit findes kun på enhed, node-agent-konfig uden service | Declarativ kerne (GPG+SBOM+units) — men: provenans-brud, upinnede deps, timesync/watchdog mangler i image, Jammy-only |

**Konsekvente blokkere:** (1) Builder kan ikke reproducere Edge1 (Noble); (2) artifact-provenans-kontrakt brudt (filer i deployet artifact findes ikke ved source_commit); (3) restart-loop-monitorering eksisterer ikke fleet-niveau (Edge1-hændelsesklassen kan gentage sig uset — DB-bevis: `deployed`-række under 19 timers crash-loop).

## 2. Identiteter (verificeret, ikke antaget)

| | Edge1 | Edge2 |
|---|---|---|
| device_id | `TL-C87FF9587CA0` (bootstrap.yaml) | `TL-043EB9E72EFD` (config.yaml) |
| hostname | `timelapse0101` | `tl-modbaggarddlvc` |
| HW/platform | Orange Pi 4 Pro (sun60iw2, arm64), 5,7 GB, NVMe 117 GB (57% brugt), 56°C | Sammenlignelig, NVMe 117 GB (31%), 48°C |
| OS | **Ubuntu 24.04.4 LTS (Noble)** | **Ubuntu 22.04.5 LTS (Jammy)** |
| Kernel | 5.15.147-sun60iw2 (begge) | — |
| Interfaces | wlan0 192.168.86.134; br-bt 192.168.42.1 (linkdown); end0 DOWN | wlan0 192.168.86.144; br-bt (linkdown); eth0 DOWN |
| Release-artifact | `TL-ART-20260909-51f93baf2817`, source_commit `51f93baf` (main ✓), v2.8.1-lab.54, installeret 09-09 14:32Z | Identisk artifact, 14:35Z |
| VERSION-fil på enhed | `bf8b2770` (juli-docs-commit — **staler/vildledende**) | `dc69c6b2` (**ikke på main!**) — staler |
| CMDB app_version (heartbeat) | `51f93baf…` ✓ korrekt | ✓ korrekt |
| Uptime | 15t39m (naturligt reboot ~03:09 i dag — bruges som reboot-persistens-evidens) | 9d12t (ikke rebootet) |

## 3. Capability-matrix

| # | Capability | Intenderet (autoritet) | Builder | Edge1 runtime | Edge2 runtime | Klassifikation |
|---|---|---|---|---|---|---|
| 1 | Edge-agent service | REQUIRED (target.yaml expected_enabled) | unit i image ✓ | active, NRestarts=0 | active, 0 | **PASS** |
| 2 | App-update + post-restart sundheds-gate | REQUIRED (main, update_lifecycle) | units ankommer via updates | verificeret: alle app-rækker `post_restart_health_confirmed` | samme | **PASS** |
| 3 | Dependency-pin-konsistens (pydantic-klassen) | REQUIRED (post-incident; fetch_python_bundle Pass1/2 re-pin + regressionstest) | re-pin + test ✓ | par nu 2.13.5+**2.46.5** ✓ (efter 14/9-manuel genoprettelse) | 2.13.5+2.46.5 ✓ | **PREVENTED/DETECTED-BEFORE-DEPLOY** — residual: ingen post-install sundheds-gate for *dependency*-updates (kun app); DB `deployed`≠working (bevis: række `TL-PY-20260911-56068cb41` deployed/tom fejl under 19 t crash-loop på Edge1) → **TEST/MONITORING GAP** |
| 4 | TOTP management-portal :8443 | REQUIRED | unit i image ✓ | HTTPS 200, stabil siden fix (0 genstarter) | HTTPS 200, 0 genstarter | **PASS** |
| 5 | Direkte Edge-terminal (portal) | CURRENT MAIN = naiv textarea-terminal (PR #239 xterm = OPEN candidate, IKKE krav) | naiv i image | `/mgmt/cli` 200; naiv renderer; `static/xterm/` ligger **inert** på disken (se §5-provenans) | samme | **PARTIAL** (i overensstemmelse med main); PR #239 afventer merge; **katalog-GAP**: ingen usecase dækker denne flade (kendt) |
| 6 | Multi-network management-reachability (Peters invariant) | REQUIRED (ADR/beslutning 2026-09-14) | service binder alle interfaces | **LAN: 22+8443 ÅBEN, HTTPS 200 fra headend** (ændring vs. 14/9 hvor blokeret — årsag uidentificeret, se §7-D4); SSH-tunnel ✓ | LAN ÅBEN ✓, tunnel ✓ | **PASS (runtime)** + åben note om uforklaret åbning |
| 7 | BT-PAN pairing/captive portal | REQUIRED-når-BT (runtime-afbødnings-klausul) | units i image ✓ | services active; br-bt linkdown (ingen peer) — **NOT TESTABLE** uden BT-klient | samme | **UNKNOWN (ikke testbar på stedet)** |
| 8 | Wi-Fi AP fallback | OPTIONAL (fallback når router-WiFi) | unit i image ✓ | active (exited) | **inactive** (router-WiFi konfigureret) | **PASS** — tilsigtet enhedsspecifik forskel |
| 9 | BLE technician transport | REQUIRED (expected_enabled; main ikke opt-in) | unit i image ✓ | active | active | **PASS** (serviceniveau; funktionel par-ring ikke testet) |
| 10 | GPS-tidsautoritet | REQUIRED (GPS eneste lokale kilde; ingen RTC) | gpsd i image ✓ men **timesync service/timer IKKE i image** (ankommer først via app-update) | gpsd+gpsdctl active; chrony **Stratum 1**, offset −14,5 µs ✓ | Stratum 1 ✓ | runtime **PASS**; **BUILDER GAP**: frisk image mangler timesync indtil første app-update |
| 11 | `qrcode`-afhængighed | Deklareret i edge/requirements.txt; forbruger = technician-QR (dormant: `technician_auth.py:25`, ingen prod-kaldere) | med i requirements (frisk venv ville have den) | **MANGLER** (`import qrcode` fejler) — venv-drift | 8.2 ✓ | Edge1: **DEVICE DRIFT** (lav impact — dormant forbruger) + **BUILDER GAP** (ingen runtime-krav-håndhævelse) |
| 12 | OS-baseline | target.yaml orangepi4pro = **Jammy**; OS_BASELINE-anbefaling (Noble) ikke implementeret | Jammy | **Noble** | Jammy | Edge1: **DEVICE DRIFT + BUILDER GAP** (ikke reproducerbar) |
| 13 | Watchdog | Forventet på enhed (historisk); unit findes **ikke i repo/builder** | fraværende | kører som root; NRestarts=628 — arkitektur: `Restart=always`+30s loop (genstarter er design, ikke incident) | kører; NRestarts=9137 (samme design) | **BUILDER GAP** (uversioneret unit på begge enheder) + **monitoring-pollution** (NRestarts ubrugeligt som alarmsignal for netop denne unit) |
| 14 | node-agent | OPTIONAL/legacy | bootstrap skriver conf | **fraværende** (ingen conf) | conf til stede, service **inactive** | Tilsigtet/legacy-forskel — klassificeret *intended device-specific* (bemærk: inaktiv) |
| 15 | Break-glass/emergency | REQUIRED (ADR-004) | wrapper + runtime-kontoreparation (agent) | konto ✓ shell=wrapper ✓ executable ✓ | ✓ | **PASS** (struktur; session ikke eksherceret) |
| 16 | Kamera/capture | REQUIRED (payload) | gphoto2-stack i image ✓ | kamera **ikke detect** (gphoto auto-detect tom; seneste capture-fil april) → **NOT VERIFIABLE** (formodentlig fysisk frakoblet dev-rig) | **LIVE**: capture `2026-09-16 16:40` + `.qa.json` minutter før audit | Edge2 **PASS**; Edge1 **UNKNOWN** |
| 17 | Version-rapportering | Agent-heartbeat autoritativ; VERSION-fil defekt (kendt) | — | VERSION staler (bf8b2770, juli) | VERSION staler (dc69c6b2, ikke-main) | **DOCUMENTATION/TOOLING GAP** (begge); CMDB korrekt via heartbeat ✓ |
| 18 | Restart-loop monitorering | §16c-status: forslag, uimplementeret | — | NRestarts **indsamles** på edge (collector/service_operations) | samme | Headend: **0 referencer** til NRestarts → collected ≠ visible ≠ alarmed. **Incidentklassen kan gentage sig uset** — åbent (§16c) |
| 19 | Artifact-provenans | REQUIRED (GPG+SBOM+source_commit reproducerbar) | builder tvang: afviser uncommittede inputs | deployet artifact indeholder `edge/scripts/static/xterm/*` som **ikke findes ved source_commit 51f93baf/main** (0 hits i ls-tree) | samme filer | **BUILDER GAP (provenans-integritet)** — se §5 |
| 20 | Secrets-hygiejne | REQUIRED per-device | image fri for secrets ✓ (keys/token/bootstrap fjernes) | device_keys/certs til stede, ikke eksponeret | samme | **PASS** (struktur) |

## 4. Device-delta (Edge1 ↔ Edge2), klassificeret

| Delta | Klassifikation |
|---|---|
| OS Jammy vs Noble | **Builder/version-difference + drift** (Edge1 foran Builder; Noble-anbefaling uimplementeret) |
| Python venv 3.10 vs 3.12 | Builder/version-difference ( følger OS) |
| qrcode 8.2 vs mangler | **Manual drift** (Edge1 — opstået via dependency-update-churn; lav impact) |
| wifi-ap inactive vs active(exited) | **Intended device-specific** (router-WiFI på Edge2) |
| node-agent conf+inactive vs fraværende | **Intended/legacy** |
| dev-rig-pakker: Edge1 = 29 (xfce/xorg/lightdm/pihole-rester), Edge2 = 0 | **Manual drift** (Edge1 dev-rig-arv; reelt harmløst men synligt) |
| NetworkManager: Edge2 har, Edge1 har ikke | Deployment-age difference |
| Kamera LIVE vs frakoblet | **Intended** ( Edge2 produktion / Edge1 dev-lokalitet) |
| Uptime/reboot-historik | Deployment-age |

## 5. Builder ↔ devices (rebuild-readiness)

**Builder-identitet:** `headend/tools/build_edge_disk_image.py` + `inject_edge_image.py`/`inject_wifi_image.py` (image), `fetch_os_bundle.py`/`fetch_python_bundle.py` (offline bundles), `headend/tools/hardware/orangepi4pro/target.yaml`, `Dockerfile.edge`, `edge/requirements.txt` — alt ved `origin/main 8452c5ef`.

**Kan en ødelagt Edge genskabes i dag?**
- **Edge2-equivalent (Jammy): PARTIALLY REPRODUCIBLE.** Base stemmer; men et frisk image mangler: timesync service/timer + watchdog-unit (ankommer først via app-updates), venv er upinnet (`>=`-ranges → kan afvige fra nuværende), OS-patches injecteres aldrig (gamle CVE'er), logrotate-installation manuel. Genopbygning + efterfølgende governed app-updates ≈ tæt på, men ikke garanti.
- **Edge1-equivalent (Noble): NOT REPRODUCIBLE.** Builder bygger Jammy til orangepi4pro; Noble-anbefalingen (#224-dokumentet) er ikke implementeret i Builder.

**Materielle builder-fund (ud over dokumenterede i OS_BASELINE-gapanalysen):**
1. **Provenans-brud:** deployet artifact `TL-ART-20260909-51f93baf2817` indeholder `static/xterm/{LICENSE,xterm.css,xterm.js}` som ikke findes ved source_commit `51f93baf` (verificeret: `git ls-tree -r 51f93baf | grep static` = 0). Filene er runtime-inert (naiv terminal aktiv), men kontrakten "source_commit reproducerer artifact" er brudt — enten er git-tvangen omgået for non-.py-inputs, eller source_commit-registreringen læser forkert grundlag. Kræver rodårsags-efterforskning i builder.
2. Watchdog-unit findes kun på enhederne (uversioneret drift-state som root-service).
3. VERSION-fil-defekten (kendt) bekræftet på BEGGE enheder; Edge2's værdi er endda en ikke-main-SHA.
4. Incident-sporet: Edge1's defekte bundle-række (`TL-PY-20260911-56068cb41`, start 09-09 01:28, **fuldført 09-11 22:52**) vs Edge2's (`TL-PY-20260911-d9f0cc170` 22:49, sundt par) — to forskellige artifacts samme aften; re-pin-fixet (#271-logik i fetch_python_bundle med eksplicit kommentar om netop pydantic-parret) nåede Edge2's bundle, ikke Edge1's. DB-status `deployed`+tom fejl på Edge1 under 19 t crash-loop = runtime-bevis for "deployed ≠ working".

## 6. Remedieringer udført

**Ingen.** Auditet var evidence-first; ingen ændringer blev foretaget på enheder, builder eller netværk. Kandidater klarlagt (kræver enten sudo/Peter eller governed update-flow):
- Edge1 `qrcode`-geninstall (via governed dependency-update med re-pin-flowet, ikke manuel pip).
- Watchdog-unit ind i repo+builder (ny PR; reproducer nuværende /etc/systemd/system-unit ordlyd).
- VERSION-fil-værktøj (opdater ved artifact-deploy) — kendt defekt, udbedres bedst i update-lifecycle.
- Builder: timesync/timer + (watchdog) med i image; digest-pin af rpi5-base (`sha256: null`); requirements-pinning (F-011); provenans-tjek: sammenlign artifact-filmanifest mod `git ls-tree source_commit` ved signering.
Alle fire er formuleret som forslag — ingen eksekveret (§19/§20: forbered, eksekver ikke uden godkendelse).

## 7. Evidens-uddrag (kommandoer forenklet, hemmeligheder maskeret)

- **D1 identitet:** `bootstrap.yaml: device_id TL-C87FF9587CA0` / `config.yaml: device_id TL-043EB9E72EFD`; `hostnamectl`; `.timelapse-release.json` (begge).
- **D2 pydantic-par:** `pip list | grep -i pydantic` → Edge1/Edge2: `pydantic 2.13.5` + `pydantic_core 2.46.5`.
- **D3 qrcode:** Edge1 `python3 -c "import qrcode"` → ModuleNotFoundError; Edge2: `qrcode 8.2` OK. Forbruger: `origin/main:edge/technician_auth.py:25`.
- **D4 reachability:** fra headend: `nc -z .134/.144 22+8443` ÅBEN ×4; `curl -sk https://…:8443/` → 200 ×2. (14/9: samme test = 100% blokeret på begge — delta uden identificeret årsag; ingen firewall ændret af dette audit.)
- **D5 portal/terminal:** `curl -sk localhost:8443/` 200 ×2; `/mgmt/cli` 200 ×2; `ls scripts/static/` → `xterm` (begge); `grep -c xterm totp-service.py` = 1 (naiv terminal aktiv).
- **D6 tid:** `chronyc tracking` → Stratum 1, offset ≤ 0,7 ms, Leap Normal (begge). `timedatectl` fejler "Failed to read RTC" (ingen RTC — forventet).
- **D7 watchdog:** `systemctl cat timelapse-watchdog` → `/etc/systemd/system/…` ExecStart watchdog.sh, Restart=always, RestartSec=30 (restart-loop = design); NRestarts 628/9137.
- **D8 monitorering:** repo-grep `NRestarts` i `headend/` = 0Hits (kun edge-collector/service_operations).
- **D9 updates (Postgres):** Edge1-rækker alle app_updates `post_restart_health_confirmed`; `dependency_updates TL-PY-20260911-56068cb41 deployed 09-11 22:52 (tom fejl)`; Edge2 `TL-PY-20260911-d9f0cc170 deployed 22:49` + os_security `TL-OS-20260916-*` deployet 03:11/03:37 i dag; `pending_updates #272/#304/#308 dependency_updates blocked (lab)`.
- **D10 kamera:** Edge2 `/data/captures/TL-043EB9E72EFD_20260916_164003.jpg(+.qa.json+.json)`; Edge1 seneste filer april + `gphoto2 --auto-detect` tom.
- **D11 reboot-persistens Edge1:** naturligt reboot ~03:09 i dag (uptime 15t39m ved 18:48-audit); efter reboot: alle services active, portal 200, LAN åben, chrony stratum-1, agent online (CMDB last_seen aktuelt) → **VERIFIED (Edge1, naturligt reboot)**. Edge2: **NOT VERIFIED** (ikke rebootet; kontrolleret reboot fraveget for ikke at forstyrre live produktion).
- **D12 break-glass:** `grep ^emergency: /etc/passwd` = 1 (begge), shell = breakglass_shell_wrapper.sh (-rwxr-xr-x).
- **D13 Pi-hole-rester Edge1:** 29 pakker matcher xfce/xorg/lightdm/pihole-mønstret (dev-rig-arv); ingen lytter på :53/:80; DNS via systemd-resolved eksterne resolvers — **harmløse rester, ingen funktionspåvirkning** (ingen kosmetisk oprydning foretaget per mandat).

## 8. Resterende gaps (ejer + disposition)

| Gap | Ejerskab | Disposition | Verifikationskrav |
|---|---|---|---|
| Restart-loop alarming (§16c) uimplementeret | Peter-beslutning → Codex impl. | §16c-afgørelse afventes; headend har ingen NRestarts-vej | Alarm-test med kontrolleret flapping |
| Post-install health-gate for dependency-updates | Codex (update-flow) | Udvid 16.9-gate til dependency-pathen | Negativ test: defekt bundle → gate stopper |
| Builder-provenans (xterm i artifact uden source_commit-fodring) | Codex/ejer af builder | Rodårsag + manifest↔ls-tree-tjek ved signering | Genbyg artifact → diff mod commit |
| Noble-baseline (#224) uimplementeret | Peter-beslutning | Implementér eller fasthold Jammy-bevidst | Frisk build på valgt baseline |
| timesync/watchdog-units mangler i frisk image | Codex (builder-PR) | Foreslået rettelse (§6) | Frisk image-boot uden efterfølgende updates |
| VERSION-fil opdateres ikke ved artifact-deploy | Codex | Kendt defekt; værktøj i update-lifecycle | Deploy → VERSION == source_commit |
| Edge1 qrcode-mangler | Codex via governed dep-update | Reinstall via bundle (ikke manuel pip) | import-qrcode OK post-deploy |
| Watchdog-unit uversioneret | Codex | Commit unit fra enhed til repo | Ratchet/test på unit-tilstedeværelse |
| BT-PAN/terminal-interaktion, TOTP positiv-login, Edge2-reboot, Edge1-kamera | Peter/fysisk | NOT TESTABLE/NOT VERIFIED — kræver BT-klient, TOTP-secret, reboot-vindue, kamera | Fysisk UAT ved lejlighed (UC-LOCAL/UC-TECH NEEDS EDGE/TESTDATA) |
| Uforklaret LAN-åbning (blokeret 14/9 → åben 16/9) | Efterforskning | Ikke rodårsags-fundet (ingen firewall-log-arkiv tilgængelig uden sudo) | Registrér som observation; bevar invariant-test i drift |

## 9. Governance-propagation (§23)

- **TimeLapse-lokalt:** alle builder/tooling-fund ovenfor.
- **Generic kandidat (Mission Framework):** "artifact-provenans: et signeret artifact skal være fil-for-fil reproducerbart fra sit source_commit — verificér manifest mod `git ls-tree` ved signering" (generaliserbar; §16-slægtskab).
- **Allerede dækket af §16.9 (runtime-evidens tilføjet):** DB-rækken `deployed/ingen fejl` under 19 t crash-loop er det stærkeste runtime-bevis til dato for "deployed ≠ working".
- **Mission Platform:** ingen nye; propagations-register-spo­rgsmålet uændret.
- **Websites/publication:** ingen påvirket.
- Negativ konklusion (ingen CI/MP-påvirkning) er evidensbaseret på dette auditors scope.

## 10. Ikke uafhængigt verificeret / usikkerhed

- TOTP **positiv** login-session (kræver secret/Peter) — portaleksistens, HTTPS og login-side verificeret; negativ sti ikke eksherceret.
- Terminalens interaktive UX (Ctrl-C/Tab/historik) — kun niveauerne "endpoint aktiv + renderer-type (naiv) + inert xterm" verificeret; brugerniveau = historisk (Peters fysiske test 13/9).
- BT-PAN- og Ethernet-stier (fysisk fraværende på teststedet).
- Årsagen til LAN-åbningen mellem 14/9 og 16/9 (kræver root/iptables-historik).
- Edge2-reboot-persistens (afstået bevidst).
- Builder-ren build eksekveret **ikke** (ingen test-infrastruktur involveret); builder-konklusioner er kildekode-baserede + gap-analyse (#224) + enheds-observabler.
