# Afhjælpningsplan 2026-08-03

## P0 - før produktionsaccept

1. Fjern fælles BT-PAN fabrikshemmelighed og gennemfør kontrolleret migration.
2. Harden OS-bundlebuilder med parameteriseret kørsel, allowlists, least
   privilege, path containment og negative sikkerhedstests.
3. Etabler separat Headend-testmiljø og gør integrationstest fail-closed mod
   aktiv port, database og storage.

## P1 - næste releasecyklus

1. Gør Edge rollback atomisk og manifestverificeret.
2. Konsolider systembackup for PostgreSQL, konfiguration og medier med
   logisk `/data-fast` storage og restoretest.
3. Kræv GPG-signatur for staging/production; hashbinding er kun lab-evidens.
4. Opgrader audit-ramte frontend-afhængigheder i testrelease.
5. Indfør ruff-/ESLint-ratchet for ændret kode og reducer backlog modulvis.

## P2 - løbende kvalitet

1. Flyt API-domæner ud af `headend/main.py` ved hver funktionel ændring.
2. Udfas maskinspecifikke absolute stier fra aktive installere og tests.
3. Fuldfør UI-hjælpetekstmatrix og browser-E2E i isoleret testmiljø.
4. Reducer bundle-størrelse og udskift udfasede FastAPI/Pydantic-mønstre.

## Releasegate

En release kan kun godkendes med ren compile/build, ingen nye lint-/ruff-fund,
relevante unit- og API-isolerede tests, artifact-signatur, SBOM/licenskontrol,
testbevis knyttet til change samt dokumenteret rollback- og restoretest.
