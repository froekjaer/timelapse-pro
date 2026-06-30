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

### Handover 2026-06-29 17:35 — fra Codex til Claude/Peter (aftale om driftsovervågning + Edge QA)
- Hvad er gjort: Opdateret samarbejdsdokumentet med en konkret snitflade mellem Claudes
  driftsovervågningssystem og Codex' Edge QA/NPU-spor. Claude ejer headend-observability,
  aggregater, alarmer og UI. Codex ejer Edge QA runtime, NPU, modelkontrakt, sidecar-format og
  billedkvalitetsdata.
- Kontrakt til Claude: overvågningen bør bruge `quality_flag`, `quality_passed`,
  `probable_cause`, `confidence`, `quality_dimension`, `autonomous_optimizer.score`,
  `autonomous_optimizer.recommendations`, `autonomous_optimizer.control_plan` samt `npu.*`.
- Vigtig beslutning: Headend-overvågningen skal aggregere/visualisere Edge QA-resultater, ikke
  genklassificere billeder fra pixels som primær logik. Manglende felter i gamle billeder vises som
  `unknown`/`not_available`.
- Samtidig Edge QA-fund: dagslys-scan på 3000 historiske billeder viser, at optimizerens
  `depth_of_field`-hint er for aggressivt som træningslabel. OK-reglen er justeret, så gode
  timelapse-billeder med almindelige/svage depth-hints kan være `ok`, mens stærk sol/fokus/
  vedligehold/hvidbalance/eksponering stadig sorteres fra. Teststatus: `26 passed`.
- Filer rørt: `Dokumentation/HANDOVER_Claude_Codex_arbejdsdeling.md`,
  `Dokumentation/SERVICES_OG_DRIFT_kilde_til_sandhed.md`,
  `Dokumentation/HANDOVER_LOG.md`, `edge/tools/mine_qa_training_candidates.py`,
  `tests/test_edge_quality_qa.py`.
- Næste skridt for Codex: lave et lille JSON-schema/eksempel for `edge_qa_signal` og fortsætte
  målrettet OK-mining + review-manifest. Næste skridt for Claude: bygge driftsovervågning mod
  kontraktfelterne og markere ukendte gamle værdier som `unknown`.

### Handover 2026-06-29 — fra Claude til Codex/Peter (ITIM/Observability v1.0 + aftalt forløb)
- Hvad er gjort: Bygget **ITIM/Observability v1.0** i headenden (Peters go på v1 uden at vente).
  Letvægt i Postgres (besluttet med Peter), additive `itim_`-tabeller i `timelapse_db`, designet
  til senere udtræk. Modul: `headend/itim.py` (models + collector + alarmer + retention + API).
  Wiret i `main.py` (router `/api/itim/*` + `start_itim_collector()` i startup).
  - **Genbruger eksisterende data** frem for at duplikere: `diagnostics` (batteri-/solspænding,
    CPU-temp, disk, kamera-batteri, shutter, upload-kø) → edge-health; `ai_batch_jobs` →
    AI-pipeline; `captures.ai_tags` → billedfejl-rater (INTERIM, se nedenfor).
  - **Nye probes:** host-metrics (psutil), service oppe/nede (headend/postgres/nginx/ollama),
    og **data-fast volumen-helbred** (mounted/writable/io_latency — den tilbagevendende smerte;
    seedet alarm: writable==0 critical, io_latency_ms>250 critical).
  - Alarmer via eksisterende `ai.notify` med cooldown (genbrug af SIEM-mønster) + retention/rollup
    (rå 48t → 5m 30d → 1h ~13mdr). 12 default-regler seedet idempotent.
  - GDPR-invariant: kun numeriske drifts-tal, ingen billeder/personoplysninger/IP i metrics.
  - Verificeret: `py_compile` grøn for `itim.py` og `main.py`.
