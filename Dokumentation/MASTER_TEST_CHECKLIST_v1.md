# TimeLapse Pro — Master Test Checklist

**Dato:** 2026-07-15
**Version:** 1.2
**Scope:** Komplet system audit for at fange alle småfejl og mangler
**Opdateret:** v1.2 (2026-07-15, Claude/Cowork): tilføjet §0.5 (unit vs. integration-split — hovedårsag til "36 fejlende tests") og §9 (manglende tests defineret, prioriteret). v1.1: F-012, Drift Detection, M-05, LAB Force Stop.

> **Læs §0.5 og §9 først hvis du skal arbejde med tests.** De forklarer hvorfor CI kun kører 3 filer, hvorfor ~20 tests "fejler" uden at koden er i stykker, og definerer præcist hvilke tests der mangler.

---

## 📊 System Oversigt

| Komponent | Filer | Tests | Coverage | Status |
|-----------|-------|-------|----------|--------|
| **Headend Backend** | 73 moduler | 23 test files | ~30% | ⚠️ Partial |
| **Edge Agent** | 61 moduler | 2 test files | ~5% | 🔴 Minimal |
| **React UI** | 31 sider | 0 automated | 0% | ⚠️ Manual |
| **Database** | 28 tables | 17 migrations | ✅ | ✅ OK |
| **API Endpoints** | 337 endpoints | ~150 tests | ~45% | ⚠️ Partial |

---

## 🎯 Prioriterede Test Kategorier

### P0 — Kritisk (MÅ testes før go-live)
- Authentication & Authorization
- Database operations
- Core API endpoints
- Edge communication

### P1 — Høj (Bør testes)
- AI/ML integrations
- Quality & drift detection
- GDPR features
- Update/rollback

### P2 — Medium (Kan testes post-GA)
- UI/UX workflows
- Reporting/export
- SIEM events
- Configuration

### P3 — Lav (Nice-to-have)
- Edge tools
- Performance
- Edge cases

---

## 0.5 TESTARKITEKTUR — unit vs. integration (NY, 2026-07-15, kritisk)

**Dette er hovedforklaringen på "36 fejlende tests" i HANDOVER_LOG (2026-07-13).** De fejler ikke fordi koden er i stykker — de er **live-integrationstests der kræver en kørende headend** på `127.0.0.1:8000` med seedede testbrugere.

### Fakta (verificeret 2026-07-15)

| Kategori | Antal filer (`tests/`) | Kører i CI/sandbox uden server? |
|---|---|---|
| **Live-integration** (kalder `api()` mod `:8000`, se `conftest.py`) | ~20 af 38 | ❌ Nej — kræver kørende headend + seedet DB |
| **Unit/kontrakt** (ingen server) | ~18 af 38 | ✅ Ja |
| `headend/tests/` (unit/kontrakt) | 11 | ✅ Ja |
| Kræver `paramiko`/edge-deps | 5 | ⚠️ Kun hvis deps installeret |

- `tests/conftest.py` definerer `TEST_CREDENTIALS` (admin/super_admin/viewer/operator med faste passwords) og `BASE_URL = TIMELAPSE_TEST_BASE_URL` (default `http://127.0.0.1:8000`). Disse tests logger reelt ind mod en levende server — uden den giver de `ConnectionError`, ikke en assertion-fejl.
- `.github/workflows/ci.yml` kører derfor **kun 3 filer** (`test_agent_integrity.py`, `test_headend_endpoints.py`, smoke) — resten ville altid være røde i en server-løs runner.
- **Assurance-hul (VPEN-2026-013):** en reel regression i unit-testbar kode (fx et fremtidigt uautentificeret endpoint, jf. R22) fanges IKKE af CI i dag.

### Anbefalet testarkitektur (skal besluttes)

