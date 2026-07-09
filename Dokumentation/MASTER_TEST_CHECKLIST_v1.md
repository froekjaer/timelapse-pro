# TimeLapse Pro — Master Test Checklist

**Dato:** 2026-07-08  
**Version:** 1.0  
**Scope:** Komplet system audit for at fange alle småfejl og mangler

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
| Headend Backend | 73 | 23 | 31% |
| Edge Agent | 61 | 2 | 3% |
| React UI | 31 | 0 | 0% |
| Database | 28 | 17 | 61% |
| **TOTAL** | **193** | **42** | **22%** |

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

**Status:** 🟡 **22% overall coverage — P0 features mostly covered**

**Next Steps:**
1. Complete Phase 1 tests (P0)
2. Manual UI verification
3. Create automated UI test suite
4. Increase edge test coverage

---

*Signed off: Peter (TimeLapse Pro) — 2026-07-08*
