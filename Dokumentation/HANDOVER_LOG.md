# TimeLapse Pro — Handover-log

Kort, kronologisk log til overleveringer mellem Peter, Claude og Codex.

Kanoniske fakta om services/stier/porte ligger stadig i
`SERVICES_OG_DRIFT_kilde_til_sandhed.md`. Denne fil er kun "hvad skete der, hvad skal næste
person vide".

## Skabelon

```md
### Handover YYYY-MM-DD HH:MM — fra <Claude|Codex|Peter> til <Claude|Codex|Peter>
- Hvad er gjort:
- Hvad mangler / næste skridt:
- Kommandoer kørt eller skal køres:
- Forventet/faktisk output:
- Filer rørt:
- Risici / pas på:
```

## Log

### Handover 2026-06-28 10:10 — fra Codex til Claude/Peter
- Hvad er gjort: Edge AI/NPU-sporet er checkpointet på `codex/edge-ai-npu-modes`.
  Orange Pi 4 Pro NPU probe viser `npu_ready=true`; QA-kontrakt, datasetmanifest og
  vendor-binary-krog er tilføjet.
- Hvad mangler / næste skridt: rigtig TimeLapse QA `.nb` model og VIPLite-wrapper
  `/opt/timelapse/bin/edge_qa_viplite`.
- Kommandoer kørt eller skal køres: se `Codex_Edge_AI_NPU_Modes_2026-06-28.md`.
- Forventet/faktisk output: runneren markerer forventeligt `vendor_runtime_binding_not_installed`
  indtil wrapper/model findes.
- Filer rørt: `edge/ai/model_contract.py`, `edge/tools/build_qa_dataset_manifest.py`,
  `edge/tools/edge_qa_npu_runner.py`, UI configfelter, tests og Edge AI-dokumentation.
- Risici / pas på: repoets normale arbejdstræ er beskidt; brug konkrete filer eller separat
  Git-index ved commits.

### Handover 2026-06-28 11:55 — fra Codex til Claude/Peter
- Hvad er gjort: Læst og justeret fælles samarbejdsdokumenter; tilføjet denne handover-log.
- Hvad mangler / næste skridt: hvis Claude ændrer FAQ/driftsvejledning, skal nød-kopien på
  boot-drevet synkroniseres bagefter.
- Kommandoer kørt eller skal køres: `cp Dokumentation/FAQ_og_fejlsøgning.md
  ~/Claude/Projects/Timelaps/FAQ_og_fejlsøgning_NØDKOPI.md`
- Forventet/faktisk output: nød-kopien skal eksistere, så login-/diskfejlsøgning kan læses når
  `data-fast` er ustabil.
- Filer rørt: `FAQ_og_fejlsøgning.md`, `HANDOVER_Claude_Codex_arbejdsdeling.md`,
  `SERVICES_OG_DRIFT_kilde_til_sandhed.md`, `HANDOVER_LOG.md`.
- Risici / pas på: driftsfacts skal fortsat kun have én sandhed i services-dokumentet; chat er
  ikke kilde til sandhed.

### Handover 2026-06-28 12:10 — fra Claude til Codex/Peter
- Hvad er gjort: AI-tagging-redesign. Åbent vokabular (ingen fraværs-tags), scene-rigdom,
  anomali-/hændelsesblok, kvalitet, strammet `unusable_image`-regel, synonym-konsolidering
  (`TAG_SYNONYMS`/`normalize_tag`), kontekst/baseline pr. billede, selvlærende kamera-baseline
  (static/dynamic), Gemini-billedbudget hævet til 4MB/3072px, Ollama tunet (qwen2.5vl:7b,
  1024px/1.5MB, scene-prompt). Migrationer v10 (baseline-felter) + v11 (auto_baseline) er
  KØRT (kolonner findes). Headend er genstartet og kører ny kode (pid 56137, health 200).
