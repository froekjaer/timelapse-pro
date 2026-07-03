# Overdragelse — Claude-session 2026-07-02 → ny session

**Formål:** Give en ny session (uanset model) alt nødvendigt for at fortsætte de aktive tråde. Læs **`00_START_HER.md` først** for projektkontekst (topologi, principper, dokument-map). Dette dokument dækker de *levende* tråde fra denne session.

---

## ⚠️ 0. VIGTIGST — uncommittet arbejdstræ + Codex V11

- **Codex-opdatering 2026-07-03:** Det relevante arbejdstræ er nu committet før sessionskift:
  - `9340aed docs: consolidate v10 handover and operations references`
  - `d7a952d chore: checkpoint code operations and edge work`
  Lokale caches/secrets/artifacts ligger stadig bevidst ucommittet: `.base_image_cache/`,
  `.claude_proxy/`, `artifacts/`, `headend/.webui_secret_key`, `dokumentation.tar.gz`,
  `timelapse-pro-doc.gz` og en LibreOffice lock-fil.
- Historisk note fra før Codex' commit: der lå **meget uncommittet** i git-arbejdstræet: hele dokument-konsolideringen (v10-filer, flytninger til `Gamle versioner/`, nye undermapper) viste sig som mange `D` (slettede originaler) + untracked nye filer, PLUS kodefixene nedenfor. Det relevante er nu committet i `9340aed` og `d7a952d`.
- **Codex har committet "V11 documentation"** (commits `260122c`, `99bff9b`). Min dokument-konsolidering var **v10** og er nu committet i `9340aed`. **Reconcilér v10 ↔ V11 med Codex før en egentlig release/merge** — koordinér via `HANDOVER_Claude_Codex_arbejdsdeling.md`, så vi ikke laver to spor. Afklar med Peter/Codex om vi lander på v10- eller v11-navngivning.
- **Codex-afklaring 2026-07-03:** `260122c` og `99bff9b` er bekræftet committet på `codex/edge-npu-qa`. De er ikke en komplet `*_v11.md` dokumentpakke, men to Codex-review/valideringsnotater til v11-sporet. Derfor bør den nye session fortsat behandle Claudes v10-konsolidering som det store uncommitted dokument-spor og først vælge v10/v11-navngivning bevidst med Peter.
- Princip: **rør ikke Codex' auth/MFA-kode** (se §4).

## 1. Kodeændringer denne session (fil → ændring → deploy-status)

| Fil | Ændring | Deployet? |
|---|---|---|
| `headend/importer.py` | Fix: `_sftp_base_path(db)` i stedet for fjernet `from main import SFTP_BASE` (**dette var 500-fejlen på ALLE imports** — "The string did not match the expected pattern" i Safari) | ✅ Live (headend genstartet) |
| `headend/importer.py` | `local_path` adgangsfejl → klar `403` (macOS TCC: ~/Downloads/Skrivebord/Dokumenter er beskyttede) | ✅ Live |
| `headend/importer.py` | `/api/import/status` returnerer nu `job_id` (ellers frøs UI-progressbaren på `/status/undefined`) | ⚠️ Kræver frisk genstart hvis ikke med i sidste kickstart |
| `headend/importer.py` | Inline thumbnail-generering ved import (`.headend-thumbs/`, 320×180) — så nye imports ikke er langsomme | ⚠️ Gælder kun NYE imports; kræver genstart |
| `headend/importer.py` | `Device` sætter nu `customer_id` (ellers opløser AI-strategien til GLOBAL i stedet for kunde) | ⚠️ Gælder kun NYE imports; kræver genstart |
| `headend/main.py` | Batch-finalize (`_finalize_ai_batch_job`) bevarer edge-QA under `edge_ai` | ✅ Live |
| `headend/ai/ai_batch_submit.py` | `--since`/`--until` + auto-resolve `sftp_base` fra DB (env var ikke længere nødvendig) | CLI (bruger disk-kode) |
| `headend/tools/backfill_thumbnails.py` | Springer `.quarantine/` over | Klar (frisk proces) |
| `timelapse-ui/src/pages/ImportPage.tsx` | Robust svar-parsing (viser rigtig fejl, ikke Safari-tekst) | ✅ `npm run build` kørt 2026-07-03 |
| `deploy/nginx/timelapse.froekjaer.dk.conf` | Ny `location /api/import/` med `client_max_body_size 1024m` | ✅ Påført live `/opt/homebrew/etc/nginx/nginx.conf`, `nginx -t` grøn, nginx kickstartet 2026-07-03 |