- **AFTALT FORLØB / arbejdsdeling** (jeg følger §8 i `HANDOVER_Claude_Codex_arbejdsdeling.md`):
  - **Claude (gjort):** headend-observability — API, collector, aggregater, alarmer, retention.
    Billedkvalitet kører lige nu på cloud-`ai_tags` som **INTERIM** (markeret `engine=cloud_tags`,
    summary siger "interim"). Metric-navnene er allerede lagt på JERES kontrakt-taksonomi
    (`unusable_rate`, `blurry_rate`, `overexposed_rate`, `underexposed_rate`,
    `lens_obstruction_rate`) så der IKKE skal omdøbes når edge-signalet lander.
  - **Codex (næste):** lever `edge_qa_signal`-feltet/skemaet + hvor det lagres (capture-kolonne
    eller sidecar + ingest), med felterne fra §8 (`quality_flag`, `probable_cause`,
    `quality_dimension`, `autonomous_optimizer.*`, `npu.*`). Sig til når feltnavn/lagring er fast.
  - **Claude (efter Codex):** skifter `_probe_image_qa` til at aggregere `edge_qa_signal` som
    PRIMÆR kilde (ai_tags som fallback, manglende → `unknown`), mapper `probable_cause` →
    defekt-metrics + viser engine-proveniens (`edge_cv_v1` / `edge_npu` / `cloud_tags`), og bygger
    Drift-UI med aggregater pr. kunde/site/kamera.
  - **Codex (OS/drift) for at gå live:**
    1. `~/.venvs/timelapse-headend/bin/pip install psutil`  (host-metrics; uden den springes de
       bare over — resten kører).
    2. Genstart headend: `launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend`
       → `itim_*`-tabeller auto-oprettes via `create_tables()`, collector starter, seeder regler.
    3. Verificér: `curl -s -H "Cookie: tl_session=…" http://127.0.0.1:8000/api/itim/health | head`
       (eller via UI når Drift-siden er bygget). Tiles bør vise data-fast/headend/postgres grønne.
    4. (Valgfrit) sudo-baseret temp/SMART (`smartmontools`/`powermetrics`) hvis I vil have
       Mac-temperatur/disk-SMART — ellers psutil-only i v1.
  - **Claude (resterende):** Drift-UI-side + menupunkt under Admin (i gang), + fold SIEM/CMDB-
    optimeringer ind (death sqlite-kode, `/threats` event_type-mismatch, retention på
    `security_events`, break-glass MFA-TODO).
- Filer rørt: `headend/itim.py` (ny), `headend/main.py` (router + collector-start),
  `Dokumentation/Claude_Observability_ITIM_Design_2026-06-29.md` (design-notat).
- Risici / pas på: collectoren skriver en lille probe-fil i `<data-fast>/.itim-probe/` (rydder selv
  op) — det er bevidst, så vi måler writable/io_latency. Probe-stien kan flyttes via setting
  `itim_data_fast_path`. Tråd-i-headend nu (dør med headend; edge-ping dækker hullet senere).
  `psutil` mangler sandsynligvis i venv → host-tiles tomme indtil punkt 1 er kørt.

### Handover 2026-06-29 — fra Claude til Codex/Peter (SIEM/CMDB-optimeringer: branch-prep, IKKE live)
- Aftalt forløb (Peter): folde de fire optimeringer ind som branch-/PR-forberedelse, additivt +
  bag flag, INGEN schema-break, INGEN live-deploy før ITIM er live-verificeret af Codex; merge
  først DEREFTER. Alle fire er lavet additive og **default-inerte** (kompilerer: py_compile OK):
  1. **siem.py — død sqlite-kode fjernet** i `_ensure_schema` (Postgres-only). Ingen adfærdsændring.
  2. **siem.py — `/threats` event_type-mismatch rettet:** matcher nu et KONFIGURERBART sæt
     (`TIMELAPSE_SIEM_THREAT_EVENT_TYPES`, default = legacy `ssh_failure` + de faktiske typer
     `ssh_tunnel_connect_failed`/`ssh_tunnel_remote_port_busy`/`network_auth_failed` m.fl.).
     Strengt additivt ift. gammel adfærd (fanger mere, fjerner intet).
  3. **siem.py — opt-in retention** `prune_old_events()` + timetrottlet kald i log-collectoren.
     **DEFAULT FRA** (`TIMELAPSE_SIEM_RETENTION_DAYS=0` → sletter intet). Destruktiv kun når
     bevidst aktiveret.
  4. **cmdb.py — break-glass checkout hærdning:** opt-in rate-limit
     (`TIMELAPSE_BREAKGLASS_CHECKOUT_MAX_PER_HOUR`, default 0 = fra) + valgfri IP-allowlist
     (`TIMELAPSE_BREAKGLASS_IP_ALLOWLIST`, tom = fra). MFA er stadig en opfølgning (kræver
     auth-integration). Default-flow uændret.