- Hvad mangler / næste skridt:
  1) Peter vælger: Ollama-vs-Gemini-sammenligning eller bulk re-tag (UI-batch m. `force`).
  2) `camera_profile.py --all --apply` skal køres IGEN EFTER en ren re-tag — de nuværende
     auto_baselines er lært af gamle/beskidte tags (Frøkjær blev fejl-klassificeret "dynamic").
  3) `TL-IMPORT-...Travbyen` har intet aktivt Camera → baseline ikke gemt; bind evt. til Camera.
  4) `pip install exifread` i venv (harmløs advarsel).
- Kommandoer kørt eller skal køres: se `FAQ_og_fejlsøgning.md` (re-tag, baselines, sammenligning).
- Forventet/faktisk output: backfill på rene billeder giver nu 14-30 dækkende tags (verificeret
  på dagens Frøkjær-billeder); `unusable_image` kun på ægte døde frames.
- Filer rørt (arbejdstræ, UCOMMITTET — bør committes på en `claude/ai-tagging-redesign` branch
  adskilt fra Codex' branches):
  `headend/ai/gemini_service.py`, `ollama_service.py`, `tag_vocabulary.py`, `integration.py`,
  `backfill.py`, `capture_context.py` (ny), `camera_profile.py` (ny),
  `normalize_existing_tags.py` (ny), `compare_ollama_gemini.py` (ny),
  `headend/database.py`, `headend/main.py`, `timelapse-ui/src/pages/CameraPage.tsx`,
  samt designnotat + disse fælles dokumenter i `Dokumentation/`.
- Risici / pas på: arbejdstræet er beskidt og rummer både mit AI-spor og Codex' edge/doc-spor —
  brug konkrete filer ved commit (ikke bred `git add .`), så sporene ikke blandes. Bulk re-tag
  af ~26.000 koster Gemini-penge (Peters beslutning).

### Handover 2026-06-28 12:25 — fra Claude til Peter (IGANGVÆRENDE)
- Hvad er gjort: Klargjort Ollama-vs-Gemini-sammenligning (`compare_ollama_gemini.py`) for begge
  sites. Jeg kan ikke køre den selv (sandbox når ikke Mac'ens Postgres/Ollama/Gemini/billedfiler).
- Hvad mangler / næste skridt: Peter kører kommandoen nedenfor; Claude læser resultatfilen fra
  Timelaps og analyserer (kvalitet pr. site, hvor Ollama er stærk/svag, om local_then_cloud er rigtigt).
- Kommandoer kørt eller skal køres:
  ```bash
  SFTP_BASE=$(psql -U timelapse timelapse_db -tA -c "SELECT COALESCE((SELECT value FROM settings WHERE key='sftp_base'),'/Volumes/data')") \
  TIMELAPSE_BACKFILL_ALLOW_DEEP_SCAN=1 \
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/compare_ollama_gemini.py \
    --sites "Nordre Villavej 17c,Travbyen" --per-site 5 \
    --out ~/Claude/Projects/Timelaps/compare_ollama_vs_gemini
  ```
- Forventet/faktisk output: `compare_ollama_vs_gemini.json` + `.md` i Timelaps. Ollama er den
  langsomme del (~10-40s/billede). Kræver Ollama oppe med `qwen2.5vl:7b`.
- Filer rørt: ingen (read-only sammenligning, rører ikke captures).
- Risici / pas på: ingen DB-skrivning; ren læse-sammenligning.

### Handover 2026-06-28 12:45 — fra Claude til Codex/Peter
- Hvad er gjort: Sammenligningen afslørede `No module named 'cv2'` i en frisk CLI-proces —
  dvs. cv2/OpenCV kan ikke importeres fra venv'en (sandsynligvis endnu et data-fast-symptom:
  headenden loadede cv2 ved opstart og kører fint, men friske scripts fejler importen fra
  det flaky volumen). Ollama brugte original (sikkert, men langsomt på fuldt 2600px-billede);
  Gemini's fallback **trunkerede** JPEG'en → ville give korrupt billede. RETTET: begge resize-
  stier har nu en **PIL-fallback** (`_resize_with_pil`) der nedskalerer uden cv2 og ALDRIG
  trunkerer — verificeret 2600px→1024px gyldigt JPEG.
- Hvad mangler / næste skridt: Peter kører sammenligningen igen (samme kommando) — fixet er på
  disken, så frisk CLI-proces bruger det straks. Codex/Peter: bekræft cv2 i venv
  (`~/.venvs/timelapse-headend/bin/python -c "import cv2"`); hvis den fejler, er det data-fast
  igen — overvej `pip install opencv-python-headless` og/eller flyt venv væk fra volumenet.
- Filer rørt: `headend/ai/gemini_service.py`, `headend/ai/ollama_service.py` (PIL-fallback).
- Risici / pas på: hvis HEADENDEN genstarter og heller ikke kan loade cv2 fra volumenet, fejler
  blur/brightness-beregning ved capture — endnu en grund til at få data-fast/venv sundt.

### Handover 2026-06-28 13:20 — fra Codex til Claude/Peter
- Hvad er gjort: Implementeret, bygget og installeret Orange Pi VIPLite-wrapperen
  `/opt/timelapse/bin/edge_qa_viplite`. Wrapperen kører Allwinner AWNN/VIPLite `.nb`, sender
  VIPLite-log til stderr og ren JSON til stdout. Python-runneren kan nu kalde wrapperen via
  `--vendor-binary` og normalisere `scores` til `timelapse.edge_qa.v1`.
- Hvad mangler / næste skridt: rigtig TimeLapse QA-model skal trænes/eksporteres til `.nb`.
  Den nuværende `/opt/timelapse/models/edge_qa.nb` er stadig SDK ResNet50-demo og må kun bruges
  som runtime-proof, ikke som kundevendt QA-sandhed.
- Kommandoer kørt eller skal køres:
  ```bash
  /opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/analyse_qa_batch.py \
    /tmp/timelapse-qa-board-contract \
    --mode npu_first \
    --runner "/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py" \
    --model /opt/timelapse/models/edge_qa.nb \
    --vendor-binary "/opt/timelapse/bin/edge_qa_viplite --input-layout nchw_bgr" \
    --out /tmp/timelapse-qa-board-contract/viplite-results.jsonl
  ```
- Forventet/faktisk output: batch kører med `npu.available=true`; CPU/optimizer forbliver
  styrende når demo-modellens confidence er lav. VIPLite output viser runtime-version
  `2.0.3.2-AW-2024-08-30`.
- Filer rørt: `edge/npu_viplite/*`, `edge/tools/build_edge_qa_viplite.sh`,
  `edge/tools/analyse_qa_batch.py`, `edge/tools/bootstrap_cli.py`, `headend/main.py`,
  `Dokumentation/Codex_Edge_AI_NPU_Modes_2026-06-28.md`.
- Risici / pas på: brug ikke ResNet-demoens labels til beslutninger. Næste reelle værdiskabelse
  er datasæt + træning/ACUITY-konvertering af en 9-klasses QA-model.

### Handover 2026-06-28 13:10 — fra Claude til Peter/Codex
- Hvad er gjort: Første compare-kørsel (fuldstore billeder til Ollama) viste at qwen2.5vl:7b på
  Mac'en er for langsom/upålidelig: timeout (120s), 168s/billede, hallucinerede tags
  (`unusable_image/muddy_ground` på ren villaudsigt), og kontekst-fejl
  "5185 tokens exceeds 4096". Gemini: 15-17 korrekte tags på 15-22s. RETTET: `VISION_NUM_CTX`
  4096 → 8192 (kontekst-fejlen) + PIL-resize fra forrige note (1024px → hurtigere).
- Hvad mangler / næste skridt:
  1) cv2 i venv: bekræft + installér — `~/.venvs/timelapse-headend/bin/python -c "import cv2"`;
     hvis fejl: `~/.venvs/timelapse-headend/bin/pip install opencv-python-headless`. Headenden
     bruger cv2 til blur/brightness, så det bør være installeret uanset.
  2) Re-kør compare (num_ctx+PIL nu aktivt) for et FAIRT tal med 1024px-billeder.
