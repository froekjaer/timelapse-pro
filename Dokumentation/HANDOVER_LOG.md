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