- **Flag der SKAL forblive USAT indtil ITIM er live-verificeret** (så ny logik ikke kobles hårdt
  på før signalet er bekræftet): alle fire env-flag ovenfor + ITIM kører på sine defaults.
- **VIGTIGT git-fund — branch-isolation overlades til Codex/Peter:** arbejdstræet er på `main` og
  meget broget (begge spor ukommitteret). Specifikt bærer `cmdb.py` en STOR ukommitteret
  **RBAC-refaktorering** (role-guards `_require_cmdb_role` på alle CMDB-endpoints — viewer/admin),
  som IKKE er mine ændringer og ikke ligger i committet `main`. Derfor kan mine fire optimeringer
  IKKE whole-file-committes rent (det ville sammenblande spor / risikere at tabe RBAC-hærdningen).
  Jeg har bevidst IKKE kørt `git checkout -b`/commit. Anbefalet isolation (Codex/Peter):
  ```bash
  git checkout -b claude/siem-cmdb-optimizations
  git add -p headend/siem.py headend/cmdb.py   # vælg KUN de fire optimerings-hunks
  git commit -S -m "SIEM/CMDB: threats-fix, sqlite-cleanup, opt-in retention, break-glass hærdning (default-inert)"
  ```
  Markører i hunks: `prune_old_events`, `TIMELAPSE_SIEM_THREAT_EVENT_TYPES`,
  `sqlite bruges ikke`, `Break-glass checkout-hærdning`, `_enforce_break_glass_policy`.
- **Separat anbefaling:** den ukommitterede CMDB-**RBAC-refaktorering** (role-guards) bør committes
  bevidst på sin egen branch — det er en reel sikkerhedshærdning der pt. kun lever i arbejdstræet
  og kan gå tabt ved en reset. Hvem ejer den? (Claude kan ikke se det fra git-historikken.)
- Filer rørt: `headend/siem.py`, `headend/cmdb.py`.
- Risici / pas på: intet aktiveres af sig selv (alle flag default-fra). Merge/deploy først efter
  ITIM live-verifikation (Peters punkt 5).

### Handover 2026-06-30 09:40 — fra Codex til Claude/Peter (ITIM live-verificeret + branches isoleret)
- Hvad er gjort: ITIM/Observability v1.0 er live-verificeret på headenden. `psutil` var allerede
  installeret i `~/.venvs/timelapse-headend`. `py_compile` er grøn for `headend/itim.py`,
  `headend/main.py`, `headend/siem.py` og `headend/cmdb.py`. Headend er genstartet rent med
  `launchctl kickstart`, `/api/health` svarer 200.
- Faktisk live-status: `itim_*`-tabeller er oprettet; seneste check viste 8 targets, 34 samples,
  8 health rows, 12 alert rules og 2 alert events. Collector starter i loggen med
  `ITIM collector startet (interval=60s)`.
- Data-fast-probe: første run gav en falsk critical, fordi default-stien `/Volumes/data-fast` er
  root-ejet, selv om TimeLapse-dataområdet er skrivbart. Codex satte derfor:
  `settings.itim_data_fast_path=/Volumes/data-fast/timelapse-incoming`. Efter genstart er
  `vol:data-fast` `ok` med `mounted=1`, `writable=1`, `io_latency_ms≈0.3`, og den tidligere
  `data-fast ikke skrivbar` alert blev automatisk `resolved`.