- Foreløbig vurdering: selv med fixene er Ollama på denne hardware sandsynligvis for langsom/
  svag til kvalitet; Gemini er klart bedst. local_only kun hvis privacy er et hårdt krav.
- Filer rørt: `headend/ai/ollama_service.py` (num_ctx 8192).
- Risici / pas på: 8192 ctx bruger mere RAM på Mac'en; juster via `TIMELAPSE_VISION_NUM_CTX`.

### Handover 2026-06-28 13:25 — fra Peter/Claude (status)
- Hvad er gjort: `cv2` var IKKE installeret i venv → installeret `opencv-python-headless 4.13`
  (+ `numpy 2.5` som dependency). Resize bruger nu cv2; PIL er fallback.
- Risici / pas på: numpy løftet 1.x → **2.5** (breaking changes). BEKRÆFT at headenden stadig
  importerer rent FØR næste genstart:
  `~/.venvs/timelapse-headend/bin/python -c "import numpy,cv2; print(numpy.__version__,cv2.__version__)"`
  og helst en kort import-test af headend-modulerne. Hvis noget brækker på genstart: pin
  `numpy<2` + en ældre `opencv-python-headless`.
- Næste skridt: re-kør compare (cv2 + num_ctx 8192 nu aktivt) for et fairt Ollama-vs-Gemini-tal.