1. **Markér** live-integrationstests: `@pytest.mark.integration`, og tilføj en autouse-fixture i `conftest.py` der `pytest.skip()`'er hvis `BASE_URL` ikke svarer (så de bliver "skipped", ikke "failed", uden server).
2. **Unit-subset i CI:** kør `pytest -m "not integration"` som blokerende gate mod en kendt-grøn baseline (ratchet — antal fejl må ikke stige, jf. H-02 ESLint-mønsteret).
3. **Integrationsjob (ikke-blokerende):** kør `pytest -m integration` mod `rd`-miljøet i et separat job, så resultater ses uden at blokere merge.
4. **Triager** de reelt knækkede unit-tests (dem der fejler MED en server, eller uden at være integration) enkeltvis: fix, `xfail` med issue-reference, eller slet. Ingen test må stå rød uden kategori.
5. **Ryd `__pycache__`** ud af Git (fylder testlisten med støj) og tilføj `paramiko`/`cryptography` til `requirements-dev.txt` så edge-SFTP-tests kan collectes.

---

## 0. NYE TESTS (2026-07-12)

### 0.1 F-012 Site-Wide Look Matching (P0)

| Test Suite | Tests | Passed | Status | File |
|------------|-------|--------|--------|------|
| Unit Tests | 72 | 72 | ✅ PASS | `edge/ai/tests/test_site_look_manager.py` |
| Integration Tests | 15 | 15 | ✅ PASS | `edge/ai/tests/test_site_look_integration.py` |
| Manual Checklist | 26 | 26 | ✅ PASS | `edge/ai/tests/test_site_look_manual.py` |
| Config Service Tests | 14 | 14 | ✅ PASS | `headend/tests/test_site_look_config_service.py` |
| **TOTAL F-012** | **127** | **127** | **✅ PASS** | |

**Test Coverage:**
- ColorProfile (Nikon Z30, Canon EOS)
- Picture Controls/Styles
- SiteReferenceFrame creation and persistence
- CameraLUT generation and application
- Quality threshold validation (75% boundary)
- Scene classification (night, golden hour, overcast, day)
- Color temperature estimation
- Capture hints and recommendations
- Multi-camera matching (Nikon + Canon)
- Database-driven configuration (hierarchical: global > customer > site > camera)
- Edge caching with TTL
- API endpoints (health, config, audit log)

**Bugs Fixed:**
- ColorProfile field name typo
- Picture Control params case sensitivity
- Decimal JSON serialization
- DateTime in edge config

**Documentation:**
- Feature documentation: `docs/feature-site-look-matching.md`
- User guide: `docs/user-guide-site-look-matching.md`
- Admin guide: `docs/admin-guide-site-look-matching.md`
- Risk assessment: `docs/risk-assessment-site-look-matching.md`
- Go-live status: `docs/go-live-status-f012-site-look-matching.md`

---

### 0.2 Drift Detection (P1)

| Test Suite | Tests | Passed | Status | File |
|------------|-------|--------|--------|------|
| Drift Detection Tests | 24 | 24 | ✅ PASS | `headend/tests/test_drift_detection.py` |

**Test Coverage:**
- Nikon Z30 drift detection algorithm
- Quality score drift
- Exposure value drift
- White balance drift
- Focus drift detection
- Timestamp drift
- Composite drift score calculation
- Drift threshold configuration

**Documentation:**
- Feature documentation: `docs/drift-detection-feature.md` (if exists)
- Risk assessment: `RISK_ASSESSMENT_v10.md` §11

---

### 0.3 M-05 Agent Lockdown (P0)

| Test Suite | Tests | Passed | Status | File |
|------------|-------|--------|--------|------|
| Agent Lockdown Tests | 78 | 78 | ✅ PASS | `headend/tests/test_agent_principal_lockdown.py` |

**Test Coverage:**
- Agent role blocked in staging/prod/production
- Default-deny policy enforcement
- Login endpoint blocking
- get_current_user() blocking
- SIEM event logging
- Environment detection (TIMELAPSE_ENV)
- AccessTicket schema prep (for mTLS device certs)
- KeyCredential schema prep (for CA integration)

**Documentation:**
- Risk assessment: `RISK_ASSESSMENT_v10.md` M-05
- Go-live checklist: `GO_LIVE_CHECKLIST_v10.md` §M

---

### 0.4 LAB Mode Force Stop (P1)

| Feature | Test | Status |
|---------|------|--------|
| Force Stop button (header) | ✅ Manual | PASS |
| Force Stop button (notice section) | ✅ Manual | PASS |
| LAB mode reset functionality | ✅ Manual | PASS |

