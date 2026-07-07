# P2-01: Refaktorering af headend/main.py
**Version:** 1.0.0  
**Dato:** 2026-07-07  
**Estimat:** 1-2 uger (køres sideløbende med andre opgaver)

---

## Nuværende status

- **Fil størrelse:** 17.045 linjer
- **Funktioner/klasser:** 490
- **API endpoints:** 219
- **Problem:** Monolitisk fil er svær at vedligeholde, teste og navigere

---

## Identifikerede moduler til udtrækning

### 1. Auth/RBAC modul (Priority: HIGH)
**Linjer:** 751-2187 (~1.400 linjer)
- Auth models (User, Role, Permission)
- MFA/TOTP/WebAuthn
- API Token auth
- User CRUD (super_admin only)
- Bootstrap & Zero-touch Enrollment
- Password policy

**Target fil:** `headend/auth.py` + `headend/rbac.py`

### 2. Update flow modul (Priority: HIGH)
**Linjer:** 4762-9712 (~5.000 linjer)
- Update styrring
- Update job management
- Artifact builder
- OS bundle builder
- Provision package
- Update deployment til edge

**Target fil:** `headend/update_flow.py`

### 3. AI/Batch modul (Priority: MEDIUM)
**Linjer:** 11765-17045 (~5.300 linjer)
- AI batch processing
- Gemini integration
- Ollama integration
- Tag generation
- AI operations scan

**Target fil:** `headend/ai_batch.py`

### 4. Capture management modul (Priority: MEDIUM)
**Linjer:** 3803-4235 (~400 linjer)
- Capture endpoints
- Capture queries
- Capture permissions
- Capture quality scoring

**Target fil:** `headend/captures.py`

### 5. Backup modul (Priority: MEDIUM)
**Linjer:** 217-12421 (~150 linjer backend logik)
- Backup auto loop
- Backup archive creation
- Backup settings
- Backup status

**Target fil:** `headend/backup.py`

### 6. Retention modul (Priority: LOW — allerede færdig)
**Linjer:** 12067-13418 (~1.350 linjer)
- Retention cleanup loop
- Deletion log
- Retention settings

**Status:** Kan udtrækkes men er relativt selvhævdende

### 7. SIEM/Reports modul (Priority: LOW)
**Linjer:** Spredt gennem filen
- SIEM endpoints
- Report generation
- Compliance evidence

**Target fil:** `headend/siem.py`

---

## Refaktoriseringsstrategi

### Fase 1: Forberedelse (1 dag)
1. Opret modul-struktur:
   ```bash
   mkdir -p headend/modules
   touch headend/modules/__init__.py
   ```

2. Import clean-up i main.py:
   - Gruppér imports
   - Fjern ubrugte imports
   - Sortér alfabetisk

### Fase 2: Trin 1 — Auth modul (2-3 dage)
1. Opret `headend/modules/auth.py`:
   - Flyt Auth models, MFA, TOTP, WebAuthn
   - Opret `def setup_auth_routes(app)` til at registrere endpoints

2. Opret `headend/modules/rbac.py`:
   - Flyt Role, Permission, user CRUD
   - Opret `def setup_rbac_routes(app)`

3. Opdater main.py:
   - Erstat med `from headend.modules.auth import setup_auth_routes`
   - Kald `setup_auth_routes(app)` efter app init

### Fase 3: Trin 2 — Capture modul (1 dag)
1. Opret `headend/modules/captures.py`
2. Flyt capture endpoints og hjælper funktioner
3. Opret `def setup_capture_routes(app)`

### Fase 4: Trin 3 — Backup modul (1 dag)
1. Opret `headend/modules/backup.py`
2. Flyt backup loop, functions, endpoints
3. Opret `def setup_backup_routes(app)`

### Fase 5: Trin 4 — Update flow modul (3-4 dage)
1. Opret `headend/modules/update_flow.py`
2. Flyt update styrring, jobs, artifacts, provisioning
3. Opret `def setup_update_routes(app)`

### Fase 6: Trin 5 — AI/Batch modul (3-4 dage)
1. Opret `headend/modules/ai_batch.py`
2. Flyt AI batch, Gemini, Ollama, tag generation
3. Opret `def setup_ai_routes(app)`

### Fase 7: Trin 6 — SIEM/Reports modul (2 dage)
1. Opret `headend/modules/siem.py`
2. Flyt SIEM endpoints, report generation
3. Opret `def setup_siem_routes(app)`

---

## Teststrategi

For hver modul udtrækning:
1. Kør eksisterende tests før udtrækning
2. Udfør udtrækning
3. Kør tests igen og sikr ingen regressions
4. Kør: `pytest tests/ -v -k "module_navn"`

---

## Risici

1. **Import cyklusser:** Vær forsigtig med imports mellem moduler
2. **Database sessions:** Sørg for at Session håndteres korrekt
3. **Global state:** Minimér brug af globale variabler
4. **Backwards kompatibilitet:** API endpoints må ikke ændre signature

---

## Succeskriterier

- [ ] main.py under 5.000 linjer
- [ ] Alle moduler kan importeres uafhængigt
- [ ] Alle tests passerer
- [ ] Ingen backwards inkompatible ændringer
- [ ] Dokumentation opdateret

---

## Næste skridt (nu)

Da dette er en stor opgave, foreslår jeg:
1. Start med **Fase 2: Trin 1 (Auth modul)** som pilot
2. Hvis det går godt, fortsæt med Capture og Backup moduler
3. Update og AI moduler kræver mere tid og bør gøres senere

**Alternativt:** Fokusér på mindre forbedringer nu:
1. Import clean-up (kan gøres på 1 time)
2. Tilføj sektion kommentarer for bedre navigation
3. Opdater task list med små, overskuelige del-opgaver

---

## Referencer

- `headend/main.py` — 17.045 linjer
- `tests/` — eksisterende test suite
- `PRIORITIZED_BACKLOG.md` — P2-01