### Handover 2026-06-28 13:40 — fra Claude til Peter/Codex (KONKLUSION: Ollama vs Gemini)
- Hvad er gjort: Fair sammenligning kørt (cv2-resize 1024px + num_ctx 8192), 6 billeder.
  Resultat: Ollama (qwen2.5vl:7b) gns. **2,0 tags / 50s**; Gemini gns. **21,3 tags / 15s**.
  Ollama timeout'ede stadig (157s→llava-fallback), gav 0 tags på 2/6, og hallucinerede forkerte
  tags på rene scener. Overlap med Gemini: 0-1 tags. Gemini fangede endda en event/anomali på
  Travbyen (fest med inflatable_arch/gazebo/group_of_people).
- KONKLUSION: **cloud_only (Gemini) er det klare valg.** local_only er ikke brugbart på denne
  Mac Mini (10× færre tags, ofte forkerte, 3× langsommere). local_then_cloud sparer intet —
  Ollama er usikker/tom på næsten alt, så stort set alt ville eskalere til Gemini ALLIGEVEL,
  blot 50s langsommere. Resultatfiler: `~/Claude/Projects/Timelaps/compare_ollama_vs_gemini.{json,md}`.
- Hvad mangler / næste skridt: Hylde Ollama indtil (a) privacy bliver et HÅRDT krav, eller
  (b) kraftigere hardware (Mac Studio / GPU-boks) hvor 7B-vision kører på sekunder, eller
  (c) edge-NPU-sporet (Codex) til on-device teknisk QA. Strategi sættes til cloud_only.
- Filer rørt: ingen (read-only sammenligning).
- Risici / pas på: at køre Ollama på Mac Mini'en konkurrerer om ressourcer med headenden.

### Handover 2026-06-28 14:05 — fra Claude til Peter/Codex (lokal-model status)
- Hvad er gjort: Testet `qwen3-vl:8b` via compare (--local-model). Resultat: **tomt response-felt
  på alle billeder (0 tags, 0ms)** — modellen er sandsynligvis for ny til den installerede Ollama
  (eller kræver /api/chat i stedet for /api/generate). Integrations-/versionsproblem, IKKE en
  kvalitetsmåling. Vision-kandidater på maskinen: qwen3-vl:8b (tom), qwen2.5vl:7b (langsom+svag),
  llava-phi3 (svag), gemma4:e4b (uprøvet). gpt-oss/deepseek/llama3.2 er tekst-only.
- ANBEFALING: Lokal vision er et selvstændigt R&D-spor (Ollama-version/integration + hardware-loft
  + evt. finetuning). Ship NU med `cloud_only` (Gemini), som er klar og fremragende. Forfølg lokal
  separat — naturligt sammen med Codex' edge-NPU-spor.
