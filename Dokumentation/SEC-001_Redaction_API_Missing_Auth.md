# SECURITY-001: Redaction API Missing Authentication

**Dato:** 2026-07-08
**Status:** ✅ LØST
**Prioritet:** HIGH
**Fundet via:** test_gdpr_redaction.py
**Løst:** 2026-07-08 14:12

## Beskrivelse

`/api/redaction/pending` endpoint kræver IKKE authentication og er offentligt tilgængelig.

## Impact

- Alle kan liste GDPR redaction status uden login
- Potentielt data exposure af redaction workflow
- GDPR compliance risiko

## Test der afslørede issue

```python
def test_redaction_endpoints_require_auth():
    r = requests.get(f"{BASE_URL}/api/redaction/pending")
    # Forventede 401/403 men fik 200
```

## Løsning

Tilføj authentication requirement til redaction API endpoints i `redaction_api.py`:

```python
from fastapi import Depends

# Tilføj auth dependency
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Verificer at brugeren er authenticated."""
    ...

@router.get("/pending", dependencies=[Depends(get_current_user)])
def get_pending_captures(...):
    ...
```

## Lignende endpoints der skal tjekkes

- `/api/redaction/status/{capture_id}`
- `/api/redaction/analyze/{capture_id}`
- `/api/redaction/redact/{capture_id}`
- `/api/redaction/approve/{capture_id}`

## Løsning implementeret

**Ændringer i `headend/redaction_api.py` (v1.0.1 → v1.0.2):**

1. Tilføjet authentication imports:
   ```python
   from jose import JWTError, jwt as _jwt
   from database import SessionLocal, Capture, User
   ```

2. Tilføjet auth dependencies:
   - `get_db()` - database session dependency
   - `get_current_user()` - returnerer user fra cookie eller None
   - `get_required_user()` - kræver authenticated user (kaster 401)

3. Tilføjet `Depends(get_required_user)` til alle endpoints:
   - `GET /api/redaction/pending`
   - `GET /api/redaction/status/{capture_id}`
   - `POST /api/redaction/analyze/{capture_id}`
   - `POST /api/redaction/redact/{capture_id}`
   - `POST /api/redaction/approve/{capture_id}`

**Test resultater:**
- ✅ 21/21 GDPR redaction tests passed
- ✅ Auth test verified: uden auth → 401, med auth → 200

## Referencer

- Test: tests/test_gdpr_redaction.py::test_redaction_endpoints_require_auth
- API: headend/redaction_api.py (v1.0.2)
- Commit: SECURITY-001 fix implemented 2026-07-08