**Opdateret drift 2026-07-03:** headend kører nu som system-LaunchDaemon. Brug
`sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend` for frisk genstart.
Frisk headend-genstart er kørt 2026-07-03 og `/api/health` svarede `200`.

## 2. Åbne handlinger (deploy/kør)

1. ~~`cd ~/projects/timelapse-pro/timelapse-ui && npm run build`~~ — kørt 2026-07-03.
2. ~~Påfør nginx `/api/import/`-body-size på live config + `nginx -t && nginx -s reload`~~ — påført live og nginx kickstartet 2026-07-03.
3. ~~Frisk headend-genstart (se §1)~~ — kørt via system-LaunchDaemon 2026-07-03.
4. **Gemini-backlog-batch** (edge-QA-billeder uden Gemini siden 29/6 12:00) — aldrig bekræftet kørt:
   ```bash
   ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/ai_batch_submit.py --since "2026-06-29 12:00" --no-context --dry-run
   # derefter uden --dry-run
   ```
   Codex tjek 2026-07-03: count = **22**. Dry-run er kørt og viser 22 billeder, 0 manglende filer,
   1 batch-job, men intet indsendt. Start ikke uden Peters accept, da det sender et rigtigt
   Gemini/Vertex batch-job.
5. Commit arbejdstræet efter v10↔V11-reconciliation (§0).

## 3. Aktiv test i gang — Ollama på Travbyen Kamera 2

- **Device:** `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_2` (importeret 2026-07-02, 1129 billeder). `customer_id` er sat til Kirkbi (`687de00d-8400-47d0-bab4-f29e17dd38bf`), så AI-strategien opløser til Kirkbi = `local_only qwen2.5vl:7b`.
- **Status:** post-processing har køet alle; worker'en tømmer køen med Ollama (serialiseret, ~sekunder pr. billede → op mod en time+). Følg: `curl -s http://127.0.0.1:8000/api/ai/status | python3 -m json.tool` (`queue_size`↓, `worker_stats.completed`↑).
- **FÆLDE:** indstillingen `peter-vil-gerne-lege-med-ollama` i `system_settings` = "Open WebUI-prioritet". Når `true` **pauser** den auto-tagging-worker'en helt (køen tømmes ikke). Skal være `false` under tagging:
  `psql timelapse_db -c "UPDATE system_settings SET value='false' WHERE key='peter-vil-gerne-lege-med-ollama';"`
- AI-strategier (pr. 2026-07-02): global = `local_only qwen2.5vl:7b`; Kirkbi/Byggros/Vejle = `local_only`; Frøkjær = `cloud_only`.

## 4. MFA — landet (Codex), Claude/Codex fritaget

MFA er nu **policy-drevet og enforced** for `super_admin` + `admin` (TOTP). Se memory + `RBAC_Remote_Operational_v10.md` §3, `RISK_ASSESSMENT_v10.md` (R02), `KRAVREGISTER_og_STATUS_v10.md` (UI-009/SEC-008), `GO_LIVE_CHECKLIST_v10.md` (C-07) — alle opdateret 2026-07-02. Claude/Codex-testkonti er på `mfa_exempt_usernames`. **Rør ikke auth/MFA-koden.**

## 5. Længere-sigtet åben (fra tidligere)

- **Tag-søgnings-virtualisering (#5):** gør "Vis alle" hurtig i Tag-søgning (resultat-grid er ikke-virtualiseret/variabel højde) og forén med samme muligheder som galleriet (klik→fuldt billede, metadata, slet). Peter har bekræftet ønsket.

## 6. Kernefakta (kort — resten i 00_START_HER.md)

Repo `~/projects/timelapse-pro` (= `/Volumes/data-fast/peter-home/projects/timelapse-pro`). Headend: FastAPI `127.0.0.1:8000`, PostgreSQL `timelapse_db`, launchd `dk.froekjaer.timelapse-headend`, venv `~/.venvs/timelapse-headend`. Storage `/Volumes/data-fast`; billed-rod `/Volumes/data-fast/timelapse-incoming/canonical-images`. Ollama `127.0.0.1:11434`. Aktiv edge `TL-C87FF9587CA0`. Principper: additiv + flag-guarded, aldrig hard-delete, dobbelttjek før udførelse.