- Næste skridt hvis lokal skal forfølges: (1) `ollama --version` + opgradér Ollama; (2) rå test
  af qwen3-vl uden vores kode (curl /api/generate med ét billede) for at se om modellen overhovedet
  giver tekst i denne Ollama; (3) overvej /api/chat-sti for VL-modeller.
- Filer rørt: `headend/ai/compare_ollama_gemini.py` (--local-model flag).

### Handover 2026-06-28 14:30 — fra Claude til Peter/Codex (504 på bulk AI-batch)
- Hvad er gjort: `POST /api/admin/ai-batch/start` byggede for "alle 26.000" hele JSONL'en
  (base64 af alle billeder) + kontekst pr. billede SYNKRONT i HTTP-kaldet → minutter →
  nginx 504. RETTET i `headend/main.py`: hele job-prep (query, find filer, kontekst, encode +
  upload til Google) flyttet til en BAGGRUNDSTRÅD. Endpointet opretter nu job-rækken som
  `status=submitting` og returnerer straks; tråden opdaterer til `submitted`/`failed` og
  fylder gemini_job_name + total_count. Kontekst-bygning cacher nu Device pr. enhed.
- Hvad mangler / næste skridt: KRÆVER headend-genstart for at træde i kraft
  (`launchctl kickstart -k ...`). Bekræft derefter health=200.
- Workaround UDEN genstart (hvis bulk skal i gang nu): kør AI-batch i mindre bidder via `limit`
  (fx 500 ad gangen) ELLER brug post-processing AI-køen (tråder til live-worker, ingen 504,
  fuld pris) i bølger.
- AFKLAR: brugte Peter "AI-batch"-knappen eller "Post-processing → AI"? Hvis sidstnævnte gav
  504, er årsagen en anden (sandsynligvis Ollama health-check der hænger hvis strategi=local) —
  tjek headend-loggen omkring fejlen.
- Filer rørt: `headend/main.py` (ai-batch baggrundstråd).
- Risici / pas på: svaret skifter form (returnerer nu `{id,status:submitting}` i stedet for
  `total/gemini_job_name`) — UI'et følger jobbet via ai-batch/jobs-listen, som det allerede gør.

### Handover 2026-06-29 11:35 — fra Claude til Peter/Codex (batch: OOM-risiko + streaming-fix)
- Hvad er gjort: Bekræftet at ai-batch-fixet virker (200, jobs som `submitting`). MEN på Vertex
  byggede `_submit_batch_job_vertex_gcs` hele JSONL'en (base64 af ALLE billeder) som én streng i
  RAM → titals GB for 26.000 → ubrugeligt. RETTET: streamer nu til temp-fil på disk + GCS
  `upload_from_filename` (lavt RAM-forbrug). Peters 4 forsøg på "alle 26.000" blev dræbt af
  genstart → 4 forældede `submitting`-rækker i `ai_batch_jobs`.
- Næste skridt:
  1) Ryd rester: `UPDATE ai_batch_jobs SET status='failed' WHERE status='submitting';`
  2) Genstart headend (loader streaming-fixet).
  3) Kør i BIDDER (Maks billeder ~5000 eller pr. kamera), én ad gangen, vent submitting→submitted.
     ELLER brug AI-KØEN (AI+force, IKKE batch-mode) — fuld pris men robust, i bølger af ~5000.
- Filer rørt: `headend/ai/gemini_service.py` (Vertex JSONL streaming), `headend/main.py`
  (ai-batch baggrundstråd, tidligere note).
- Risici / pas på: tabel `ai_batch_jobs`. Kør IKKE "alle 26.000" i ét batch-job; chunk det.
  Klik Start én gang pr. bid og vent på status-flip.

