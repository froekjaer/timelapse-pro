# Testevidens 2026-08-03

## Udførte tests

| Kontrol | Resultat | Evidens |
|---|---:|---|
| Python-syntaks | PASS | Alle relevante `headend`, `edge`, `node-agent` og testfiler kompilerede. |
| Python uden integration | PASS | 371 passed, 4 skipped, 544 deselected, 13 warnings, 5,70 s. |
| Release/image/backup/drift-kontrakter | PASS | 39 passed, 0,09 s. |
| UI production build | PASS med advarsler | TypeScript/Vite bestod. Bundle: 1,55 MB / 400 KB gzip. |
| Python dependency-konsistens | FAIL | `google-api-core 2.31.0` kræver `requests >=2.33.0,<3`; installeret er `2.32.3`. |
| Frontend dependency audit | FAIL | Fem advisories: fire high og en moderate. |
| Ruff statisk analyse | FAIL/backlog | 2.103 fund. |
| ESLint gate | FAIL/backlog | 165 errors og 20 warnings. |

## Integrationstests - bevidst ikke kørt

`pytest --collect-only` fandt 919 tests: 544 med markøren `integration` og
375 uden. De 544 er ikke et samlet bevis på fejl; markøren bruges også på
fil- og kontraktchecks. De er ikke kørt, fordi standard
`TIMELAPSE_TEST_BASE_URL` er `http://127.0.0.1:8000`, den aktive Headend,
mens database-fixtures bruger `timelapse_test`.

Før fuld kørsel etableres et isoleret testmiljø med:

1. Egen Headend på separat port, fx `127.0.0.1:8001`.
2. Egen `timelapse_test` PostgreSQL, testbrugere og filstorage.
3. Obligatorisk `TIMELAPSE_TEST_BASE_URL`; testen afviser port 8000.
4. Markører for API-isoleret, hardware, destruktiv og manuel test.

## UI-teststatus

Browseren viste login efter genstart. Ingen adgangskode eller aktiv
testsession blev udledt eller anvendt. Den autentificerede browser-E2E er
derfor ikke registreret PASS. Navigation og produktion-build er analyseret
statisk; fælles hover-hjælp er tilføjet i `Navbar.tsx`.

## Kendte buildadvarsler

- `api/client.ts` importeres baade statisk og dynamisk og kan derfor ikke
  kode-splittes af Vite.
- Hovedbundle overskrider Vites 500 KB guidance.
- FastAPI anvender udfasede `on_event` hooks flere steder.
- Pydantic v2-advarsler forekommer i AI repositories.
