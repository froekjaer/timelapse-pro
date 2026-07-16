# Incident: pytest ramte Headend driftsdatabase

**Opdaget:** 2026-07-16 02:00 CEST

**Hændelsestidspunkt:** 2026-07-15 ca. 14:25 CEST

**Miljø:** R&D Headend (Mac mini), PostgreSQL `timelapse_db`

**Status:** Gendannet og permanent testspærre implementeret

## Effekt

`users`, `devices`, `captures`, kunder og sites blev erstattet/ryddet af test-fixtures.
Symptomet var samtidig `401` for Peter-login, Headend node-agent og Edge
`TL-C87FF9587CA0`. Backend og nginx var oppe (`/health` returnerede 200).

## Root cause

Legacy Headend-tests valgte deres testdatabase med:

```python
os.environ.setdefault("DATABASE_URL", "...")
```

Driftsmiljøet eksporterede allerede
`DATABASE_URL=postgresql://timelapse@localhost/timelapse_db`. `setdefault()`
ændrede derfor intet. Test-fixtures kørte efterfølgende cleanup med delete på alle
SQLAlchemy-tabeller i driftsdatabasen. De eneste resterende brugere var testbrugerne
`viewer1` og `viewer`, oprettet 15. juli kl. 14:25.

## Gendannelse og evidens

Backup `/Volumes/data-fast/backup/timelapse-backup-headend-20260714_200239.tar.gz`
blev først indlæst i en isoleret verifikationsdatabase. Verificeret indhold:

- 9 brugere, inkl. aktiv `peter`/`admin` som `super_admin`
- 10 devices, inkl. `TL-C87FF9587CA0` og Headend node-agent
- 29.061 captures
- 5 kunder og 4 sites

Databaserne blev derefter skiftet ved rename. Den ramte database er bevaret som
`timelapse_db_corrupt_20260716`; ingen destruktiv drop blev udført. Efter genstart:

- `/health`: HTTP 200
- Headend SIEM/inventory: HTTP 200
- Edge site-look/config poll: HTTP 200
- Driftsdata efter isoleret regressionstest: 9 brugere, 10 devices, 29.061 captures

## Permanente kontroller

1. `headend/database.py` afviser import under pytest, hvis URL ender på
   `/timelapse_db`. En override kræver en eksplicit, faresignal-værdi og må ikke
   anvendes i normal QA.
2. `headend/tests/conftest.py` tvinger alle Headend-tests over på PostgreSQL
   `timelapse_test` før testmoduler importeres.
3. `timelapse_test` er oprettet med `timelapse` som ejer.
4. Regressionstests kontrollerer begge sikkerhedsbarrierer.
5. Beviskørsel: 30 tests bestod; driftsdatabasens rækkeantal var uændret bagefter.

## Opfølgning

- CI og alle lokale testkommandoer skal sætte `TIMELAPSE_TEST_DATABASE_URL`.
- Testsetup må aldrig bruge `setdefault()` til en sikkerhedsgrænse.
- Backup-restore drill skal fremover kontrollere rækkeantal, identiteter og aktive
  device credentials før promotion.
- Karantænedatabasen må først slettes efter Peters accept og en afsluttet
  efteranalyse af eventuelle data mellem backup og hændelse.
