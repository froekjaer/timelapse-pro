# Prioriteret backlog for TimeLapse Pro

**Opdateret:** 2026-07-07 (Session 7 — Test script oprettet, backlog opdateret med test-status)

**Kontekst:** Denne backlog er udarbejdet efter gennemgang af RISK_ASSESSMENT_v10.md, GO_LIVE_CHECKLIST_v10.md, KRAVREGISTER_og_STATUS_v10.md, SYSTEM_HEALTH_REGISTER.md og HANDOVER_LOG.md. Den prioriterer arbejder der bringer systemet fra LAB/pre-production til Internet-facing production readiness.

---

## P0 — Blokerende (skal løses før go-live)

| ID | Opgave | Estimat | Ansvar | Status |
|----|--------|---------|--------|--------|
| **P0-01** | **Review og merge PR #2 (M-05 agent-lockdown)** — 24/24 tests passed, kode klar, afventer Peters review | 1 dag | Peter/Claude | PR #2 åben |
| **P0-02** | **Port 8443-migration på staging/prod** — nginx-eksponering på port 8443 (ikke 443/80 grundet CrushFTP), DNS-01 certifikat (certbot-dns-cloudflare) | 2-3 dage | Codex/Peter | 🔴 Ikke bygget |
| **P0-03** | **Backup + restore-test** — bekræft at billed-backup rent faktisk kører i produktion, udfør restore-test, dokumenter RTO/RPO | 3-5 dage | Codex/Peter | 🔴 Mangler |
| **P0-04** | **GDPR DPIA per kunde/site** — udfyld DPIA-skabelon for hver kunde/site, få juridisk godkendelse | 1-2 uger | Peter/jurist | 🟠 Skabelon klar |
| **P0-05** | **Retention policy implementation** — ✅ FÆRDIG 2026-07-07. Database migration v15, backend cleanup loop, API endpoints, UI (RetentionPage + per-kamera felt), test suite (8/8 unit tests), dokumentation opdateret. Kræver migration v15 FØR deploy. | 3-5 dage | Claude-2 | ✅ Implementeret |
| **P0-06** | **Databehandleraftale** — eksisterende for Kirkbi A/S, men skal bekræftes at den dækker AI/Gemini + GPS. Nye kunder kræver ny aftale. | 1-2 uger | Peter/jurist | 🟠 Delvist |
| **P0-07** | **Stale credential cleanup** — TL-DCA63234D813 skal migreres/revokeres, HMAC globalt på alle aktive noder | 2-3 dage | Codex/Claude | 🟠 Stale credentials |
| **P0-08** | **Node-agent genetablering** — stopped 2026-06-22, skal genetableres som user LaunchAgent (ikke root) | 1 dag | Codex | 🟠 Plan klar |

## P1 — Høj prioritet (bør løses før første rigtige kunde)

| ID | Opgave | Estimat | Ansvar | Status |
|----|--------|---------|--------|--------|
| **P1-01** | **Kamera-profil model** — ✅ FÆRDIG 2026-07-07. Separate profiler for Z30/EOS 2000/1300/1000 med fælles base settings, GPS/NTP sync capabilities, shutter ratings, datetime sync funktion. | 3-5 dage | Codex/Claude | ✅ Implementeret |
| **P1-02** | **Kamera/site-scope i update-UI** — ✅ FÆRDIG 2026-07-07. Verificeret at UI har alle 4 scopes (global/device/customer/site) med fungerende dropdowns. | 2-3 dage | Claude | ✅ Implementeret |
| **P1-03** | **Intern CA + client-certs (mTLS)** — design færdigt, implementering mangler (Peter skal generere nøgler) | 1-2 uger | Peter/Claude | 🔴 Mangler |
| **P1-04** | **OS offline-update E2E på aktiv Edge** — verifikation at det virker fra A til Z | 2-3 dage | Codex/Claude | 🟠 Kode klar |
| **P1-05** | **Per-target deployment status** — 13/13 tests passed, men live multi-device-rollout-test mangler | 2-3 dage | Codex/Peter | 🟡 Flush rettet |
| **P1-06** | **ESLint-baseline oprydning** — 222 problemer, ratchet-gate klar, men reelle fejl bør rettes løbende | 1-2 uger | Claude | 🟡 Ratchet klar |
| **P1-07** | **Fail2ban på staging/prod** — verify_fail2ban.sh v1.0.1 opdateret med pfctl+--apply. Klar til deployment/test på staging. | 1 dag | Codex/Claude | 🟡 Script klar, kræver deploy |
| **P1-08** | **Dokumentationssynk** — ✅ FÆRDIG 2026-07-07. Datoer opdateret til 2026-07-07, ADM-002 og SEC-003 opdateret til "Implementeret", status konsistent på tværs af RISK/GO_LIVE/KRAVREGISTER. | 1-2 dage | Claude | ✅ Implementeret |
| **P1-09** | **MFA/WebAuthn UI-forbedringer** — TOTP enforced, men UI kan forbedres (setup, recovery, etc.) | 2-3 dage | Claude | 🟡 TOTP klar |
| **P1-10** | **Break-glass rate-limit/IP-allowlist** — i dag opt-in via env-var, bør gøres mere robust | 2-3 dage | Claude/Codex | 🟡 MFA dækker |

