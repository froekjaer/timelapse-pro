# Backup/restore-test procedure (v1)

**Dato:** 2026-07-04 (nat) · **Lukker (delvist):** R09/E-02 i `RISK_ASSESSMENT_v10.md` og
`GO_LIVE_CHECKLIST_v10.md`
**Status:** Procedure klar til brug, **IKKE eksekveret** — kræver kørsel på Mac Mini'en
(jeg kan ikke nå Postgres/NAS/billedfilerne fra min sandbox).

## Hvorfor dette dokument

`_run_backup_archive()` er i nat udvidet til rent faktisk at inkludere billeder (se
`HANDOVER_LOG.md` 2026-07-04 nat, "KRITISK backup-hul lukket"). En backup, der aldrig er
afprøvet med en reel gendannelse, er ikke en pålidelig backup — kun en antagelse om en. Denne
procedure er designet til at kunne køres **uden at røre produktionsdata eller -databasen**,
så den er lav-risiko at eksekvere selv tæt på et go-live-vindue.

## Forudsætninger

- Et frisk backup-arkiv findes (`timelapse-backup-headend-<dato>.tar.gz`) — kør evt. en manuel
  backup fra UI'en (Backup-siden → "Kør backup nu") først, med "Inkludér billeder" slået til.
- PostgreSQL-klient (`psql`, `pg_restore`) er tilgængelig lokalt (allerede tilfældet, da
  `pg_dump` bruges til at lave backuppen).
- Et **scratch-miljø** — IKKE produktions-Postgres. To muligheder, i prioriteret rækkefølge:
  1. En midlertidig database på samme Postgres-server, fx `timelapse_db_restoretest`
     (hurtigst, ingen ekstra software).
  2. Et helt separat Postgres-instance (Docker container) hvis I vil teste "fra bar metal".

## Trin 1 — Pak arkivet ud til et scratch-område

```bash
mkdir -p /tmp/restoretest-$(date +%Y%m%d)
cd /tmp/restoretest-$(date +%Y%m%d)
tar xzf /Volumes/Backup/timelapse-backup-headend-<dato>.tar.gz
ls -la timelapse-backup-headend-<dato>/
```

Forventet indhold: `database/timelapse_db_<dato>.sql`, `configs/` (MANIFEST.json + kopierede
config-filer), `SYSTEMINFO.txt`. Bekræft filstørrelser er fornuftige (SQL-filen bør være
mindst nogle MB givet ~26.000+ captures).

## Trin 2 — Gendan databasen til en SCRATCH-database (ikke produktion)

```bash
createdb -U timelapse timelapse_db_restoretest
psql -U timelapse -d timelapse_db_restoretest -f database/timelapse_db_<dato>.sql
```

Verificér gendannelsen uden at røre produktionsdatabasen:

```bash
psql -U timelapse -d timelapse_db_restoretest -c "SELECT count(*) FROM captures;"
psql -U timelapse -d timelapse_db_restoretest -c "SELECT count(*) FROM devices;"
psql -U timelapse -d timelapse_db_restoretest -c "SELECT max(created_at) FROM captures;"
```

Sammenlign tallene med produktionsdatabasen (kør samme queries mod `timelapse_db`) — de bør
være tæt på ens (produktion kan have et par nye captures siden backup blev taget, det er
forventet og fint).

**Ryd op bagefter:** `dropdb -U timelapse timelapse_db_restoretest` — lad IKKE en scratch-DB
med samme skema/rettigheder som produktion stå og flyde permanent.

## Trin 3 — Verificér config-delen

```bash
cat configs/MANIFEST.json | python3 -m json.tool
```

Bekræft at listen af `copied`-filer matcher det I forventer (nginx.conf, .env, plists m.v.) —
hvis en fil mangler i listen, betyder det den ikke fandtes på disken ved backup-tidspunktet
(ikke nødvendigvis en fejl i selve backup-koden, men værd at vide).

## Trin 4 — Verificér billed-mirroren (den nye del fra i nat)

Dette er IKKE en del af selve tar.gz'en (bevidst, se begrundelse i koden) — mirroren ligger i
`{base_dir}/timelapse-images-mirror/` ved siden af backup-arkiverne.

```bash
find /Volumes/Backup/timelapse-images-mirror -type f | wc -l
du -sh /Volumes/Backup/timelapse-images-mirror
```

Sammenlign filantallet med det faktiske billedantal i produktion:

```bash
find "$SFTP_BASE" -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) | wc -l
```

De to tal bør være tæt på ens (mirroren er inkrementel — første kørsel kan tage lang tid og
et efterfølgende diff-tjek er den rigtige test af at rsync rent faktisk holder dem i sync).

**Stikprøve på faktiske filer** — åbn 3-5 tilfældige billeder fra mirroren og bekræft de kan
åbnes og ligner det forventede motiv (ikke bare at filstørrelsen er >0 bytes):

```bash
find /Volumes/Backup/timelapse-images-mirror -type f -iname '*.jpg' | shuf -n 5
```

## Trin 5 — Dokumentér resultatet

Udfyld og gem denne blok i `HANDOVER_LOG.md` (eller en dedikeret log, hvis I foretrækker det),
så restore-testen er sporbar til en go-live-beslutning:

```md
### Restore-test udført <dato> af <navn>
- Backup-arkiv testet: timelapse-backup-headend-<dato>.tar.gz
- DB-gendannelse: OK/FEJL, <antal> captures, <antal> devices (sammenlignet med produktion: <diff>)
- Config-gendannelse: OK/FEJL, <antal> filer verificeret
- Billed-mirror: <antal> filer i mirror vs. <antal> i produktion, stikprøve på 5 filer: OK/FEJL
- Samlet tid brugt: <minutter>
- RTO-estimat (tid fra "server død" til "systemet kører igen på ny hardware"): <estimat>
- Konklusion: Go/No-go for at stole på denne backup ved et reelt nedbrud
```

## Hvad denne test IKKE dækker (vær ærlig om det i go-live-vurderingen)

- **Fuld bare-metal-gendannelse** (ny Mac Mini fra scratch, OS-installation, alle
  LaunchDaemons/nginx/Postgres geninstalleret) — denne procedure tester kun data-laget, ikke
  hele infrastruktur-genopbygningen. Et separat "disaster recovery runbook" (ikke skrevet endnu)
  ville dække det fulde scenarie.
- **Off-site-scenariet** (Mac Mini + NAS begge tabt samtidig, fx brand/tyveri) — mirroren og
  arkiverne ligger i nat stadig kun lokalt/på samme NAS som produktionsdata. Uden en ekstern
  kopi (cloud-bucket, anden fysisk lokation) er R09/E-03 fortsat reelt åben, uanset hvor godt
  restore-testen går.
- **RPO under selve billed-mirroringen** — da mirroren er inkrementel og køres på et interval
  (daily/weekly), er der et vindue hvor de allernyeste billeder endnu ikke er i mirroren. Dette
  bør indgå eksplicit i RTO/RPO-dokumentationen (E-07).

## Hvorfor jeg ikke selv har kørt dette i nat

Denne procedure rører rigtig PostgreSQL og et helt (potentielt stort) billedtræ på Mac Mini'en
— infrastruktur jeg ikke har direkte adgang til fra min sandbox. At designe proceduren
grundigt, så I kan køre den trygt og hurtigt, er den rigtige rolle for mig her; selve
udførelsen og den efterfølgende go/no-go-vurdering hører hjemme hos jer, jf.
"dobbelttjekker før du udfører".