**Test Coverage:**
- Force Stop button visible when labConnecting=true
- Button triggers forceStopLab function
- LAB mode state reset to idle
- Camera connection recovery

**Documentation:**
- FAQ: `FAQ_og_fejlsøgning.md` "LAB mode hænger" section

---

## 1. HEADEND BACKEND TESTS

### 1.1 Authentication & Authorization (P0)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `POST /api/auth/login` | ✅ | `test_api_integration.py` | |
| `POST /api/auth/logout` | ✅ | `test_api_integration.py` | |
| `GET /api/auth/me` | ✅ | `test_api_integration.py` | |
| `POST /api/auth/webauthn/*` | ⚠️ | Partial | |
| `POST /api/auth/setup-mfa` | ⚠️ | Partial | |
| `POST /api/auth/confirm-mfa` | ⚠️ | Partial | |
| Role-based access control | ✅ | `test_operational_readiness.py` | |

**Gaps:**
- WebAuthn full workflow test
- MFA setup + login integration test
- Session expiration
- Cookie domain handling

---

### 1.2 User Management (P0)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `GET /api/admin/users` | ✅ | `test_headend_endpoints.py` | |
| `POST /api/admin/users` | ⚠️ | Partial | |
| `PUT /api/admin/users/{id}` | ❌ | Missing | |
| `DELETE /api/admin/users/{id}` | ❌ | Missing | |
| `POST /api/admin/users/{id}/mfa/reset` | ✅ | `test_headend_endpoints.py` | |

**Gaps:**
- User CRUD operations
- User deactivation
- Password change flow
- Default admin password warning

---

### 1.3 Device Management (P0)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `GET /api/admin/devices` | ✅ | `test_api_integration.py` | |
| `GET /api/admin/devices/{id}` | ✅ | `test_api_integration.py` | |
| `POST /api/admin/devices` | ❌ | Missing | |
| `PUT /api/admin/devices/{id}` | ❌ | Missing | |
| `DELETE /api/admin/devices/{id}` | ❌ | Missing | |

**Gaps:**
- Device CRUD operations
- Device assignment
- Device decommission

---

### 1.4 Camera Management (P1)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `GET /api/admin/cameras` | ✅ | `test_api_integration.py` | |
| `GET /api/admin/cameras/{id}` | ✅ | `test_api_integration.py` | |
| `POST /api/admin/cameras` | ❌ | Missing | |
| `PUT /api/admin/cameras/{id}` | ⚠️ | Partial (test_retention_policy.py) | |
| `DELETE /api/admin/cameras/{id}` | ❌ | Missing | |
| `GET /api/cameras/{id}/drift-analysis` | ✅ | `test_drift_detection.py` | |

**Gaps:**
- Camera CRUD operations
- Camera config validation
- Drift detection integration test

---

### 1.5 Capture & Images (P0)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `GET /api/images/{device}/{filename}` | ✅ | `test_capture_access_log.py` | |
| `GET /api/images/{device}/{filename}/thumbnail` | ❌ | Missing | |
| `POST /api/images/{id}/redact` | ⚠️ | Partial (test_gdpr_redaction.py) | |
| `GET /api/redaction/pending` | ✅ | `test_gdpr_redaction.py` | |

**Gaps:**
- Thumbnail generation
- Redaction workflow full integration
- Image format variants

---

### 1.6 Retention Policy (P0)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `GET /api/admin/retention/status` | ✅ | `test_retention_policy.py` | |
| `PUT /api/admin/retention/settings` | ✅ | `test_retention_policy.py` | |
| `POST /api/admin/retention/trigger` | ✅ | `test_retention_policy.py` | |
| `GET /api/admin/retention/deletion-log` | ✅ | `test_retention_policy.py` | |

**Gaps:**
- Retention cleanup loop integration
- Per-camera retention override

---

### 1.7 Updates & Rollback (P1)

| Endpoint | Test | Status | File |
|----------|------|--------|------|
| `GET /api/admin/updates` | ✅ | `test_update_lifecycle.py` | |
| `POST /api/admin/updates/{id}/approve` | ✅ | `test_update_lifecycle.py` | |
| `POST /api/admin/updates/{id}/deploy` | ✅ | `test_update_lifecycle.py` | |
| `POST /api/admin/updates/{id}/rollback` | ✅ | `test_update_lifecycle.py` | |