## P2 — Medium prioritet (teknisk gæld og kvalitet)

| ID | Opgave | Estimat | Ansvar | Status |
|----|--------|---------|--------|--------|
| **P2-01** | **Refaktorering af headend/main.py** — brydes op i mindre komponenter for bedre vedligeholdelse | 1-2 uger | Claude | 🟡 Store moduler |
| **P2-02** | **Thumbnail postprocessing backlog** — ✅ FÆRDIG 2026-07-07. API endpoint `/api/admin/thumbnail-backlog` implementeret med UI badge på PostProcessingPage. | 2-3 dage | Claude/Codex | ✅ Implementeret |
| **P2-03** | **Sløring/redaction workflow (UI-010)** — ✅ FÆRDIG 2026-07-07. Database migration v17 (redaction fields), OpenCV-based detection/sløring (ansigter/nummerplader), API endpoints (/api/redaction/*), UI (RedactionPage.tsx + navbar link). Kræver migration v17 FØR deploy. | 1-2 uger | Claude/Codex | ✅ Implementeret |
| **P2-04** | **Web terminal (xterm.js/websocket SSH)** — remote shell til Edge-noder | 1-2 uger | Claude/Codex | 🔴 Mangler |
| **P2-05** | **GPS tidssynkronisering** — GPS-clock til Edge-noder | 1 uge | Codex | 🔴 Mangler |
| **P2-06** | **Lokal management UI på Edge** — til provisioning/debug uden headend-forbindelse | 1-2 uger | Claude/Codex | 🔴 Mangler |
| **P2-07** | **Disk-kryptering på Edge (LUKS/overlayFS)** — R05-kompromitteret edge | 1-2 uger | Codex | 🔴 Mangler |
| **P2-08** | **SBOM auto-generering** — ✅ FÆRDIG 2026-07-07. CycloneDX 1.5 SBOM genereres automatisk i `build_os_bundle.py`. | 3-5 dage | Claude/Codex | ✅ Implementeret |
| **P2-09** | **GRC evidence-links** — ✅ FÆRDIG 2026-07-07. `_evidence_links_for_control()` helper + UI links til ADMINISTRATORMANUAL/RISK/GO_LIVE/KRAVREGISTER. | 3-5 dage | Claude | ✅ Implementeret |
| **P2-10** | **Python testmiljø** — ✅ FÆRDIG 2026-07-07. requirements-dev.txt + pyproject.toml oprettet i roden med pytest, ruff, black, mypy config. | 1 dag | Claude/Codex | ✅ Implementeret |
| **P2-11** | **Incident response procedure** — ✅ FÆRDIG 2026-07-07. SEC-013 oprettet, dokumenteret i ADMINISTRATORMANUAL §1.5.6, R20 i RISK_ASSESSMENT. | 2-3 dage | Peter/Claude | ✅ Implementeret |
| **P2-12** | **Vulnerability handling/CVE-process** — ✅ FÆRDIG 2026-07-07. SEC-014 oprettet, dokumenteret i ADMINISTRATORMANUAL §1.5.7, G-08 i GO_LIVE_CHECKLIST. | 2-3 dage | Peter/Claude | ✅ Implementeret |

## P3 — Lav prioritet (nice-to-have, fremtidige features)

| ID | Opgave | Estimat | Ansvar | Status |
|----|--------|---------|--------|--------|
| **P3-01** | **Kold/varm backup Headend** — arkitektur ikke designet endnu | 2-3 uger | Peter/Claude | 🔴 Mangler |
| **P3-02** | **www.timelapse-pro.dk** — public marketing site, hostes separat fra staging/prod | 1 uge | Claude/Peter | 🟡 Draft klar |
| **P3-03** | **Tag-oversættelse i UI** — tags vises på engelsk, skal vises på dansk i "AI Styring" og "Tag søgning" | 2-3 dage | Claude | 🟡 Queued |
| **P3-04** | **Multi-headend/customer-owned governance** — udvidet RBAC til multi-headend | 1-2 uger | Claude/Codex | 🔴 Mangler |
| **P3-05** | **Cloud tag-pipeline (Gemini, fast ontologi)** — forbedret AI-tagging | 1-2 uger | Claude/Codex | 🟡 Delvist |
| **P3-06** | **AI resource governance** — budget, limits, monitoring for Gemini/GCS | 2-3 dage | Claude/Codex | 🟠 Åben |

---

## Kritisk sti til go-live (minimalt viable production)

Følgende P0-opgaver **skal** være løst før systemet kan gå Internet-facing production:

1. ✅ **P0-01**: PR #2 merged (M-05 agent-lockdown)
2. 🔴 **P0-02**: Port 8443-migration + DNS-01 certifikat
3. 🔴 **P0-03**: Backup verify + restore-test
4. 🟠 **P0-04**: DPIA udfyldt + juridisk godkendt
5. ✅ **P0-05**: Retention policy implementeret (2026-07-07)
6. 🟠 **P0-06**: DPA bekræftet for AI/Gemini + GPS
7. 🟠 **P0-07**: Stale credentials ryddet
8. 🟠 **P0-08**: Node-agent kørende

**Estimeret tid:** 4-6 uger med fokusindsats.

---

## Test Status — Weekend 5-7 Juli 2026 Features

**Opdateret:** 2026-07-07
**Test Script:** `tests/test_weekend_features_api.py`

### Test Suite Oversigt

| Kategori | Tests | Status | Prioritet |
|----------|-------|--------|-----------|
| **P2-03 GDPR Redaction** | 3 | ⬜ | HØJ |
| **P0-05 Retention Policy** | 2 | ⬜ | KRITISK |
| **Drift-Detection** | 2 | ⬜ | HØJ |
| **M-05 Agent-Lockdown** | 1 | ⬜ | SIKKERHED |
| **Update UI Scopes** | 1 | ⬜ | MEDIUM |
| **P2-02 Thumbnail Backlog** | 1 | ⬜ | MEDIUM |
| **Database Schema (v15-v17)** | 3 | ⬜ | KRITISK |
| **TOTAL** | **13** | **⬜** | |

### Kør Test Script

```bash
# Mod localhost (kræver headend kørende)
python tests/test_weekend_features_api.py

# Mod staging/produktion
TIMELAPSE_TEST_BASE_URL=https://timelapse-pro-staging.kirkbi.local \
TIMELAPSE_TEST_USER=admin \
TIMELAPSE_TEST_PASSWORD=*** \
python tests/test_weekend_features_api.py

# Med verbose output
python tests/test_weekend_features_api.py --verbose

# Uden login (offentlige endpoints)
python tests/test_weekend_features_api.py --no-login
```

### Manual UI Tests (ikke automatiseret)

Disse skal testes manuelt i browseren:

| # | Feature | UI Side | Status |
|---|---------|---------|--------|
| **UI-01** | GDPR Redaction (dansk tekst) | Admin → GDPR Sløring | ⬜ |
| **UI-02** | Retention per kamera | Enheder → rediger kamera | ⬜ |
| **UI-03** | Global retention config | Admin → Retention | ⬜ |
| **UI-04** | Drift config hierarki | Admin → Drift → Config | ⬜ |
| **UI-05** | Update scopes | Admin → Opdateringer | ⬜ |
| **UI-06** | Thumbnail backlog badge | Admin → Post-processing | ⬜ |

### Database Migration Checks

Før testen køres, sørg for at følgende migrations er kørt:

```bash
# Tjek v15 (Retention)
psql -U timelapse -d timelapse_db -c "\d cameras" | grep retention_days
psql -U timelapse -d timelapse_db -c "\d captures" | grep retention_date

# Tjek v16 (wb_cast_strength)
psql -U timelapse -d timelapse_db -c "\d captures" | grep wb_cast_strength

# Tjek v17 (Redaction)
psql -U timelapse -d timelapse_db -c "SELECT unnest(enum_range(NULL::redaction_status_enum));"
psql -U timelapse -d timelapse_db -c "\d captures" | grep redaction_status
```

---

## Næste skridt (denne session)

1. **Review PR #2** — gennemgå koden, testene og dokumentationen
2. **Lave konkret handlingsplan** for P0-02 (port migration) — trin-for-trin guide
3. **Synkronisere dokumentstatus** — fjerne uoverensstemmelser mellem docs
4. **Opdatere ADMINISTRATORMANUAL_v10.md** — med M-05, R17, G-05, R09
5. **Analysere teknisk gæld** i headend/main.py — konkrete forslag til refaktorering

---

## Referencer

- `RISK_ASSESSMENT_v10.md` — detaljeret risikoanalyse
- `GO_LIVE_CHECKLIST_v10.md` — fuld go-live liste (A-M)
- `KRAVREGISTER_og_STATUS_v10.md` — alle krav med status
- `SYSTEM_HEALTH_REGISTER.md` — teknisk gæld og fund
- `HANDOVER_LOG.md` — løbende log af sessioner
- `Claude_Support_Access_Model_2026-07-06.md` — break-glass design
- `Claude_Intern_CA_mTLS_Design_2026-07-05.md` — CA/mTLS design
