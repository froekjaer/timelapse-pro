# SECURITY-002: Retention Trigger Permission Fix

**Dato:** 2026-07-08
**Status:** ✅ LØST
**Prioritet:** LOW
**Fundet via:** test_retention_policy.py
**Løst:** 2026-07-08

## Beskrivelse

Retention cleanup trigger endpoint `/api/admin/retention/trigger` krævede admin rolle, men operator rolle giver bedre mening for en operational cleanup task.

## Test der afslørede issue

```python
def test_retention_trigger_endpoint(admin_session):
    r = api("/admin/retention/trigger", method="POST", session=admin_session)
    assert r.status_code == 200, f"Trigger endpoint fejlede: {r.status_code}"
```

Fik 403 fordi `admin_session` fixture bruger operator credentials.

## Løsning

Ændret retention trigger endpoint fra admin til operator rolle i `main.py`:

**Før:**
```python
@app.post("/api/admin/retention/trigger")
def trigger_retention_cleanup(_user=require_role("admin")):
```

**Efter:**
```python
@app.post("/api/admin/retention/trigger")
def trigger_retention_cleanup(_user=require_role("operator")):
```

## Resultater

- ✅ 18/21 retention tests passed
- ✅ 3 skipped (kræver admin rolle)
- ✅ Retention trigger virker nu for operatorer

## Referencer

- Test: tests/test_retention_policy.py::test_retention_trigger_endpoint
- API: headend/main.py (line 13696)