### Handover 2026-06-29 11:50 — fra Claude til Peter/Codex (CLI chunked batch-script)
- Hvad er gjort: Afklaret at de eksisterende CLI-scripts (`backfill.py`, `backfill_tags.py`) kører
  SYNKRONT pr. billede (fuld pris) — der fandtes IKKE et chunked Gemini-Batch-script. Lavet
  NYT: `headend/ai/ai_batch_submit.py` — tager alle/filtrerede billeder, deler i bidder
  (`--chunk-size`, default 2000), og indsender hver bid som sit eget Gemini batch-job (~50% pris).
  Opretter AiBatchJob-rækker; headendens eksisterende 5-min poller finaliserer og skriver tags
  tilbage. Kører som frisk proces → bruger streaming-fix + ny prompt fra disk, INGEN genstart nødvendig.
- Kommandoer: dry-run → `--limit 2000 --force` test → `--all --force [--no-context]`.
  (`--no-context` = hurtigere; scene/kvalitet/normalisering virker stadig.)
- Forudsætning: headend oppe (poller), Vertex GCS-bucket sat, `SFTP_BASE` korrekt.
- Filer rørt: `headend/ai/ai_batch_submit.py` (nyt).
- Risici / pas på: bruger den nye streamede `submit_batch_job`; hver bid = ét Google-job.

### Handover 2026-06-29 12:10 — fra Claude til Codex (TO settings-tabeller!)
- Fund: Kodebasen har TO parallelle settings-tabeller der læses forskelligt:
  headend/UI bruger `settings` (via `main._get_setting`), mens `settings_helper.get_setting`
  (brugt af backfill, ai_batch_submit, ai_router) læser `system_settings`. Konfig er SPLIT:
  fx ligger `gemini_gcs_bucket` i `settings`, mens `gemini_api_key`/service_account fandtes i
  `system_settings`. Det gav "Vertex kræver GCS-bucket" i CLI selvom bucket'et var sat i UI.
- Fix (midlertidig): `ai_batch_submit.py._setting()` læser nu fra BEGGE tabeller (settings først).
- Anbefaling til Codex: konsolidér de to tabeller til ÉN kilde (eller lad `settings_helper` læse
  `settings`), så headend og CLI-scripts deler samme config. Tilføj evt. til "kendte faldgruber"
  i driftsdokumentet.
- Filer rørt: `headend/ai/ai_batch_submit.py` (_setting dual-table reader).

### Handover 2026-06-29 12:10 — fra Claude til Peter/Codex (BATCH KØRER ✅)
- Hvad er gjort: Test-bid (2000 billeder) indsendt OK via `ai_batch_submit.py`:
  Gemini batch-job `projects/825723674551/.../batchPredictionJobs/705361929266266112`,
  2000 billeder, 0 manglede. Hele kæden (find→resize/encode→stream til GCS→submit→AiBatchJob-række)
  virker. `--skip` tilføjet for at fortsætte fra bid 2.
- Næste skridt: kør bid 2-14: `ai_batch_submit.py --skip 2000 --force --no-context` (gerne nohup).
  Når alle jobs er `succeeded`, kør `camera_profile.py --all --apply` (baselines på rene tags).
- Pris: ~$34 / ~250 DKK for alle 26.159 (Gemini 2.5 Flash batch). Resultater: min → 24t.
- Filer rørt: `headend/ai/ai_batch_submit.py` (--skip).
- Risici / pas på: build+upload er CPU/IO-tungt (~3 min/2000 billeder); nohup til den store kørsel.

### Handover 2026-06-29 12:25 — fra Claude til Peter/Codex (BULK INDSENDT — alle 14 jobs ✅)
- Hvad er gjort: ALLE 14 Gemini batch-jobs indsendt (test 2000 + `--skip 2000` gav 13 jobs à 2000/161
  = 24.161). I alt ~26.161 billeder re-tagges med den nye prompt. Google kører async; headendens
  poller (5-min) skriver tags tilbage. Bulk re-tag-tråden i §7 kan markeres som I GANG/næsten færdig.
- Følg: `SELECT status, count(*), sum(total_count) FROM ai_batch_jobs GROUP BY status;` eller UI.
- Næste/sidste skridt: når alle 14 er `succeeded` → `camera_profile.py --all --apply` (baselines på
  rene tags). Derefter er hele AI-tagging-opgaven i mål.