**Gaps:**
- Multi-target rollout
- Update rollback verification
- Change ticket integration

---

### 1.8 AI/ML Integrations (P1)

| Module | Test | Status | File |
|--------|------|--------|------|
| `ai/drift_detection.py` | ✅ | `test_drift_detection.py` | |
| `ai/gemini_service.py` | ✅ | `test_gemini_region_guard.py` | |
| `ai/ollama_service.py` | ❌ | Missing | |
| `ai/integration.py` | ❌ | Missing | |
| `ai/model_results.py` | ❌ | Missing | |

**Gaps:**
- Ollama service integration
- AI model fallback logic
- Region guard enforcement

---

### 1.9 SIEM & Events (P2)

| Module | Test | Status | File |
|--------|------|--------|------|
| `siem.py` | ⚠️ | Partial | |
| Event logging | ❌ | Missing | |
| Debug mode events | ❌ | Missing | |

**Gaps:**
- SIEM event verification
- Event persistence
- Debug mode audit trail

---

### 1.10 Security Features (P0)

| Feature | Test | Status | File |
|----------|------|--------|------|
| Agent lockdown (M-05) | ✅ | `test_agent_principal_lockdown.py` | |
| Default admin password | ✅ | `test_default_admin_password_warning.py` | |
| Access tickets | ✅ | `test_access_ticket_and_device_cert_schema.py` | |
| Device certificates | ✅ | `test_access_ticket_and_device_cert_schema.py` | |

**Gaps:**
- mTLS device cert verification
- Break-glass account logging
- Key audit event completeness

---

## 2. EDGE AGENT TESTS

### 2.1 Core Agent (P0)

| Module | Test | Status | File |
|--------|------|--------|------|
| `agent.py` (2432 lines) | ⚠️ | Minimal | |
| `security.py` | ❌ | Missing | |
| Camera drivers | ❌ | Missing | |

**Gaps:**
- Agent startup sequence
- Camera communication
- Upload retry logic
- Quality analysis integration

---

### 2.2 Edge Quality & AI (P1)

| Module | Test | Status | File |
|--------|------|--------|------|
| `quality.py` | ⚠️ | `test_edge_quality_qa.py` | |
| `ai/autonomous_optimizer.py` | ❌ | Missing | |
| NPU runner | ❌ | Missing | |

**Gaps:**
- Quality score calculation
- QA result upload
- NPU model execution

---

### 2.3 Edge Diagnostics (P2)

| Module | Test | Status | File |
|--------|------|--------|------|
| `diagnostics/camera_diagnostics.py` | ❌ | Missing | |
| Config drift detection | ❌ | Missing | |

**Gaps:**
- Drift detection algorithm
- Diagnostics upload

---

### 2.4 Edge Tools (P3)

| Tool | Test | Status |
|------|------|--------|
| `bootstrap_cli.py` | ❌ | Manual only |
| `tools/edge_qa_npu_runner.py` | ❌ | Missing |
| QA dataset tools | ❌ | Missing |

---

## 3. REACT UI TESTS

### 3.1 Core Pages (P0)

| Page | Test | Status | Notes |
|------|------|--------|-------|
| `LoginPage.tsx` | ❌ | Manual | |
| `Dashboard.tsx` | ❌ | Manual | |
| `DevicePage.tsx` | ❌ | Manual | |
| `CameraPage.tsx` | ❌ | Manual | |
| `UsersPage.tsx` | ❌ | Manual | |

**UI Testing Notes:**
- Automated UI tests require Playwright/Cypress
- Manual test checklist needed for go-live
- All pages have API validation

---

### 3.2 Feature Pages (P1)

| Page | Feature | Test | Status |
|------|---------|------|--------|
| `RetentionPage.tsx` | P0-05 | ❌ | Manual |
| `RedactionPage.tsx` | P2-03 | ❌ | Manual |
| `UpdatesPage.tsx` | Updates | ❌ | Manual |
| `LabPage.tsx` | R17 | ❌ | Manual |
| `SIEMPage.tsx` | SIEM | ❌ | Manual |

