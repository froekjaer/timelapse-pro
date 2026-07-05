# TimeLapse Pro

Dansk timelapse-kamera-SaaS: edge-agenter på kamera-noder (Orange Pi + Nikon) uploader
billeder til en central headend (FastAPI + PostgreSQL), som håndterer CMDB, AI-tagging,
bruger/kunde-administration, RBAC, opdateringer og en React-baseret admin-UI.

**Status:** LAB/pre-production. Endnu ikke klar til fuld Internet-eksponering — se
`Dokumentation/GO_LIVE_CHECKLIST_v10.md` for gate-status og `Dokumentation/RISK_ASSESSMENT_v10.md`
for åbne risici.

## Dokumentation først

All autoritativ dokumentation ligger i [`Dokumentation/`](Dokumentation/). Start altid med
[`Dokumentation/00_START_HER.md`](Dokumentation/00_START_HER.md) — det er master-indekset og
peger på den seneste version af hvert dokument (`*_v10.md`), levende arbejdsdokumenter
(`HANDOVER_LOG.md`, `SYSTEM_HEALTH_REGISTER.md` m.fl.) og risiko-/kravregistre. Denne README
dækker kun det tekniske "kom i gang" — ikke arkitektur, sikkerhed eller drift.

## Struktur

| Mappe | Indhold |
|---|---|
| `headend/` | FastAPI-backend (Python) — API, CMDB, AI-tagging, updates, auth/RBAC. PostgreSQL i produktion, kan køre mod SQLite lokalt via `DATABASE_URL` til test. |
| `edge/` | Edge-agent (Python) til kamera-noder — capture, upload, HAL, CMDB-rapportering, HMAC-signering, self-update. |
| `timelapse-ui/` | Admin/kunde-UI (React 19 + TypeScript + Vite). |
| `node-agent/` | Let monitorerings-/health-agent til node-collectors. |
| `website/` | Statisk public informationssite. |
| `deploy/` | LaunchAgent/-Daemon-manifester og deployment-scripts til Mac Mini/Orange Pi. |
| `tests/` | Repo-niveau integrations-/API-/edge-QA-tests (pytest). |
| `Dokumentation/` | Al SABSA/ISO 27001/IEC 62443/CRA/GDPR-relevant dokumentation — autoritativ kilde. |

## Kom i gang lokalt

### Headend (API)

```bash
cd headend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Produktion bruger PostgreSQL; til lokal udvikling/test kan SQLite bruges via:
export DATABASE_URL="sqlite:////tmp/timelapse_dev.db"
uvicorn main:app --reload --port 8000
```

Se `Dokumentation/Installationsguide_v10.md` (Del A) for fuld produktionsopsætning
(PostgreSQL, nginx, LaunchDaemons, secrets).

### Admin-UI

```bash
cd timelapse-ui
npm install
npm run dev       # udviklingsserver med HMR
npm run build     # tsc -b && vite build
npm run lint:gate # ESLint ratchet-gate — fejler kun ved flere problemer end baseline
```

### Edge-agent

Se `Dokumentation/Installationsguide_v10.md` (Del B/C) for provisionering af en fysisk
Orange Pi + Nikon-node. Kræver ikke npm/Node — ren Python (`edge/requirements.txt`).

## Test

```bash
# Repo-niveau integrations-/API-tests
pytest tests/

# Headend contract-tests (kræver fastapi/sqlalchemy/slowapi/python-jose/bcrypt/passlib/
# python-multipart/python-dotenv/pytest i et venv — kører mod midlertidig SQLite, ingen
# live Postgres nødvendig)
cd headend && pytest tests/ -v

# Frontend
cd timelapse-ui && npm run lint:gate
```

CI kører via `.github/workflows/ci.yml`.

## Sikkerhed og compliance

Projektet følger SABSA-metodikken og er bevidst om ISO 27001, IEC 62443, CRA, GDPR, NIS2 og
AI Act. Al risikovurdering, trusselsmodellering og gate-status føres i `Dokumentation/`
(`RISK_ASSESSMENT_v10.md`, `TimeLapse_Security_Compliance_v10.md`,
`SABSA_Architecture_v10.md`). Rapportér ikke sikkerhedshuller offentligt — se
`Dokumentation/HANDOVER_LOG.md`-konventionen for hvordan Claude/Codex/Peter koordinerer
ændringer i dette repo.