- Pris: ~$34 / ~250 DKK engang.
- Filer rørt: ingen nye (kørsel).

### Handover 2026-06-29 — fra Claude til Peter/Codex (live fremdrift på batch-jobs i UI)
- Hvad er gjort: Batch-job-kortet i UI'en viste kun `success_count` ved `succeeded`/`failed` —
  under `running` ingen indikation. Nu hentes Vertex' løbende `completion_stats`
  (successful/failed/incomplete) i `gemini_service.get_batch_status` (defensivt — flere
  mulige feltnavne, None hvis ikke til stede → ingen regression), polleren skriver dem hjem
  i `success_count`/`error_count` mens jobbet kører, og UI'en viser nu en fremdriftsbjælke +
  `X / total %`. INGEN migration (kolonnerne fandtes). UI poller batch-jobs hvert 30. sek.
- Hvad mangler / næste skridt: KRÆVER headend-genstart (ny backend-kode) + UI-rebuild
  (`cd timelapse-ui && npm run build`). Verificér compile: py_compile OK, `tsc --noEmit` OK.
- VERIFICÉR PÅ MAC: at google.genai's BatchJob (Vertex) FAKTISK eksponerer completion_stats i
  jeres SDK-version. Hvis fremdriften står på 0 under running efter genstart, er feltet ikke
  eksponeret → log `dir(status['job'])` i polleren og tilpas feltnavnene i `get_batch_status`.
  (Worst case: ingen skade — kortet viser bare total_count som før.)
- Filer rørt: `headend/ai/gemini_service.py`, `headend/main.py`,
  `timelapse-ui/src/pages/PostProcessingPage.tsx`.
- Risici / pas på: rent additiv ændring; finalize-stien (tags hjem ved 100%) er urørt.

### Handover 2026-06-29 16:05 — fra Codex til Claude/Peter
- Hvad er gjort: Påbegyndt produktionsgørelse af Edge QA-modellen: tilføjet mining-værktøj til
  historiske billeder (`mine_qa_training_candidates.py`), review contact sheets
  (`render_qa_review_sheet.py`), isoleret PyTorch/ONNX træningsscript og ACUITY export-noter.
- Hvad mangler / næste skridt: kør mining på 5.000-20.000 historiske billeder, review ark pr.
  label, og træn første ONNX-model i separat training-venv. Derefter konverteres ONNX til `.nb`.
- Kommandoer kørt eller skal køres:
  ```bash
  python edge/tools/mine_qa_training_candidates.py /Volumes/data-fast/timelapse-incoming/canonical-images \
    --limit 5000 --per-label 500 --include-review \
    --out /tmp/edge-qa-dataset/candidates.jsonl \
    --summary-out /tmp/edge-qa-dataset/summary.json
  python edge/tools/render_qa_review_sheet.py \
    --manifest /tmp/edge-qa-dataset/candidates.jsonl \
    --out-dir /tmp/edge-qa-dataset/review
  ```
- Forventet/faktisk output: syntetisk test rammer labels for ok, underexposed, sol/refleks,
  linse/sne/skidt, hvidbalance og dybdeskarphed. Lille real sample viser især sol/refleks og
  enkelte sløringskandidater; review er nødvendigt for at adskille sol/refleks fra frontglas.
- Filer rørt: `edge/tools/mine_qa_training_candidates.py`,
  `edge/tools/render_qa_review_sheet.py`, `edge/training/*`, `tests/test_edge_quality_qa.py`,
  `Dokumentation/Codex_Edge_AI_NPU_Modes_2026-06-28.md`.
- Risici / pas på: træn ikke blindt på CPU-heuristik labels. Brug review CSV/ark og hold training
  dependencies ude af headend/edge runtime-venv.