---

### 3.3 Admin Pages (P1)

| Page | Feature | Test | Status |
|------|---------|------|--------|
| `SystemAdminPage.tsx` | Admin | ❌ | Manual |
| `GlobalConfigPage.tsx` | Config | ❌ | Manual |
| `KeyManagementPage.tsx` | Keys | ❌ | Manual |
| `CompliancePage.tsx` | GRC | ❌ | Manual |

---

## 4. DATABASE TESTS

### 4.1 Schema Tests (P0)

| Table | Migration Test | Status |
|-------|----------------|--------|
| All 28 tables | ✅ | `test_access_ticket_and_device_cert_schema.py` | |
| Migration files | ✅ | 17 migrations verified | |

**Gaps:**
- Migration rollback tests
- Data migration tests
- Foreign key constraints

---

### 4.2 Data Integrity (P1)

| Feature | Test | Status | File |
|---------|------|--------|------|
| Cascade deletes | ❌ | Missing | |
| Constraint validation | ❌ | Missing | |
| Index performance | ❌ | Missing | |

---

## 5. INTEGRATION TESTS

### 5.1 End-to-End Workflows (P0)

| Workflow | Test | Status |
|----------|------|--------|
| User login → view devices | ❌ | Missing |
| Create camera → configure → capture | ❌ | Missing |
| Upload → QA → redaction → approval | ❌ | Missing |
| Update → approve → deploy → rollback | ❌ | Missing |

---

### 5.2 External Integrations (P1)

| Service | Test | Status |
|---------|------|--------|
| Open WebUI | ❌ | Missing |
| Gemini Cloud | ⚠️ | `test_gemini_region_guard.py` |
| Ollama | ❌ | Missing |
| SIEM | ❌ | Missing |

---

## 6. MANUAL TEST CHECKLIST

### 6.1 Pre-Go-Live (P0)

- [ ] All users can login
- [ ] All devices show correct status
- [ ] Camera configuration applies
- [ ] Captures upload successfully
- [ ] QA analysis runs
- [ ] Retention cleanup works
- [ ] GDPR redaction works
- [ ] Update approval works
- [ ] Rollback works
- [ ] SIEM events appear

---

### 6.2 Edge Technician UI (P1)

- [ ] Bootstrap UI loads (port 8099)
- [ ] Camera detection works
- [ ] Photo capture works
- [ ] QA test images generate
- [ ] Network config applies

---

### 6.3 GDPR Compliance (P0)

- [ ] Capture access log written
- [ ] Deletion log complete
- [ ] Retention policy enforced
- [ ] Redaction workflow complete
- [ ] Data export works

---

## 7. TEST COVERAGE SUMMARY

| Category | Files | Test Files | Coverage % |
|----------|-------|-------------|-------------|
| Headend Backend | 73 | 28 | 38% |
| Edge Agent (AI) | 61 | 5 | 8% |
| React UI | 31 | 0 | 0% |
| Database | 28 | 18 | 64% |
| **TOTAL** | **193** | **51** | **26%** |

**Nye tests siden 2026-07-08:**
- +127 tests (F-012 Site-Wide Look Matching)
- +24 tests (Drift Detection)
- +78 tests (M-05 Agent Lockdown)
- **+229 nye tests i alt**

---

## 8. RECOMMENDED TEST PRIORITY

### Phase 1 — Pre Go-Live (P0)
1. ✅ Complete retention policy tests
2. ✅ Complete GDPR redaction tests  
3. ✅ Complete drift detection tests
4. ✅ Complete security tests (M-05)
5. ⚠️ Add authentication integration tests
6. ⚠️ Add device management tests
7. ⚠️ Add update lifecycle tests

### Phase 2 — Post GA (P1)
1. Add AI/ML integration tests
2. Add SIEM event tests
3. Add edge agent tests
4. Add UI component tests

### Phase 3 — Long-term (P2)
1. Performance tests
2. Load tests
3. Edge case tests
4. Automated UI tests

---

**Status:** 🟢 **26% overall coverage — P0 features mostly covered, F-012 fully tested**