- Aktuel reelt firing signal: `pipeline:ai` warning for `batch_jobs_failed_24h=4` og
  `batch_jobs_running=7`. Det ligner et rigtigt driftssignal fra batchstatus, ikke ITIM-fejl.
- Branch-isolering udført:
  - `claude/siem-cmdb-optimizations` push'et med commit `a595c6a`:
    `headend/siem.py` + break-glass opt-in hardening i `headend/cmdb.py`. Ingen RBAC-hunks.
  - `codex/cmdb-rbac-hardening` push'et med commit `b5cfc34`:
    CMDB role guards/status hardening isoleret uden Claudes break-glass env-flag.
- Filer/DB rørt live: `settings.itim_data_fast_path` i Postgres. Kode deployet via allerede
  liggende worktree-ændringer + headend-genstart; branchene ovenfor er review-/merge-grundlaget.
- Næste skridt: Claude kan nu skifte SIEM/CMDB-optimeringer fra "venter på ITIM" til klar til
  review/merge efter Peters prioritering. Drift-UI kan bygges mod ITIM-kontrakten; gamle/manglende
  Edge QA-felter skal stadig vises som `unknown`.

### Handover 2026-06-30 11:30 — fra Codex til Claude/Peter (Edge QA lokal AI v1 smoke)
- Hvad er gjort: Gennemført næste Edge AI/NPU-spor fra historiske billeder til en faktisk ONNX
  smoke-model. Mining på 12000 billeder gav 6381 kandidater og en brugbar `ok`-klasse
  (`ok=1200`, `direct_sun_reflection=1200`, `depth_of_field_issue=1200`, `overexposed=1200`,
  `underexposed=1162`, `blurry=408`, `white_balance_cast=11`).
- Artefakter:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321`
  indeholder `candidates.jsonl`, curated manifests, `review/`, model-mappe og ACUITY bundle.
- Model: `model-broad-v1-smoke/edge_qa_model.onnx` er eksporteret og valideret med ONNX Runtime.
  `edge_qa_npu_runner.py` kan nu køre `.onnx` lokalt med `engine=edge_onnxruntime_local` og returnere
  `timelapse.edge_qa.v1`.
- Orange Pi prep: ONNX + metadata er kopieret til `timelapse0101` som
  `/opt/timelapse/models/edge_qa_model_v1_smoke.onnx` og
  `/opt/timelapse/models/edge_qa_model_v1_smoke_metadata.json`. Demo
  `/opt/timelapse/models/edge_qa.nb` er ikke overskrevet.
- Kvalitet/status: v1-smoke beviser pipeline, men er ikke produktionsklar (`best_val_accuracy=0.36`,
  `test_accuracy≈0.31`). CPU/OpenCV optimizer skal fortsat være autoritativ fallback.
- ACUITY: bundle klar som `acuity-bundle-v1-smoke.tar.gz` med ONNX, metadata og 83
  kalibreringsbilleder. Docker CLI findes, men Docker daemon kørte ikke, så `.nb`-konvertering er
  ikke udført endnu.
- Fuldrun til v2: startet som baggrundsjob i
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-full-20260630-112714`
  (`run-full-mining.sh`, `full-mining.log`, `full-mining.pid`).
- Filer rørt: `edge/tools/curate_qa_training_manifest.py`,
  `edge/tools/edge_qa_npu_runner.py`, `edge/training/train_edge_qa_model.py`,
  `edge/training/requirements-edge-qa.txt`, `tests/test_edge_quality_qa.py`,
  `Dokumentation/Codex_Edge_AI_NPU_Modes_2026-06-28.md`, `Dokumentation/HANDOVER_LOG.md`.
- Næste skridt: lad fuldrun færdiggøre, render review-ark, human-review de støjende klasser og træn
  v2. Kør ACUITY-konvertering når Docker daemon + Allwinner ACUITY image/workspace er klar.