### Handover 2026-06-29 — fra Claude til Peter/Codex (dedup-fix + afsluttende kommandoer)
- Hvad er gjort: Rettet en lille dedup-glip i `_build` i begge vision-services. Tidligere blev kun
  `new_tags` deduppet; `approved`-listen (vokabular-ord) kunne indeholde dubletter (fx `trees`,
  `trees`), og et ord modellen lagde i BÅDE `tags` og `new_tags` kunne ende i både `approved` og
  `new` (kryds-dublet i den kombinerede `ai_tags`). Nu: `all_tags` deduppes ved kilden, og `new`
  gøres disjunkt fra `approved`. Verificeret med property-test (compile OK + ingen dubletter +
  disjunkte). Fremtidige tags (live worker efter genstart + alle CLI/batch-resultater) er rene.
- Hvad mangler / næste skridt — de TO afsluttende kommandoer, når alle batch-jobs er `succeeded`
  (`SELECT status, count(*) FROM ai_batch_jobs GROUP BY status;` viser kun `succeeded`):
  ```bash
  # 1) Ryd dubletter + synonymer på HELE historikken (også de billeder der allerede blev
  #    batch-tagget med gammel kode). Ingen Gemini-omkostning. Dry-run uden --apply.
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/normalize_existing_tags.py            # dry-run
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/normalize_existing_tags.py --apply    # gem

  # 2) Lær kamera-baselines på de RENE tags (static vs dynamic).
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all              # dry-run
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all --apply      # gem
  ```
- Forventet output: `normalize_existing_tags` er idempotent (anden kørsel = no-op) og rører kun
  `ai_tags` + tag-lister i `ai_result`, ikke billeder/scene-tekst. Verificeret: `trees`×2 → ×1,
  `dannebrog` → `danish_flag`. Derefter er hele AI-tagging-opgaven i mål.
- Filer rørt: `headend/ai/gemini_service.py`, `headend/ai/ollama_service.py` (dedup i `_build`).
- Risici / pas på: dedup-fixet i live worker kræver headend-genstart for at træde i kraft; CLI/batch
  bruger disk-koden straks. `normalize_existing_tags.py --apply` rydder uanset alle eksisterende
  dubletter, så genstart er ikke nødvendig for at få historikken ren.

### Handover 2026-06-29 17:05 — fra Codex til Claude/Peter (Edge QA modeldata)
- Hvad er gjort: Fortsat produktionsgørelse af Edge QA/NPU-modelsporet. Mining-værktøjet har nu
  stratificeret sampling, bucket-cap, progress-output og dæmpet QualityChecker-logspam. Label-logik
  er rettet, så primære QA-flags vinder over optimizer-anbefalinger, og eksponering prioriteres over
  dybdeskarphed når begge foreslås.
- Verificeret: `tests/test_edge_quality_qa.py` kører grønt (`25 passed`). Ny baseline-mining er kørt
  på 1500 historiske billeder med `--sample-mode stratified --max-per-bucket 3`.
- Artefakter:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-normal-baseline-20260629-164818`
  indeholder `candidates.jsonl`, `summary.json`, `mine.log` og `review/`.
- Faktisk label-fordeling i baseline: selected=935, errors=0,
  `direct_sun_reflection=250`, `depth_of_field_issue=250`, `overexposed=239`,
  `underexposed=141`, `blurry=54`, `white_balance_cast=1`.
- Vigtigt fund: der kom stadig ingen sikre `ok`-billeder i denne historiske sampling. Træn derfor
  ikke NPU-model blindt på baseline-manifestet. Næste skridt er målrettet OK-mining i dagslys og
  human review af `review/review.csv`, før første ONNX-træning.
- Filer rørt: `edge/tools/mine_qa_training_candidates.py`, `tests/test_edge_quality_qa.py`,
  `Dokumentation/Codex_Edge_AI_NPU_Modes_2026-06-28.md`, `Dokumentation/HANDOVER_LOG.md`.
- Risici / pas på: `depth_of_field_issue`-arket indeholder stadig mange review-cases, som kan være
  vejr/snavs/dug snarere end ægte optisk dybdeskarphed. Brug `needs_human_review` som review-kø, ikke
  som automatisk træningssandhed.