**Next Steps:**
1. ✅ F-012 Site-Wide Look Matching — Fully tested (127/127)
2. ✅ Drift Detection — Fully tested (24/24)
3. ✅ M-05 Agent Lockdown — Fully tested (78/78)
4. ⚠️ Complete remaining Phase 1 tests (P0)
5. ⚠️ Manual UI verification
6. ⚠️ Create automated UI test suite (Jest)
7. ⚠️ Increase edge test coverage

---

*Signed off: Peter (TimeLapse Pro) — 2026-07-08*
*Updated: 2026-07-12 (Claude — tilføjet F-012, drift detection, M-05 tests)*
*Updated: 2026-07-15 (Claude/Cowork — §0.5 testarkitektur + §9 manglende tests defineret)*

---

## 10. CODEX BASELINE OG IMPLEMENTEREDE TESTS — 2026-07-15

### 10.1 Reproducerbar baseline

Codex etablerede et rent Python 3.12-testmiljø med `requirements-dev.txt`,
`headend/requirements.txt` og `edge/requirements.txt`. Med eksplicit SQLite-test-DB,
samlet `PYTHONPATH` og `--import-mode=importlib` kan hele inventaret nu collectes uden
at ramme live PostgreSQL eller en delt Headend.

| Måling | Resultat |
|---|---:|
| Tests collected | **1.028** |
| Serverløse unit/contract valgt | **485** |
| Bestået | **481** |
| Skipped | **4** (auth-afhængige live smoke-kald) |
| Fejlet | **0** |
| Deselecterede integration/hardware | **543** |

Kommandoen er nu CI-gate i `.github/workflows/ci.yml`. CI installerer alle tre
dependency-sæt og kører:

```bash
DATABASE_URL=sqlite:////tmp/timelapse-ci.db \
PYTHONPATH="$PWD:$PWD/headend:$PWD/edge" \
pytest tests headend/tests edge/ai/tests \
  --import-mode=importlib -m "not integration" -p no:randomly -q
```

### 10.2 Implementeret fra §9

| ID/område | Status | Evidens |
|---|---|---|
| T-SEC-01 route-auth sweep | **PASS** | `headend/tests/test_route_auth_coverage.py`; eksplicit allowlist med rationale |
| T-SEC-02 AI admin-flader | **PASS (contract)** | Mutation/review kræver role dependency; `tests/test_ai_admin_security_contract.py` |
| T-SEC-03 MFA disable/reset step-up | **PASS** | Frisk password + TOTP; kun super-admin må ændre andre; særskilte `mfa_disabled`/`mfa_reset` SIEM-events |
| T-SEC-04 CORS fail-fast | **PASS** | staging/prod kræver eksplicit `ALLOWED_ORIGIN` |
| T-AI-01 tag similarity | **PASS** | Reel repository-metode med fake DB, ikke kun tekstscan |
| T-AI-02 translations viewer | **PASS (contract)** | Separat viewer-router; mutationer forbliver admin |
| T-UPD-01 multi-target rollup | **PASS** | Fire rollup-tests opdateret til device-auth-kontrakten |
| SIEM RAM anti-flap | **PASS** | Enkelt sample kan ikke længere opfylde 60 sek.; tre tests |
| Open WebUI/Ollama lifecycle | **PASS (unit)** | Status/PID, `keep_alive=0`, Ollama-daemon stoppes ikke |
| LAB `_lab_tick` state machine | **PASS (unit)** | Retry, powercycle, exhausted retries, disable-cleanup og `set_param` rapportering |
| Arkitektur-ratchet | **PASS** | `main.py` må ikke vokse over 18.483 linjer eller 235 direkte routes |
| Hardware target-profiler | **PASS** | 27 tidligere fejlklassificerede tests er serverløse og nu med i CI |
| GDPR redaction session-secret | **PASS** | Router bruger samme runtime-secret som Headend; kendt dev-secret kan ikke validere forfalskede sessions |
| Gemini batch-status | **PASS** | Object- og dict/camelCase completion stats samt manglende progress |

