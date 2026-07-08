# 📋 TESTLISTE — Weekend 5-7 Juli 2026

**Dato:** 2026-07-07
**Status:** Klar til test
**Session:** Sammen gennemgang med Peter

---

## 🚀 QUICK START

```bash
# 1. Start headend (hvis ikke kører)
cd /Volumes/data-fast/peter-home/projects/timelapse-pro/headend
source venv/bin/activate
python main.py

# 2. Kør automatiseret API test (i ny terminal)
cd /Volumes/data-fast/peter-home/projects/timelapse-pro
python tests/test_weekend_features_api.py --verbose

# 3. Åbn UI og test manuelt
# https://timelapse-pro-staging.kirkbi.local
```

---

## 📊 TEST STATUS OVERSKRIG

| Feature | API Tests | UI Tests | Prioritet |
|---------|-----------|----------|-----------|
| **P2-03 GDPR Redaction** | ✅ Script | ⬜ Manual | HØJ |
| **P0-05 Retention Policy** | ✅ Script | ⬜ Manual | KRITISK |
| **Drift-Detection** | ✅ Script | ⬜ Manual | HØJ |
| **M-05 Agent-Lockdown** | ✅ Script | N/A | SIKKERHED |
| **Update UI Scopes** | ✅ Script | ⬜ Manual | MEDIUM |

---

## 🎯 MANUELLE UI TESTS

### GDPR Redaction (P2-03)
1. **Navbar:**
   - [ ] Admin dropdown → "GDPR Sløring" (ikke "GDPR Redaction")
   - [ ] Side titel: "GDPR Slørings-workflow"

2. **Dansk tekst:**
   - [ ] "Analyser", "Slør", "Godkend" knapper
   - [ ] "Er du sikker på at du vil sløre dette billede?" confirm dialog
   - [ ] Fejlbeskeder: "Kunne ikke indlæse afventende billeder"
   - [ ] Status labels: "Afventer", "Analyseret (OK)", "GDPR fundet", "Sløret"

3. **Workflow:**
   - [ ] Vælg billede → klik "Analyser" → viser detektioner
   - [ ] Billede med PII → "GDPR fundet" → "Slør" → "Godkend"
   - [ ] Filtrer: "Kun GDPR-detektioner" / "Afventer analyse"

### Retention Policy (P0-05)
1. **Global:**
   - [ ] Admin → Retention → "Global retention (dage)" → gem
   - [ ] Reload → værdi husket

2. **Per kamera:**
   - [ ] Enheder → rediger kamera → "Retention (dage)" → gem
   - [ ] Forskellige kameraer kan have forskellige værdier

### Drift-Detection
1. **Config hierarki:**
   - [ ] Admin → Drift → Config viser global/device/customer/site
   - [ ] Dropdowns virker korrekt

### Update UI
1. **Scopes:**
   - [ ] Admin → Opdateringer → scopes vises korrekt

---

## 🤖 AUTOMATISEREDE API TESTS

Kør scriptet og tjek output:

```bash
python tests/test_weekend_features_api.py --verbose
```

Forventet output:
```
✅ [1.1] GET /api/redaction/pending: API returnerer X billeder...
✅ [1.2] GET /api/redaction/status/{id}: Capture X status: pending...
✅ [1.3] POST /api/redaction/analyze/{id}: Analyse færdig: X ansigter...
✅ [2.1] GET /api/admin/config (retention_days): Global retention: 365 dage
✅ [2.2] Kamera retention_days felt: Retention field tjekket
✅ [3.1] GET /api/admin/drift-status: Drift detection: aktiveret/deaktiveret
✅ [3.2] Config hierarki: Config hierarki: OK
✅ [4.1] Agent login rejection: Agent login korrekt afvist
✅ [5.1] GET /api/updates: Update data: OK
✅ [6.1] GET /api/admin/thumbnail-backlog: Thumbnail backlog: X billeder
✅ [7.1] v17 Redaction kolonner: Database v17 redaction kolonner OK
✅ [7.2] v15 Retention kolonner: Database v15 retention: OK
✅ [7.3] v16 wb_cast_strength kolonne: Database v16 wb_cast_strength: OK
```

---

## 🗄️ DATABASE MIGRATION CHECKS

Før testing — bekræft migrations er kørt:

```bash
# v15 Retention
psql -U timelapse -d timelapse_db -c "\d cameras" | grep retention_days

# v16 wb_cast_strength
psql -U timelapse -d timelapse_db -c "\d captures" | grep wb_cast_strength

# v17 Redaction
psql -U timelapse -d timelapse_db -c "SELECT unnest(enum_range(NULL::redaction_status_enum));"
```

Forventet resultat:
- `retention_days | integer`
- `wb_cast_strength | double precision`
- `pending`, `analyzed`, `detected`, `redacted`, `skipped`

---

## 📝 NOTER TIL MORGEN

1. **Start med migrations** — hvis disse mangler fejler alt andet
2. **Kør API script først** — hurtig feedback på backend
3. **UI test sidst** — kræver browser og klik
4. **Noter fejl** — opdater testlisten med ❌ når noget fejler

---

## 🔗 REFERENCER

- **Test script:** `tests/test_weekend_features_api.py`
- **Backlog:** `PRIORITIZED_BACKLOG.md` (sektion "Test Status")
- **Migrations:** `headend/migrations/v15_*.sql`, `headend/migrations/v17_*.sql`