### Handover 2026-06-29 — fra Claude til Codex/Peter (ITIM-hærdning + natlig baseline-genberegning)
- Hvad er gjort (py_compile grøn for `itim.py`, `main.py`, `ai/camera_profile.py`):
  1. **ITIM data-fast-probe hærdet** efter Codex' live-fund (falsk critical pga. root-ejet
     volumen-rod):
     - **Smartere default-sti:** probe defaulter nu til `itim_data_fast_path` → env →
       `sftp_base` (kendt skrivbar) → fallback. Virker out-of-the-box uden manuel setting.
     - **EACCES skelnes fra I/O-fejl:** en rettighedsfejl giver `warning`
       ("probe-sti ikke skrivbar — sæt itim_data_fast_path") og rører IKKE `writable`-metrikken,
       så `writable==0`-alarmen ikke fyrer falsk. Kun ægte I/O-fejl/umonteret → `critical`.
       Ny hjælpe-metrik `probe_config_ok` (0/1). Codex' eksisterende setting respekteres uændret.
  2. **Natlig baseline-genberegning** som **headend-baggrundstråd** (IKKE Cowork-skemalagt — den
     kan ikke nå Mac'ens DB). Ny `camera_profile.recompute_all_baselines(db, apply=True)` +
     `_baseline_recompute_loop` i `main.py`, startet i startup. Kører én gang i døgnet kl. 03
     lokal tid (env `TIMELAPSE_BASELINE_RECOMPUTE_HOUR`, slå fra med
     `TIMELAPSE_BASELINE_RECOMPUTE_ENABLED=false`). Idempotent.
- Kræver headend-genstart for at aktivere (hærdning + natlig tråd). KØR NU (uden genstart, CLI
  bruger disk-koden) for at få baselines på de rene tags med det samme:
  ```bash
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all --apply
  launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend   # aktiverer hærdning + natlig tråd
  sleep 25 && curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
  ```
- Forventet: `camera_profile` printer profiler + "✅ gemt på aktivt kamera"; efter genstart logger
  headenden "Natlig baseline-genberegning aktiv (kl. 03 lokal tid)" og data-fast-tile forbliver `ok`
  (rettighedsfejl ville nu give `warning`, ikke `critical`).
- Filer rørt: `headend/itim.py`, `headend/main.py`, `headend/ai/camera_profile.py`.
- Risici / pas på: disse ITIM-ændringer er additive oven på den allerede live-verificerede v1.0 →
  bør på `claude/...`-branch og genstartes bevidst (ikke nødvendigvis sammen med SIEM/CMDB-merge).

### Handover 2026-06-29 — fra Claude til Peter/Codex (baseline static/dynamic-fix + Travbyen-binding)
- Fund ved første baseline-kørsel på rene tags:
  1. **TL-C87FF9587CA0 (villa-/byudsigt) fejl-klassificeret `dynamic`** ("AKTIV BYGGEPLADS") —
     burde være `static`. Årsag: `compute_profile` talte ordvalgs-drift mellem nær-synonymer
     (`house↔apartment_building`, `bushes↔vegetation`) som "forandring"; bløde tærskler
     (older<10%, recent≥30%) blev krydset af modellens sprog-variation.
  2. **Travbyen korrekt `dynamic`**, men `store_baseline` returnerede "intet aktivt kamera" →
     enheden `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1` har INGEN aktiv `device_assignments`-binding.
- Fix (kun klassifikationen — `generate_baseline_text` gater allerede bygge-sprog på kind):
  - **Hysterese** på new/gone: ny kræver older<5% OG recent≥50%; gone kræver older≥40% OG recent<5%.
  - **Byggeplads-gate**: `dynamic` kræver nu BÅDE ≥3 stærke ændringer OG mindst ét
    `_CHANGE_DOMAIN_TAGS` (scaffolding/crane/excavator/shell_construction/facade_cladding/…) i
    scenen. En stabil udsigt med kun synonym-drift forbliver derfor `static`.
  - Simulationstest (uden DB): Frøkjær→`static`, Travbyen→`dynamic`. py_compile grøn.
- Handling:
  - Peter genkører (CLI, ingen genstart nødvendig — bruger disk-koden):
    `~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all --apply`
    → forvent: TL-C87FF9587CA0 = `static`, Travbyen = `dynamic`.
  - **Travbyen-binding** (så dens baseline kan gemmes): tildel et logisk `Camera` til enheden
    `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1` (UI: Kamera-tildeling / `device_assignments`).
    Indtil da beregnes baselinen korrekt men gemmes ikke (returnerer "intet aktivt kamera").
- Filer rørt: `headend/ai/camera_profile.py` (`_CHANGE_DOMAIN_TAGS` + hysterese + gate).
- Designvalg: i dette produkt = "dynamic" betyder *aktiv byggeplads*, så vi gater bevidst på
  bygge-domæne-tags. En ikke-bygge dynamisk scene ville vises som `static` (acceptabelt her).

### Handover 2026-06-29 — fra Claude til Peter (RETTELSE: baseline-fix overkorrigerede sparsomme kameraer)
- Genkørslen afslørede en regression i mit FØRSTE fix: TL-C87FF9587CA0 blev korrekt `static`, MEN
  Travbyen blev fejlagtigt `static`. Årsag: jeg koblede byggeplads-gaten til hysterese + ≥3
  overgange — for stramt for sparsomme kameraer (Travbyen 51 billeder → for få stærke overgange).
- RETTET: `dynamic` afgøres nu af det ROBUSTE signal — om scenen PERSISTENT indeholder bygge-
  domæne-tags (`scaffolding/construction_site/shell_construction/scissor_lift/facade_cladding/…`).
  Uafhængigt af datatæthed. new_since/gone_since bruges nu KUN til progressions-teksten, ikke til
  beslutningen. Hysteresen rullet tilbage til de oprindelige bløde tærskler (rigere progression).
- Simulationstest (4 cases, py_compile grøn): Frøkjær tæt→static, Travbyen 51/15→dynamic,
  Travbyen uden ældre data→dynamic, lille static 12/0→static. ALLE korrekte.
- Handling: Peter genkører `camera_profile.py --all --apply` → forvent nu TL-C87FF9587CA0=`static`,
  Travbyen=`dynamic` (men stadig "ikke gemt" til kameraet er bundet — se forrige note).
- Filer rørt: `headend/ai/camera_profile.py`.

### Handover 2026-06-29 — fra Claude til Peter (adaptivt baseline-vindue: brug de tusinder)
- Diagnose bekræftede: Travbyen = ÉN device_id (`TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1`),
  **5029 billeder, alle taggede, 2022-01-26 → 2026-05-08**. Ingen device-split, ingen tagging-gap.
  Baselinen brugte kun 51 fordi det FASTE 21-dages vindue (ankret på sidste billede 8. maj) kun
  fanger den sparsomme slutfase; de 5029 lå som "ældre" historik.
- FIX: `compute_profile` har nu et **adaptivt vindue** (ny param `min_samples=150`): start ved
  `window_days` (21); hvis for få billeder, udvid trinvist (45→90→180→365→730 dage) indtil
  ≥ min_samples. Tætte aktive kameraer (Frøkjær, 4032/21d) rammer grænsen straks og beholder 21d;
  tynde lang-historik-kameraer (Travbyen) udvider og bruger hundredevis i stedet for 51.
  Profilens `window_days` afspejler det faktiske vindue (baseline-teksten siger "seneste N dage").
- Simulation (py_compile grøn): Frøkjær → static, 21d, n=4032; Travbyen → dynamic, udvider til
  ~365d, n≈447 (ikke 51).
- Handling: Peter genkører `camera_profile.py --all --apply`. Forvent Travbyen nu med et bredere
  vindue og mange flere billeder i baselinen. (Stadig "ikke gemt" indtil et `Camera` bindes til
  enheden — uændret.)
- Filer rørt: `headend/ai/camera_profile.py` (adaptivt vindue).

### Handover 2026-06-29 — fra Claude til Peter (tæthed-kalibrering: min_samples som knap)
- Kontekst fra Peter: Frøkjær er TESTSYSTEM (~144 billeder/døgn, 24/7) og atypisk tæt; ægte
  produktions-sites er sparsomme (Travbyen ~3-4/dag, kun dagtimer), tættere fremover. Det adaptive
  count-baserede vindue er netop designet til at normalisere den variation (tæt → 21d; tynd →
  udvides til stabil baseline) — ingen Frøkjær-specifik tuning bagt ind.
- Tilføjet `min_samples` som **knap** (CLI `--min-samples`, env `TIMELAPSE_BASELINE_MIN_SAMPLES`,
  default 150). Verificeret på 4/dag-dagtimer-kamera: 150→45d/181 billeder, 80→21d/85, 300→90d/361.
- Dag/nat-egenskab værd at huske: 24/7-kameraer (Frøkjær) får ægte nat-baseline; dagtimer-kun
  kameraer får korrekt "nat = mørke/ingen aktivitet" → ethvert natbillede m. personer/køretøjer
  bliver automatisk en anomali. Virker for begge mønstre uden ændring.
- Filer rørt: `headend/ai/camera_profile.py` (min_samples-param + CLI/env-knap).

### Handover 2026-06-29 — fra Claude til Peter/Codex (thumbnails: tomme rammer = Travbyen + thundering herd)
- Analyse: `get_thumbnail` (GET) er serve-only og 404'er ved manglende fil → frontend viser tom
  ramme. Survey: 36.474 billeder, 32.503 thumbnails, 0 korrupte → ~3.970 mangler, og de ligger
  ALLE under `Kirkbi_A_S/Travbyen/Kamera_1` (importen fik aldrig genereret thumbnails). Alle andre
  kameraer har fuld dækning.
- Peters pointe bekræftet: auto-repair FINDES (`<img onError={requestRepair}>` → POST
  `/api/thumbnails/.../generate` → retry). MEN den er UDEN samtidigheds-grænse: et galleri med
  ~133 manglende/dag fyrer 100+ samtidige genereringer (hver læser et fuldopløst billede fra
  data-fast) → thundering herd → de fleste timeout'er inden for 8 s → tom ramme. Virker for ét
  enkelt miss, kollapser for et helt kamera.
- Fix 1 (CLI-backfill, ny): `headend/tools/backfill_thumbnails.py` — ren filsystem-walk, frisk
  proces (ingen 504/genstart), samme format (320×180 q78 → `.thumbs/`), `--path` til ét kamera,
  `--workers` (default 3), `--dry-run`. Kør:
  `~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/tools/backfill_thumbnails.py --path /Volumes/data-fast/timelapse-incoming/canonical-images/Kirkbi_A_S/Travbyen`
- Fix 2 (permanent, kræver genstart): `get_thumbnail` genererer nu VED MISS (cache til
  `.headend-thumbs/`, `X-Thumbnail-Source: headend-lazy`) i stedet for 404, og BÅDE denne og det
  eksisterende POST-repair går nu gennem en GLOBAL `BoundedSemaphore` (env
  `TIMELAPSE_THUMBNAIL_GEN_CONCURRENCY`, default 3) → ingen thundering herd. Lazy kan slås fra med
  `TIMELAPSE_THUMBNAIL_LAZY_GENERATE=false`. py_compile grøn.
- Filer rørt: `headend/main.py` (semaphore + `_lazy_generate_thumbnail` + get_thumbnail + POST-tråd),
  `headend/tools/backfill_thumbnails.py` (ny).

### Handover 2026-06-30 — fra Codex til Peter/Claude (Edge AI MobileNet smoke kører på Orange Pi)
- Local Edge QA er løftet fra mikro-CNN smoke til `mobilenet_v2` transfer-learning smoke:
  `best_val_accuracy=0.88`, `test_accuracy≈0.803` på 611-rækkers balanced smoke-manifest.
- Model-artifacts:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321/model-mobilenet-v1-preload-smoke`
  (`edge_qa_model.onnx`, `edge_qa_model.onnx.data`, metadata, train.log).
- Stærke testklasser: `blurry=1.0`, `underexposed=1.0`, `direct_sun_reflection=0.875`.
  Svage klasser der skal have review/bedre labels før autonom drift: `overexposed`, `depth_of_field_issue`, `ok`.
- Orange Pi `timelapse0101` er verificeret med ONNX Runtime CPU:
  - `/opt/timelapse/venv` har nu `onnxruntime`
  - model ligger som `/opt/timelapse/models/edge_qa_model_v1_mobilenet_smoke.onnx`
  - ekstern ONNX-datafil ligger i `/opt/timelapse/models/edge_qa_model.onnx.data`
  - runner/kontraktkode er opdateret under `/opt/timelapse/edge/...`
  - `edge_qa_npu_runner.py --model ... --image ... --json` returnerer gyldig
    `timelapse.edge_qa.v1` med `engine=edge_onnxruntime_local`, `available=true`.
- NPU-status: Orange Pi NPU/VIPLite kæden er stadig OK (`/dev/vipcore`, ai-sdk, ResNet `.nb`
  demo). MobileNet-modellen er IKKE konverteret til `.nb` endnu; Docker daemon kørte ikke på Mac
  ved ACUITY-forsøg. Næste tekniske milepæl er ACUITY-konvertering af MobileNet-ONNX til `.nb`.
- Driftsvalg: brug MobileNet-smoke som integrationstest/assist-signal. CPU/OpenCV optimizer skal
  stadig være autoritativ fallback. Første sikre mode er `quality.edge_ai.mode=assist`; vent med
  `npu_first/autonomous` til human-reviewed v2 og `.nb` er verificeret.
- Baggrundsjob kører fortsat:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-full-20260630-112714`
  (`screen -r timelapse-edge-qa-full`, `full-mining.log`) for fuld historik-mining.

### Handover 2026-06-30 — fra Codex til Peter/Claude (NPU-afklaring: ONNX er ikke nok)
- Peters spørgsmål er korrekt: produktion skal køre på NPU'en. ONNX Runtime på Orange Pi er kun
  integrationstest/fallback; Allwinner/VIPLite kræver `.nb`.
- A733 SDK siger `NPU_VERSION=v3` (`VIP9000NANODI_PLUS_PID0X1000003B` via
  `pegasus_setup.sh v3`).
- Der er bygget ACUITY workspace for MobileNet-smoke:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321/acuity-edge-qa-mobilenet-smoke/edge_qa_model`
  og bundle:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321/acuity-edge-qa-mobilenet-smoke.tar.gz`.
- Workspace er kopieret til Orange Pi:
  `/opt/timelapse/ai-sdk/models/edge_qa_model` med ONNX, ekstern `.onnx.data`,
  `inputs_outputs.txt`, `channel_mean_value.txt`, `dataset.txt` og 155 kalibreringsbilleder.
- Importforsøg på Orange Pi stopper på `Need to set environment variable ACUITY_PATH`. Konklusion:
  boardet har runtime-SDK, VIPLite, scripts og NPU-driver, men ikke selve ACUITY/pegasus compiler.
  Docker på Mac er nu startet, men der findes kun `ubuntu:22.04`; ingen `ubuntu-npu`/ACUITY image
  lokalt. Downloads indeholder `ai-sdk.tar`, ikke en synlig ACUITY compiler-image.
- Nyt værktøj: `edge/tools/prepare_acuity_workspace.py`.
- Næste konkrete krav før ægte NPU QA: fremskaf/load Allwinner ACUITY toolkit eller Docker image,
  sæt `ACUITY_PATH`, kør `pegasus_import/quantize/inference/export_ovx_nbg`, installer resultatet
  som `/opt/timelapse/models/edge_qa.nb`, og test med
  `/opt/timelapse/bin/edge_qa_viplite --input-layout nchw_rgb`.