Route-auditten fandt og rettede samtidig ubeskyttede flader, som de tidligere
tekst-/eksistenstests ikke fangede: `/api/import/*`, `/api/timelapse/*`,
`/api/settings*` og tre `/api/node/{device_id}/*`-ruter. Import, timelapse og
settings er nu rollebeskyttet; node-ruter bruger Edge device-auth.

### 10.3 Testklassifikation rettet

`tests/test_api_integration.py` og `tests/test_weekend_features_api.py` var live
API-suiter uden modulmarkør og blev derfor fejlagtigt kørt som unit-tests. De er
nu markeret `integration`. Stale update-rollup-tests sender nu det
`authenticated_device_id`, som produktionskontrakten kræver; sikkerheden blev
ikke omgået for at få tests grønne.

### 10.4 Fortsat åbent

Følgende er ikke dækket af den grønne serverløse baseline og må ikke rapporteres
som bestået:

- De 543 integration/hardware-tests skal yderligere opdeles i isoleret Headend
  integration og serialiseret R&D Edge hardware-E2E.
- T-EDGE-01 fuld `_lab_tick`-tilstandsmaskine og capture-cycle med mocks.
- Backup **restore execution** på frisk/ephemeral installation; dokument-/filtests
  er ikke restore-evidens.
- Thumbnail idempotens/performance ved stor backlog med rigtige billedfiler.
- Playwright/Vitest for login, RBAC, updates, LAB og Open WebUI UI-flows.
- DAST, ekstern port/TLS-scanning og tenant-isolation mod et provisioneret,
  destruerbart testmiljø.
- macOS node-agenten er runtime-verificeret aktiv, men kører som root. Den stale
  z.ai-test er rettet til korrekt plist/procesnavn og afslører nu den reelle
  least-privilege-afvigelse. Collector-privilegier skal opdeles eller begrænses,
  før LaunchDaemon-identiteten ændres.

### 10.5 Supplerende QA

- Alle trackede Pythonfiler: syntax PASS.
- Alle trackede shellscripts: `bash -n` PASS.
- UI TypeScript/Vite production build: PASS.
- ESLint ratchet: PASS, baseline sænket fra 222 til 188 (167 fejl, 21 advarsler).
- Kendt gæld: FastAPI `on_event`- og Pydantic v1-config warnings samt stor UI-chunk.

---

## 9. MANGLENDE TESTS — DEFINERET (NY, 2026-07-15)

Konkret, prioriteret liste over tests der mangler, med formål og hvor de hører hjemme. Rækkefølgen følger risiko (jf. `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md`). Alle nye tests bør være **unit/kontrakt** (server-løse) med mindre andet er noteret, så de kan gate i CI.

### 9.1 P0 — Sikkerheds-assurance (lukker fejlklasser, ikke kun enkeltfund)

| ID | Test | Formål | Fil (forslag) |
|----|------|--------|---------------|
| **T-SEC-01** | **Route-auth sweep** (K1) | Iterér `app.routes`; fejl hvis et endpoint mangler auth-dependency. Allowlist: `/api/health`, `/api/auth/login`, `/api/auth/verify-mfa`, enrollment, `/api/ai/vocabulary/translations` (efter R24). **Havde fanget SEC-001, R15 og R22.** | `headend/tests/test_route_auth_coverage.py` |
| **T-SEC-02** | vocabulary/review auth-regression | Bekræft at `/api/ai/vocabulary/*` (muterende) og `/api/review/escalation/approve` giver 401/403 uden admin+MFA-session (regressionsvagt for R22) | `headend/tests/test_ai_router_auth.py` |
| **T-SEC-03** | disable-mfa step-up (R25) | Bekræft at `POST /api/auth/disable-mfa` kræver MFA-verificeret session; at `admin` ikke kan nulstille `super_admin`s MFA; at der udstedes SIEM-event | `headend/tests/test_disable_mfa_stepup.py` |
| **T-SEC-04** | CORS/ALLOWED_ORIGIN fail-fast (VPEN-012) | Bekræft at appen nægter at starte i `prod`/`staging` uden eksplicit `ALLOWED_ORIGIN` | `headend/tests/test_cors_config.py` |

### 9.2 P1 — Korrekthed & regressioner fundet i review

