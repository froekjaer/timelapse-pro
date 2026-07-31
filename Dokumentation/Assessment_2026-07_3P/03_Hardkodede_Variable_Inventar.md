# 03 — Hardkodede Variable: Inventar mod konfigurationsreglen

**Reglen (Peters krav):** Alle variable skal kunne ændres i UI'en og gemmes i databasen. Eneste undtagelse: opstartsparametre, der parallelt står i `.env`.

**Metode:** Fuld sweep for IP'er, porte, domæner, filsystemstier og magiske defaults i `headend/` og `edge/` (126 forekomster i alt, ekskl. tests/kommentarer); krydsholdt mod settings-helperen (`setting(db, …)`, 53 brug i main) og env-inventaret.

## 3.1 Overtrædelser der bør flyttes til DB-settings + UI (**Mellem**)

| # | Evidens | Værdi | Vurdering |
|---|---|---|---|
| H-01 | `headend/tools/backfill_capture_metadata.py:22` | `CANONICAL_BASE = /Volumes/data-fast/timelapse-incoming/canonical-images` | Modul-konstant uden DB-opslag; øvrige tools bruger korrekt `setting(db,"sftp_base",…)` — inkonsistent |
| H-02 | `headend/main.py:14966-14967` | To hardkodede edge-image-artefaktstier (`/Volumes/data-fast/...`) | Skal være settings (`edge_image_dirs`) — prod-serveren har næppe samme volume-layout |
| H-03 | `headend/itim.py:304,328,359` | `127.0.0.1:<port>`-health-URL'er + storage-fallbackstier | Porte findes delvist i settings; fallbacks omgår dem |
| H-04 | `headend/main.py:5713,5719` | `/opt/homebrew/opt/postgresql@17/bin/pg_isready` | Homebrew-sti hardkodet → brækker på enhver ikke-Mac/anden pg-version; skal være setting med PATH-fallback |
| H-05 | `headend/main.py:5867,5954,17672,17701` | `127.0.0.1:11434` (Ollama), `:8080`, `:8000` fallbacks | `OLLAMA_URL` findes som env — fallback bør læse settings, ikke konstant |
| H-06 | `headend/main.py:18339` | OpenAPI `servers: http://127.0.0.1:8000` | Kosmetisk, men forvirrende i prod-docs |
| H-07 | `edge/utils/database.py` + capture-loop | Interval-/retry-defaults spredt som konstanter | Edge får config fra signeret hierarki — konstanterne bør være defaults i config-skemaet, ikke i koden |

## 3.2 Env-variabler der reelt er driftsindstillinger (bør til DB/UI, jf. reglen) (**Mellem**)

Fra env-inventaret (headend): `UPLOAD_SLOT_WINDOW_SECONDS`, `UPLOAD_SLOT_MAX_PENDING_PER_WINDOW`, `UPLOAD_SLOT_ENFORCED`, `UPLOAD_SLOT_CYCLE_SECONDS`, `TIMELAPSE_DEBUG_MODE_MAX_HOURS`, `TIMELAPSE_BACKFILL_ALLOW_DEEP_SCAN`. Det er tunbare driftsparametre, ikke opstartsparametre — de hører hjemme i Settings-UI'et med audit-log på ændring.

## 3.3 Legitim .env (opstartsparametre — OK jf. undtagelsen)

`DATABASE_URL`, `JWT_SECRET`, `TIMELAPSE_ENV`, `BASE_URL`/`TIMELAPSE_PUBLIC_URL`, `COOKIE_SECURE`, `GOOGLE_APPLICATION_CREDENTIALS`/`GEMINI_API_KEY` (secrets), `WEBAUTHN_RP_*`, `SFTP_BASE` (bootstrap før DB findes), tunnel-parametre (`TIMELAPSE_TUNNEL_*`), `FFMPEG_PATH`. Disse kan ikke ligge i DB (hønen-og-ægget eller secret-karakter). **Anbefaling:** dokumentér præcis denne liste som "authoritative .env-kontrakt" i Installationsguiden, og lad `/api/health` rapportere hvilke der er sat (uden værdier).

## 3.4 Anbefalet mekanik (så reglen kan håndhæves maskinelt)

1. Én settings-adapter (jf. TPA-15) med registreret nøgle, type, default, kategori og "kræver genstart"-flag — UI'et genererer Settings-siden fra registret i stedet for håndbyggede felter.
2. CI-gate: grep-sweep (som denne assessments) der fejler ved nye `/Volumes/`, `127.0.0.1`, homebrew-stier m.v. uden for whitelisten (`tests/` + dokumenterede bootstrap-steder). Baseline = de 126 nuværende; ratchet nedad ligesom main.py-loftet.
3. Alle settings-ændringer skriver audit-event (findes allerede for nogle; gør det ensartet).