| ID | Test | Formål | Fil (forslag) |
|----|------|--------|---------------|
| **T-AI-01** | `get_similar_tag_suggestions` (R23) | Regressionsvagt: kald metoden mod in-memory DB og bekræft at den returnerer grupper uden `TypeError` (buggen der crashede /similar) | `headend/tests/test_tag_repository.py` |
| **T-AI-02** | `/translations` viewer-adgang (R24) | Bekræft at read-only translations-endpoint er tilgængeligt for `viewer` (kunde-UI via `useTagLabels.ts`) efter R24-fix | `headend/tests/test_ai_router_auth.py` |
| **T-UPD-01** | Multi-target rollout-flip | Kontrakttest (server-løs) af `report_update`-rollup: 2+ devices, `scope=site` → status flipper korrekt til deployed/rolled_back (udbygger `test_report_update_rollup.py`; live-varianten er fortsat P1 i R06) | `headend/tests/` |
| **T-EDGE-01** | `_lab_tick` tilstandsmaskine | Enhedstest af LAB-tick uden hardware (mock driver/api): connect-retry → powercycle → critical; frame-push health-check; disable-exit. Fanger regressioner i den 456-linjers funktion | `tests/test_lab_tick.py` |

### 9.3 P1 — Dækning af utestede kernemoduler (fra §1-tabellernes "Gaps")

- **User CRUD** (`PUT/DELETE /api/admin/users/*`) — server-løs kontrakttest med mock DB.
- **Device CRUD + decommission** (`POST/PUT/DELETE /api/admin/devices/*`) — inkl. decommission-midt-i-rollout-gap'et (R06-detalje).
- **Camera CRUD + config-validering** (`POST/DELETE /api/admin/cameras/*`).
- **Ollama-service + AI-fallback** (`ai/ollama_service.py`, `ai/integration.py`, `ai/model_results.py`) — mock HTTP mod `:11434`.
- **SIEM event-persistens** (`siem.py`) — bekræft at security-events (login-fejl, mfa_disabled, debug_mode, agent-lockdown) faktisk persisteres og kan hentes.

### 9.4 P2 — Edge-agent (i dag ~5-8% dækning, systemets svageste område)

- Capture-cyklus (`_do_capture_cycle`, 210 linjer) med mock kamera/relay.
- Store-and-forward buffer (`edge/capture/buffer.py`) — fyld/tøm, disk-fuld, genstart-persistens.
- Update-apply + rollback (`_run_artifact_app_update`/`_run_artifact_os_update`) — signaturverifikation, GPG-fingerprint-match, rollback ved fejl.
- SFTP-upload (`edge/upload/sftp.py`) — kræver `paramiko` i dev-deps (mangler i dag → `test_edge_sftp_config.py` kan ikke collectes).
- HMAC request-signering (`headend_client.py`) — freshness/afvisning af stale credentials.

### 9.5 P2 — UI (i dag 0% automatiseret)

- Vitest/Jest-opsætning + smoke-render af de 4 største sider (Backup 1.980, Updates 1.780, Device 1.681, Lab 1.532 linjer).
- `useTagLabels`-hook: fald tilbage til engelske nøgler ved 403 (relateret R24).
- Typet API-klient genereret fra FastAPI's OpenAPI-skema (fjerner håndskrevne fetch-fejl; se QA-review §4.3).

### 9.6 Hygiejne (blokkerer ren testkørsel)

- Fjern `tests/__pycache__` fra Git.
- Tilføj `paramiko`, `cryptography` til `requirements-dev.txt`.
- `test_api_integration.py::test_headend_reachable` bør skippes (ikke fejles) uden server (§0.5 pkt. 1).

---

### Korrektion til §7 coverage-tal (2026-07-15)

Tallet "26% / 51 testfiler" bør læses med §0.5 in mente: en stor del af `tests/`-filerne er live-integration og bidrager **0% assurance i CI** i deres nuværende form. Reel CI-gate-dækning i dag = 3 filer. Efter T-SEC-01…04 + unit/integration-split vil den **blokerende** dækning stige markant uden at der skrives hundredvis af nye tests — de fleste eksisterende unit-/kontrakttests skal bare gøres CI-kørbare og gated.
