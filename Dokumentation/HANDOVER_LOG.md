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

### Handover 2026-07-03 10:55 — fra Codex til ny Claude-session/Peter
- Hvad er gjort: Peter bad om at få alt committet før sessionskift. Det relevante arbejde er nu
  committet på `codex/edge-npu-qa`.
- Commits:
  - `9340aed docs: consolidate v10 handover and operations references`
  - `d7a952d chore: checkpoint code operations and edge work`
- Bevidst ucommittet/lokalt: `.base_image_cache/`, `.claude_proxy/`, `artifacts/`,
  `headend/.webui_secret_key`, `dokumentation.tar.gz`, `timelapse-pro-doc.gz` og
  `Dokumentation/.~lock.KRAVREGISTER_og_STATUS_v10.md#`. De er caches/artifacts/secrets/lockfiles
  og skal ikke ind i Git.
- Verifikation før commit: `npm run build` grøn, `nginx -t` grøn, headend `200`, UI `200`, nginx
  `301`, WiFi-watchdog logger router reachable.
- Risici / pas på: De to commits er store checkpoints med blandet Claude/Codex-arbejde. De er
  lavet for at undgå tab før sessionskift; senere kan vi splitte/PR-reviewe mere fint, hvis det
  bliver nødvendigt.

### Handover 2026-07-03 10:35 — fra Codex til ny Claude-session/Peter
- Hvad er gjort: Læst `Dokumentation/HANDOVER_2026-07-02_Claude_session.md` og
  `Dokumentation/00_START_HER.md`. Bekræftet at Codex' V11-relaterede commits `260122c` og
  `99bff9b` allerede ligger på `codex/edge-npu-qa`; de er review-/valideringsnotater, ikke en
  komplet `*_v11.md` dokumentpakke. Claudes v10-konsolidering ligger stadig som stort uncommitted
  dokument-spor og skal reconciles bevidst før bredt commit.
- Deploy udført: `npm run build` i `timelapse-ui` er grøn. Live nginx har fået specifik
  `location /api/import/` med `client_max_body_size 1024m`, `nginx -t` er grøn, og nginx er
  kickstartet som system-LaunchDaemon. Headend er kickstartet som
  `system/dk.froekjaer.timelapse-headend`.
- Verifikation: `headend 200`, `ui 200`, `nginx 301`; PostgreSQL/nginx/headend/UI kører som
  systemservices. WiFi-watchdoggen logger fortsat at `en1` har IP og router `192.168.86.1` er
  reachable.
- Gemini-backlog: DB-count for captures uden `ai_tags` siden `2026-06-29 12:00` = 22. Dry-run af
  `ai_batch_submit.py --since "2026-06-29 12:00" --no-context --dry-run` viser 22 billeder,
  0 manglende filer og 1 batch-job. Intet er indsendt, fordi det koster/kalder Vertex.
- Filer rørt: `Dokumentation/HANDOVER_2026-07-02_Claude_session.md`,
  `Dokumentation/00_START_HER.md`, `Dokumentation/HANDOVER_LOG.md`, live
  `/opt/homebrew/etc/nginx/nginx.conf` (backup taget), samt tidligere Mac/WiFi launchd-artefakter.
- Risici / pas på: Arbejdstræet er stadig meget beskidt og har 0 staged filer. Brug ikke bredt
  commit uden først at adskille v10-dokumentkonsolidering, Claudes kodefixes og Codex'
  drift/launchd-artefakter.

### Handover 2026-07-03 10:15 — fra Codex til Peter/Claude
- Hvad er gjort: Undersøgt Mac Mini kernel panic. Panicloggen viser `watchdog timeout: no
  checkins from watchdogd in 90 seconds`, samtidig med `Compressor Info ... 100% of segments
  limit (BAD) with 32 swapfiles and LOW swap space`. CPU-listen pegede på `kernel_task`,
  `docker-agent` og `com.apple.Virtualization.Virtual`; senest startede kext var `smbfs`.
  Mest sandsynlige årsag er system-hang under kraftig memory/swap pressure, muligvis forværret af
  Docker/Virtualization og/eller SMB/NAS-I/O, ikke en almindelig headend-app-crash.
- Hvad er gjort: Sat Mac'en mere serveragtigt op: `Restart After Power Failure: On`,
  `Restart After Freeze: On`, `sleep 0`, `disksleep 0`, WOL/tcpkeepalive aktive. Installeret
  system-LaunchDaemons for PostgreSQL, nginx, headend og UI, plus
  `/usr/local/sbin/timelapse-headend-start`, som venter på `/Volumes/data-fast` og PostgreSQL før
  uvicorn startes. Runtime-env ligger lokalt i `/etc/timelapse/headend.env` og ikke i Git. De
  gamle bruger-LaunchAgents for headend/UI/nginx/PostgreSQL er omdøbt til `.disabled-20260703-*`,
  så de ikke starter dobbelt ved næste GUI-login.
- Hvad er gjort: WiFi er sat som første netværksservice, og
  `dk.froekjaer.timelapse-wifi-ensure` er installeret som system-LaunchDaemon. Den kører ved boot
  og hvert minut, tjekker `en1` + router `192.168.86.1`, og forsøger re-join til `p-froekjaer`.
- Kommandoer kørt eller skal køres: verificeret med
  `launchctl print system/dk.froekjaer.timelapse-headend`,
  `launchctl print system/dk.froekjaer.timelapse-postgresql`,
  `launchctl print system/dk.froekjaer.timelapse-nginx`,
  `curl http://127.0.0.1:8000/api/health`.
- Forventet/faktisk output: system-services kører som user `peter`; listeners på `5432`, `80`,
  `443`, `8000`, `5173`; headend `200`, UI `200`, nginx `301`.
- Filer rørt: `deploy/macos/timelapse-headend-start.sh`,
  `deploy/macos/timelapse-wifi-ensure.sh`,
  `deploy/launchd/macos/dk.froekjaer.timelapse-*.plist`,
  `Dokumentation/SERVICES_OG_DRIFT_kilde_til_sandhed.md`,
  `Dokumentation/FAQ_og_fejlsøgning.md`,
  `Dokumentation/HANDOVER_Claude_Codex_arbejdsdeling.md`.
- Risici / pas på: FileVault er On. Efter rigtigt strømudfald kan maskinen stadig kræve manuel
  FileVault-unlock før normal WiFi, volumes og LaunchDaemons bliver tilgængelige. Fuld unattended
  recovery kræver en bevidst FileVault-beslutning og helst kablet net.

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

### Handover 2026-06-29 — fra Claude til Peter/Codex (thumbnails: 503 = backend-overbelastning)
- ENDELIG diagnose (via browser-konsol): Frøkjær-thumbnails fejler med **HTTP 503 Service
  Temporarily Unavailable** — IKKE 404. Filerne + thumbnails FINDES (verificeret: 15/15 nyeste
  captures OK). 503 = nginx/uvicorn er overbelastet. Mekanisme: tæt galleri (Frøkjær ~144/dag)
  fyrer 100+ samtidige thumbnail-GET → sync-endpoints mætter uvicorns trådpulje → nginx 503 → hver
  503 trigger `<img onError>` → POST `/generate` → 100+ TUNGE kald (fuldopløst billede-læs) →
  selvforstærkende storm, serveren kommer ikke op. (`_find_image` er allerede lru-cachet, så det er
  ikke synderen.)
- Travbyen-omvejen: `_dup`-filer var forældreløse dubletter (ingen DB-rækker); de rigtige
  capture-filer havde thumbnails hele tiden. Travbyen-galleriet blev bedre fordi det er sparsomt
  (få samtidige requests); Frøkjær kollapser fordi det er tæt.
- Fix 1 (frontend, gjort): `CaptureThumbnailCard` prøver nu den EKSISTERENDE thumbnail igen med
  jittered backoff (4×) ved fejl, i stedet for straks at fyre `/generate`. Da thumbnailen findes,
  lykkes genforsøget når serveren får luft → generate-stormen opstår ikke. `tsc -b` grøn.
- Fix 2 (backend, bygget tidligere, kræver genstart): global `BoundedSemaphore` på
  thumbnail-generering (lazy GET + POST-repair) → ingen herd af tunge genereringer.
- **DEN ÆGTE FIX (Codex/infra):** 503 er nginx. Tjek `limit_req`/`limit_conn` på `/api/` — en
  burst på 100+ thumbnail-requests sprænger sandsynligvis en for lav rate-limit (nginx svarer 503
  default). Anbefaling: enten hæv/undtag `/api/thumbnails/` fra rate-limit, ELLER (bedst) server
  thumbnails via **X-Accel-Redirect** (Python laver auth + resolver sti, returnerer header, nginx
  sender filen → frigør uvicorn-workeren straks) eller en statisk nginx-location. Plus evt. flere
  uvicorn-workers/trådpulje. Det fjerner loftet; frontend+semaphore er mitigering.
- Filer rørt: `timelapse-ui/src/components/CaptureThumbnailCard.tsx` (retry-backoff),
  `headend/main.py` (semaphore + lazy-gen, tidligere note), `headend/tools/backfill_thumbnails.py`.

### Handover 2026-07-01 — fra Claude til Peter (Timelapse Video virtualisering + tag-oversættelse)
- **Timelapse Video "gik i kludder" ved lange perioder (21.000 frames)** — REGRESSION fra
  thumbnail-gaten: `CaptureThumbnailCard` fik en IntersectionObserver + `animate-pulse`-placeholder
  PR. KORT → 21.000 observers + 21.000 CSS-animationer væltede browseren. Rettet i tre trin:
  (1) ÉN delt IntersectionObserver (`observeInView` i `imageLoadGate.ts`) i stedet for én pr. kort;
  (2) statisk placeholder (ingen `animate-pulse`);
  (3) NY **`VirtualImageGrid`** (afhængighedsfri, vindues-scroll, måler via getBoundingClientRect)
  — `TimelapseVideoPage` renderer nu KUN synlige frames i stedet for alle 21.000. `tsc -b` grøn.
  Deploy: `npm run build` + hård reload.
- **Tags var engelske i Tag søgning** — TO årsager: (a) `TagSearchPage` viste rå `#{t.tag}` i
  søgefelt/forslag/tag-cloud i stedet for `tagLabel(...)` — RETTET (result-kortene brugte det
  allerede); (b) `display_name_da` er tom for mange tags (især nye fra bulk-re-tag), så
  `/api/ai/vocabulary/translations` returnerer dem ikke → NY script
  `headend/ai/backfill_tag_translations.py` fylder dansk fra `PREDEFINED_DA_LABELS` (~386 tags).
  Kør: `~/.venvs/timelapse-headend/bin/python headend/ai/backfill_tag_translations.py --apply`
  (dry-run uden `--apply`). py_compile grøn. Tags uden predefineret dansk forbliver engelske
  (kan oversættes i Tag Review / senere AI-pass).
- Filer rørt: `timelapse-ui/src/components/VirtualImageGrid.tsx` (ny),
  `timelapse-ui/src/components/CaptureThumbnailCard.tsx` (delt observer + statisk placeholder),
  `timelapse-ui/src/lib/imageLoadGate.ts` (observeInView + gate uden rate-throttle, MAX 12),
  `timelapse-ui/src/pages/TimelapseVideoPage.tsx` (VirtualImageGrid),
  `timelapse-ui/src/pages/TagSearchPage.tsx` (tagLabel i chips),
  `headend/ai/backfill_tag_translations.py` (ny).

### Handover 2026-07-01 — fra Claude til Codex/Peter (BUG: edge-QA blokerer Gemini-analyse)
- **Symptom:** Ingen Gemini-AI-data på captures siden ~29/6 12:00; billeder viser kun edge-QA
  (fx "depth_of_field_issue, konfidence 76%") + gul advarselstrekant.
- **ROD-ÅRSAG (bekræftet i kode):**
  1. Ved capture-upload skriver headenden edgens QA i `ai_result`:
     `main.py` ~linje 3298 og ~3511: `if req.edge_ai_result and not capture.ai_result:
     capture.ai_result = json.dumps({**edge_ai_result, "source":"edge", ...})`.
  2. Den live AI-worker springer over ALT med `ai_result` sat:
     `integration.py` ~linje 328: `if capture.ai_result: skip`.
  → Da Codex' edge-QA gik live (~29/6 12:00) begyndte nye captures at ankomme med edge-QA i
  `ai_result` → Gemini-workeren springer dem over → ingen Gemini-tags. (Basale flag som
  `quality_flag`/`quality_passed` overlever i egne kolonner; kun Gemini-tags mangler.)
- **Foreslået fix (afventer Peters/Codex' go — Gemini-omkostning + rører edge-QA-kontrakten):**
  - Headend-worker: skip kun hvis `ai_result` er en RIGTIG analyse — ikke edge-QA. Fx:
    `if capture.ai_result and json.loads(capture.ai_result).get("source") != "edge" and capture.ai_tags: skip`.
    Så kører Gemini på edge-QA-captures. Bevar edge-QA under en `edge_ai`-nøgle (eller læs den
    fra kolonnerne) når Gemini skriver `ai_result`, så intet går tabt.
  - Backlog (29/6→nu): kør en Gemini-pass (post-processing/batch) på perioden for at hente de
    manglende tags — det koster Gemini-kald (som før 29/6).
  - ALTERNATIV (renere, Codex' bord): lad IKKE edgen skrive i `ai_result`; gem edge-QA i et
    separat felt/`edge_qa_signal` (jf. §8-aftalen), så `ai_result` er reserveret Gemini.
- Claude kan implementere headend-fixet på 10 min når retningen er valgt.

### Handover 2026-07-02 — fra Codex til Peter/Claude (Orange Pi Edge QA NPU kører, kalibrering udestår)
- ACUITY/Docker-sporet er nu igennem på Mac:
  - Docker image: `ubuntu-npu:v2.0.10.2`
  - ACUITY: 6.30.22
  - target: Orange Pi 4 Pro A733 / VIP9000NANODI_PLUS_PID0X1000003B / `v3`
- MobileNet smoke-modellen skulle re-eksporteres som legacy ONNX opset 13 (`dynamo=False`).
  PyTorch 2.9/dynamo-export gav opset 18, som ACUITY importerede forkert.
- `pegasus_import` og `pegasus_quantize` kører rent. `.nb` blev genereret via
  `VIV_VX_ENABLE_SAVE_NETWORK_BINARY=1` i Vivante simulatoren; direkte `vxGenerateNBG()`/wrapper
  crashede i denne SDK-version.
- Installeret på `timelapse0101`:
  - `/opt/timelapse/models/edge_qa.nb`
  - sha256 `773c9986d8997ce01977e865ab2a4e64b777813d025ecfc090b7af9e582d963d`
- VIPLite-wrapperen er rettet:
  - input til den nye `.nb` er FP16, ikke `uint8`; tidligere wrapper sendte 150.528 bytes, mens
    NBG-inputbufferen er 301.056 bytes, hvilket gav segfault.
  - wrapperen laver nu FP16-preprocess og kan køre `nchw_rgb`, `nchw_bgr` og `nhwc_rgb`.
  - `edge_qa_npu_runner.py` parser vendor-output robust og returnerer `timelapse.edge_qa.v1`
    med `available=true`.
- Live-test på Orange Pi:
  - `/opt/timelapse/bin/edge_qa_viplite --model /opt/timelapse/models/edge_qa.nb --image /tmp/edge-qa-smoke.jpg --json --input-layout nchw_rgb --classes 9`
  - NPU `vip_run_network` omkring 2-3 ms.
  - Python-runneren returnerer gyldig kontrakt via vendor binary.
- Vigtigt forbehold: NPU-runtime er nu på plads, men kvantiseret output matcher endnu ikke ONNX
  CPU-baseline tæt nok. Dette skal betragtes som integrationstest/assist-signal, ikke autonom
  QA-beslutning, indtil v2 calibration/export er valideret på bred historik.
- Næste AI-opgave:
  1. Byg et eval-script der sammenligner ONNX CPU vs `.nb` NPU på 100-500 kendte billeder.
  2. Juster ACUITY inputmeta/calibration/præprocessering, så topklasse og scorefordeling matcher.
  3. Først derefter sættes `quality.edge_ai.mode=npu_first`; indtil da bruges `assist` + CPU/OpenCV
     fallback.

### Analyse 2026-07-02 — ONNX CPU vs Orange Pi NPU parity
- Nyt eval-script: `edge/tools/evaluate_edge_qa_npu_parity.py`.
- 50-billeders sample mod live Orange Pi/NPU:
  - summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-090636_summary.json`
  - JSONL: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-090636.jsonl`
  - `top1_match_rate=0.36`
  - mean MAE `0.1142`
  - mean cosine `0.5870`
  - mean KL CPU→NPU `0.8567`
- Input sweep på 20 billeder viser at `nchw_rgb` med default `1/255` fortsat er bedste kontrakt
  blandt de testede. `nchw_bgr` har cirka samme distance men lavere top-1 match; `nhwc_rgb` og
  scale `1.0` er dårligere.
- Fejlmønster: `.nb`/NPU har kraftig bias mod `blurry`. Den rammer mange egentlige `blurry`, men
  mister især `underexposed`, `depth_of_field_issue`, `ok` og en del `overexposed`.
- Konklusion: runtime er god, men modellen/kvantiseringen er ikke god nok til autonom drift. Næste
  runde bør være ny ACUITY-export med bedre calibration/inputmeta, evt. en modelvariant hvor
  normalisering håndteres eksplicit uden at ACUITY skal kvantisere PyTorch Normalize-subgrafen.

### Arbejde i gang 2026-07-02 — Edge QA v2 NPU-model
- Codex arbejder videre på en NPU-venlig v2-model til Orange Pi 4 Pro.
- Træningsscriptet `edge/training/train_edge_qa_model.py` er udvidet med
  `--export-normalization absorbed`:
  - modellen kan stadig trænes/evalueres med ImageNet-normalisering,
  - men ved ONNX-export foldes normaliseringen ind i første MobileNet-convolution,
  - og `torch.onnx.export(..., dynamo=False, opset_version=13)` fastholder ACUITY-kompatibel
    legacy ONNX.
- Smoke-export verificeret:
  - `artifacts/edge-qa-training/edge-qa-v2-npu-smoke-20260702-094604/edge_qa_model.onnx`
  - opset 13, NCHW input `batch,3,224,224`
  - grafen har `Conv/Clip/Add/GlobalAveragePool/Flatten/Gemm` og ingen separat Normalize-subgraf.
- Nyt v2-datageneratorværktøj:
  - `edge/tools/generate_edge_qa_v2_manifest.py`
  - bygger balanceret manifest og reproducerbare syntetiske fotofejl for underdækkede klasser.
- Nyt v2-datasæt:
  - run-dir: `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056`
  - manifest: `edge-qa-v2-balanced-manifest.jsonl`
  - 10.800 rows, 1.200 pr. klasse.
  - syntetiske fills:
    - `blurry`: 359
    - `snow_or_dirt_on_lens`: 1.200
    - `condensation`: 1.200
    - `white_balance_cast`: 1.180
- Træning er startet i samme run-dir:
  - output: `model-mobilenet-v2-npu-absorbed-full`
  - command: MobileNetV2 pretrained, full fine-tune, 10 epochs, batch 48, lr 0.0002,
    `--export-normalization absorbed`.
- Efter træning:
  1. Verificer ONNX opset og testmetrics.
  2. Forbered ACUITY workspace fra v2-manifestet.
  3. Kør `pegasus_import`, `pegasus_quantize`, simulator/NBG-export.
  4. Installer som ny `/opt/timelapse/models/edge_qa.nb` på Orange Pi.
  5. Kør `evaluate_edge_qa_npu_parity.py` igen mod live NPU og hold mode i `assist`, indtil parity
     og billedfaglig adfærd er god nok.

### Status 2026-07-02 — NPU-kæden virker, MobileNetV2 gør ikke
- MobileNetV2 v2-modellen trænede godt på CPU/ONNX:
  - run-dir: `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056`
  - ONNX: `model-mobilenet-v2-npu-absorbed-full/edge_qa_model.onnx`
  - test accuracy: `0.9655`
- ACUITY/VIPLite-exporten af MobileNetV2 er stadig uegnet:
  - installeret kandidat: `/opt/timelapse/models/edge_qa_v2.nb`
  - RGB-reexport-kandidat: `/opt/timelapse/models/edge_qa_v2_rgb.nb`
  - begge låser i praksis på `blurry` i ONNX-vs-NPU parity.
- VIPLite-wrapperen er nu udvidet og installeret på Orange Pi:
  - `/opt/timelapse/bin/edge_qa_viplite`
  - backup: `/opt/timelapse/bin/edge_qa_viplite.bak-20260702-114945`
  - understøtter `--input-dtype fp16|uint8`
  - v1 `fp16` regression er testet OK.
- Bevis for at NPU-kæden virker:
  - ny NPU-venlig `simple_cnn`-mini model uden depthwise conv/BatchNorm-kompleksitet.
  - ONNX: `model-simple-cnn-mini-npu-rgb/edge_qa_model.onnx`
  - NPU: `/opt/timelapse/models/edge_qa_simple_mini.nb`
  - sha256 `3af381b14bfb8de8431441f85448b26fa8f541996162447298a04d219102a0eb`
  - parity summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-114804_summary.json`
  - 12-image parity: top-1 match `0.9167`, mean MAE `0.0032`, mean cosine `0.9994`.
- Vigtigt: `simple_cnn`-mini er kun en teknisk parity-probe, ikke produktionsmodel:
  - mini-træning på 2.700 billeder gav test accuracy cirka `0.507`.
  - næste rigtige spor er en bedre NPU-venlig standard-conv model med mere kapacitet og fuld træning.
- Anbefalet næste step:
  1. Behold wrapperens nye `uint8` support.
  2. Træn en større NPU-venlig standard-conv model på hele v2-manifestet.
  3. Brug `edge_qa_simple_mini.nb` kun til runtime/parity-regression.
  4. Sæt ikke MobileNetV2 `.nb` i autonom drift.

### Status 2026-07-02 — Edge CNN NPU-baseline virker
- Codex har tilføjet en større, men stadig ACUITY-venlig `edge_cnn`-arkitektur:
  - kun standard `Conv/ReLU/MaxPool/GlobalAveragePool/Flatten/Gemm`
  - ingen depthwise convolutions og ingen BatchNorm-subgraf i ONNX-exporten
  - inputkontrakt: `nchw_rgb`, `uint8`, 224x224, classes=9
- Mini-træning på v2 mini-manifestet:
  - ONNX: `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/model-edge-cnn-mini-npu-rgb/edge_qa_model.onnx`
  - best val accuracy: `0.8741`
  - test accuracy: `0.8370`
- ACUITY/VIPLite-exporten er installeret side-by-side på Orange Pi:
  - NPU-model: `/opt/timelapse/models/edge_qa_edge_cnn_mini.nb`
  - sha256: `d98274bdf7bf36745300cbf8da4ebc2e07a1c95f62b6c0e21b86f247ca8eda24`
  - wrapper: `/opt/timelapse/bin/edge_qa_viplite --input-layout nchw_rgb --input-dtype uint8`
- ONNX-vs-NPU parity på 20 rigtige historiske billeder:
  - summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-121903_summary.json`
  - JSONL: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-121903.jsonl`
  - top-1 match: `1.0000`
  - mean MAE: `0.0053`
  - mean cosine: `0.9985`
  - failures: `0`
- Konklusion: NPU-runtime og ACUITY-export er nu bevist med en modeltype, der også har nyttig
  billedfaglig signalværdi. Mini-modellen bør stadig holdes i `assist`/test, men den er en
  reel kandidatbase for produktion.
- Arbejde i gang:
  - fuld `edge_cnn`-træning på `edge-qa-v2-balanced-manifest.jsonl` er startet i
    `model-edge-cnn-full-npu-rgb`.
  - næste trin er ACUITY-export, installation som ny kandidat, bredere parity og derefter
    konfigurationsbinding til global/kunde/site/kamera AI modes.

### Beslutning 2026-07-02 — Real-world eval-suiter
- Peter præciserede at Travbyen er den mest virkelighedsnære kundecase:
  - 4-5 års billeder.
  - alle årstider.
  - primært dagslys.
  - ikke taget gennem stuevindue.
- Frøkjær/Nordre Villavej bruges fremover mere selektivt:
  - dagslys gennem stuevindue er ikke egnet som primær kundesandhed.
  - tidsrummet 01:00-05:59 er nyttigt som nat-/underbelysningssuite.
- Nyt reproducerbart værktøj:
  - `edge/tools/build_edge_qa_eval_suites.py`
  - bygger eval-manifester fra v2-manifestet.
- Aktuelle eval-suiter:
  - Travbyen dagslys real-world:
    `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/edge-qa-v2-travbyen-daylight-realworld-manifest.jsonl`
    - 1.361 historiske billeder.
    - labels: `blurry=635`, `direct_sun_reflection=446`, `overexposed=278`, `white_balance_cast=2`.
  - Frøkjær nat 01:00-05:59:
    `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/edge-qa-v2-froekjaer-night-0100-0559-manifest.jsonl`
    - 1.438 historiske billeder.
    - labels: `depth_of_field_issue=694`, `underexposed=404`, `blurry=154`, `ok=135`,
      samt få sol/overeksponering/hvidbalance cases.
- `edge/tools/evaluate_edge_qa_npu_parity.py` kan nu tage `--manifest` og rapporterer både:
  - ONNX-vs-NPU parity.
  - match mod manifestets forventede label, når manifestet har label.
- Mini `edge_cnn` NPU-baseline på de nye eval-suiter:
  - Travbyen 30-sample:
    - summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-124722_summary.json`
    - top-1 ONNX-vs-NPU: `1.0000`
    - mean cosine: `0.9982`
    - expected-label match: `0.7667`
  - Frøkjær nat 30-sample:
    - summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-125144_summary.json`
    - top-1 ONNX-vs-NPU: `1.0000`
    - mean cosine: `0.9998`
    - expected-label match: `0.8667`
- Fortolkning:
  - NPU-runtime er nu stabil på begge relevante suiter.
  - Expected-label mismatch skyldes især at historiske CPU-QA labels ikke altid er
    fototeknisk sandhed, fx overeksponering vs direkte solrefleks vs hvidbalance.
  - Næste modelrunde bør bruge Travbyen som primær real-world accept og Frøkjær 01-05 som
    nat/low-light accept, plus en manuel reviewliste for label-konflikter.
- Datakvalitetsfund samme runde:
  - Det oprindelige v2-manifest indeholdt 35 thumbnail-rækker, bl.a. under `.headend-thumbs`.
  - `edge/training/train_edge_qa_model.py`, `build_edge_qa_eval_suites.py` og
    `evaluate_edge_qa_npu_parity.py` filtrerer nu alle path parts med `thumb`.
  - Regenereret holdout-træningsmanifest:
    - 7.967 rækker.
    - 0 thumbnail-rækker.
    - alle 9 klasser stadig repræsenteret.
- Arbejde i gang:
  - ny `edge_cnn` holdout-træning:
    `model-edge-cnn-holdout-lr3e4-npu-rgb`
  - trænes med `lr=0.0003`, 14 epochs, Travbyen + Frøkjær nat holdt ude.

### Resultat 2026-07-02 — Holdout-model må ikke driftsættes
- Holdout-træning færdig:
  - model-dir:
    `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/model-edge-cnn-holdout-lr3e4-npu-rgb`
  - best validation accuracy: `0.9401`
  - intern test accuracy: `0.9157`
- Men fuld ONNX-evaluering på Travbyen real-world holdout viser domain gap:
  - summary:
    `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/edge-qa-v2-travbyen-daylight-realworld-manifest-onnx-holdout-summary.json`
  - rows: `1.361`
  - failed: `0`
  - expected-label match: `0.1381`
- Confusion viser tydelig syntetisk bias:
  - mange Travbyen `blurry` bliver `condensation`.
  - mange `direct_sun_reflection` bliver `blurry`.
  - mange `overexposed` bliver `snow_or_dirt_on_lens`.
- Fortolkning:
  - Interne metrics på syntetisk/balanceret data er ikke nok.
  - Holdout-modellen er teknisk god, men ikke fototeknisk god nok på Travbyen.
  - Den skal ikke eksporteres til `.nb` eller bruges som NPU-kandidat.
- Næste modelrunde:
  - reducer syntetiske `condensation`/`snow_or_dirt_on_lens` cases kraftigt eller giv dem lavere vægt.
  - brug Travbyen som aktiv real-world træningsdomæne, men med review af svage labels.
  - lav en reviewliste for Travbyen-konflikter, især:
    `blurry` vs `condensation`, `direct_sun_reflection` vs `overexposed`, og `snow_or_dirt_on_lens`.
  - behold mini `edge_cnn` som NPU parity baseline indtil en real-world model slår Travbyen-suiten.

### Status 2026-07-02 — Real-world-only og små JPEGs tagget
- Beslutning efter Peters input:
  - næste QA-modelspor skal være real-world-first.
  - syntetiske `snow/condensation`-eksempler må ikke dominere, fordi produktmålet er at opdage
    dårlige billeder og frontglas-/linsecover-problemer på rigtige kundebilleder.
- `edge/tools/build_edge_qa_eval_suites.py` bygger nu også:
  - `edge-qa-v2-realworld-only-manifest.jsonl`
  - aktuelt 6.826 historiske billeder, 0 syntetiske, 0 thumbnail paths.
- Reelt datagrundlag i real-world-only manifestet:
  - `depth_of_field_issue=1200`
  - `ok=1200`
  - `underexposed=1200`
  - `overexposed=1199`
  - `direct_sun_reflection=1167`
  - `blurry=841`
  - `white_balance_cast=19`
  - ingen ægte `snow_or_dirt_on_lens`/`condensation` i dette manifest.
- 41 små Travbyen originalfiler under 200 KB blev fundet i canonical-strukturen:
  - ingen er thumbnails.
  - alle ligger i original/canonical paths.
  - mange giver `Premature end of JPEG file` warnings og bør reviewes/slettes/repareres.
- DB tagging udført:
  - tag: `qa_review_small_or_truncated_original`
  - tag: `qa_review_possible_bad_jpeg`
  - 9 unikke `captures` i PostgreSQL blev tagget.
  - de 41 filer mapper til disse 9 DB-captures plus 1 fil uden DB-match; mange er `_dup...`
    filsystemdubletter uden egen capture-række.
  - review-liste:
    `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/small-or-truncated-originals-review-20260702.json`
- Real-world-only træning blev forsøgt med `edge_cnn`, `lr=0.0003`, men stoppet:
  - epoch 1-2 lå ca. `0.85-0.86` validation accuracy.
  - epoch 3 kollapsede til ca. `0.45`, epoch 4 ca. `0.76`.
  - konklusion: genstart med lavere LR og/eller en reduceret klassekontrakt, hvor klasser uden nok
    real-world data ikke trænes som ligeværdige outputklasser.

### Codex review 2026-07-02 — dokumentationsstyring og v11
- Peter bad Codex give "sidste ord" på Claudes plan om at gøre dokumentationsmappen til et
  stabilt referencegrundlag for nye sessioner.
- Codex' anbefaling er skrevet i:
  `Dokumentation/Codex_Dokumentationsstyring_Review_2026-07-02.md`
- Kort konklusion:
  - Ja til `00_START_HER.md` som session-anchor og én seneste `.md` pr. dokument.
  - Nej til mekanisk v11-bump af alle dokumenter uden kode-/driftsvalidering.
  - Ja til manifest-styret v11-runde dokument-for-dokument.
  - RPi5/headend-historik skal arkiveres/markeres historisk, ikke blandes ind som aktiv sandhed.
  - Canon EOS 1000/1300/2000 og Nikon Z30 bør beskrives som supportmatrix, ikke som gensidigt
    udelukkende spor.

### Codex validering 2026-07-02 — kode/drift før v11
- Peter bad om kode-/driftsvalidering før dokumenter løftes til v11.
- Valideringsnotat er skrevet i:
  `Dokumentation/Codex_Kode_Drift_Validering_for_v11_2026-07-02.md`
- Live bekræftet:
  - headend API er sund på `127.0.0.1:8000`.
  - UI dev server, nginx, PostgreSQL, Ollama, syslog receiver og reverse SSH-forwarding kører.
  - Orange Pi `timelapse0101` svarer på SSH; `timelapse-edge` er aktiv.
  - NPU-wrapper og `.nb` modeller findes på Orange Pi.
  - SFTP DB-settings peger på `/Volumes/data-fast/timelapse-incoming/canonical-images`.
- Vigtige v11-forbehold:
  - nginx lytter stadig offentligt på `*:80` og `*:443`; prod-portmodellen må ikke beskrives som aktiv.
  - 0 brugere har MFA slået til.
  - Orange Pi `timelapse-node-agent` er inaktiv; kun `timelapse-edge` er aktiv der.
  - aktiv edge-device mangler `hardware_model` og `camera_model` i `devices`.
  - UI har stadig hardcoded `Kamera - Canon EOS 1300D` i DevicePage.
  - NPU-runtime er etableret, men production QA-model er stadig under real-world tuning.

### Codex 2026-07-02 — MFA reset og hierarkisk MFA policy
- Peters halve MFA-state blev fundet og nulstillet:
  - før: `mfa_enabled=false`, men `totp_secret` var stadig sat.
  - efter: `mfa_enabled=false`, `totp_secret=null`.
- Headend MFA-runtime manglede `pyotp` og `qrcode`; de er installeret i live-venv og tilføjet til
  `headend/requirements.txt`.
- Kodeændringer:
  - `ConfigDefaults.session_policy` er nu SQLAlchemy-modelkolonne.
  - startup-migration sikrer `config_defaults.session_policy`.
  - default session policy kræver MFA for `super_admin` og `admin`, men ikke for `operator`/`viewer`.
  - session policy resolves hierarkisk: global → kunde → site → kamera, med `mfa_required_by_role`.
  - `require_role` afviser admin/super_admin API-adgang uden MFA-verificeret session, når policy kræver det.
  - password-login for admin/super_admin uden TOTP giver en kort MFA-enrollment-session i stedet for permanent lockout.
  - `/api/admin/users/{user_id}/mfa/reset` nulstiller hel/halv TOTP-state; valgfri WebAuthn-sletning er understøttet via payload.
  - Users UI viser `MFA kræves`, `MFA halv state` og har `Nulstil MFA`.
  - Login UI kan oprette MFA direkte, når policy kræver enrollment.
- Verifikation:
  - `/Users/peter/.venvs/timelapse-headend/bin/python -m py_compile headend/main.py headend/database.py` OK.
  - `npm --prefix timelapse-ui run build` OK.
  - live headend health OK.
  - smoke-test: ny super_admin uden MFA → `mfa_setup_required` → QR/secret → TOTP confirm → `/api/admin/users` HTTP 200.
  - smoke-test: super_admin med MFA nulstiller halv TOTP-state på anden bruger OK.

### Codex 2026-07-02 — MFA-undtagelser i config-hierarki
- Peter bad om en eksplicit mulighed for at undtage bestemte admin/super_admin-brugere fra MFA,
  så Codex/Claude testbrugere og evt. kundeønskede service-admins kan logge ind uden TOTP.
- Implementeret som config, ikke hardcoded:
  - `session_policy.mfa_exempt_usernames`
  - virker i samme hierarki som resten af session policy: global → kunde → site → kamera.
- Global Config UI har nu feltet `MFA-undtagelser` med checkbox/dropdown over admin/super_admin-brugere.
- Live DB er sat til:
  - `mfa_exempt_usernames=["claudetest","codex"]`
- Live policy-test efter headend restart:
  - `codex required=False`
  - `claudetest required=False`
  - `peter required=True`
- Verifikation:
  - backend compile OK.
  - UI build OK.
  - `/api/health` OK efter restart.

### Codex 2026-07-03 — Travbyen Kamera 2 real-world frontglas-cases
- Peter importerede nye Travbyen Kamera 2 billeder med ægte frontglas-problemer.
- Fundet i canonical originalstruktur, ikke thumbnails:
  - `2026/01/06` — sne/is på frontglas:
    `Kirkbi_A_S_Travbyen_Kamera_2_20260106_125938.jpg`, capture `28016`
  - `2026/01/08` — sne/vand på frontglas:
    `Kirkbi_A_S_Travbyen_Kamera_2_20260108_125936.jpg`, capture `28017`
  - `2026/01/14` — vand/sne på frontglas + modlys:
    `Kirkbi_A_S_Travbyen_Kamera_2_20260114_095931.jpg`, capture `28018`
- DB-tags lagt på de tre captures:
  - fælles: `qa_review_realworld_front_glass`, `qa_training_candidate`, `travbyen_camera_2_realworld`
  - `28016`: `snow_or_ice_on_front_glass`, `snow_or_dirt_on_lens`, `very_blurry`, `low_saturation`
  - `28017`: `snow_or_water_on_front_glass`, `snow_or_dirt_on_lens`, `localized_water_snow_blobs`
  - `28018`: `front_glass_water`, `direct_sun_reflection`, `snow_or_dirt_on_lens`, `sun_glare`
- Artefakter:
  - review sheet:
    `artifacts/edge-qa-training/travbyen-kamera2-realworld-frontglass-20260703/travbyen-kamera2-frontglass-review-sheet.jpg`
  - features:
    `artifacts/edge-qa-training/travbyen-kamera2-realworld-frontglass-20260703/travbyen-kamera2-frontglass-features.json`
  - labels/manifest:
    `artifacts/edge-qa-training/travbyen-kamera2-realworld-frontglass-20260703/travbyen-kamera2-frontglass-realworld-labels.jsonl`
  - current CV report efter tuning:
    `artifacts/edge-qa-training/travbyen-kamera2-realworld-frontglass-20260703/edge-cv-after-frontglass-tuning.jsonl`
- Kodejustering:
  - `edge/tools/analyse_qa_batch.py` ignorerer nu både `.thumbs` og `.headend-thumbs`.
  - `edge/capture/quality.py` har en forsigtig tile-baseret frontglas-sne/is heuristik.
- Resultat efter tuning:
  - 2026-01-06 klassificeres nu som `snow_or_dirt_on_lens` med confidence `0.88`.
  - 2026-01-14 klassificeres fortsat som `direct_sun_reflection`.
  - 2026-01-08 klassificeres stadig `ok` af ren CV; den er derfor en vigtig supervised AI/NPU-træningscase
    for lokale vand/sne-blobs på frontglas.
- Verifikation:
  - `python -m py_compile edge/capture/quality.py edge/tools/analyse_qa_batch.py tests/test_edge_quality_qa.py` OK.
  - `python -m pytest tests/test_edge_quality_qa.py -q` OK: `32 passed`.

### Handover 2026-07-03 — fra Claude (ny session) til Peter/Codex

- Hvad er gjort: onboardet via `00_START_HER.md` + handover-dokumenter, derefter fuld læsning af
  alle 17 autoritative v10-dokumenter + levende dokumenter/designnotater, og en målrettet, frisk
  kodegennemgang (`headend/main.py`, `cmdb.py`, `siem.py`, `itim.py`, `edge/security.py`,
  `edge/agent.py`, UI auth-lag, CI-workflow, `requirements.txt`, repo-hygiejne). Ingen kodeændringer.
- Rapport: `Dokumentation/Claude_Kritisk_Statusgennemgang_2026-07-03.md` — læs den for fuld
  begrundelse og linjehenvisninger.
- Vigtigste nye fund (verificeret i kode, ikke kun dokumentation):
  1. **`/api/siem/events|summary|threats` har ingen autentificering** (`headend/siem.py`,
     monteret uden `dependencies=[...]` i `main.py:10007`). Med nginx stadig public på `*:80/443`
     er dette reelt eksponeret i dag, ikke kun teoretisk. `POST /events/{device_id}` kan også
     modtage fabrikerede events uden HMAC/token.
  2. **MFA håndhæves kun i `main.py::require_role`** — `cmdb.py::_require_cmdb_role` og
     `itim.py::_require_role` er separate, kopierede RBAC-tjek uden MFA-kald. Det betyder hele
     CMDB-routeren (inkl. `checkout_break_glass`) og ITIM-routeren reelt omgår MFA-politikken,
     modsat "✅ Løst"-status i `RISK_ASSESSMENT_v10.md` R02 / `GO_LIVE_CHECKLIST_v10.md` C-07.
  3. Break-glass-checkout's egne kode-kommentarer kræver MFA/IP-whitelist/rate-limit i produktion,
     men alle tre er opt-in via env-var og default fra.
  4. `captures` har ingen `customer_id`-kolonne — tenant-isolation for billeddata er 100%
     applikations-join-disciplin (`_ensure_capture_device_access`/`_ensure_capture_file_access`).
     Ingen aktiv lækage påvist, men arkitekturen er skrøbelig; anbefaler systematisk audit +
     automatiseret cross-tenant-kontrakttest (matcher Codex' egen v11-anbefaling punkt 8/9).
  5. `headend/requirements.txt` er 100% upinnet og mangler `slowapi`, som `main.py` importerer
     direkte — en frisk `pip install -r requirements.txt` crasher headend ved opstart. Direkte
     risiko for restore-testen, der allerede er en P0-blocker.
  6. CI kører kun syntakstjek + to tynde smoke-tests — ingen lint/SAST/dependency-audit-gate.
- Positivt bekræftet: path-traversal-forsvar på billed-/thumbnail-endpoints er solidt
  (`resolve().relative_to(...)` + tenant-tjek), CORS er korrekt scoped (ingen `*`), SQL er
  konsekvent parametriseret, Ed25519/HMAC edge-signering i `edge/security.py` er velskrevet, og
  `DOKUMENTPAKKE_OVERSIGT_v10.md`'s note om localStorage-tokens er forældet i positiv retning —
  `tl_session` er reelt en HttpOnly-cookie, ikke localStorage.
- Hvad mangler / næste skridt: Peter/Codex bør se rapporten, beslutte rækkefølge (jeg foreslår
  fund #1-4 først, da #1 og #3 er reelt eksponerede lige nu), og derefter kan jeg starte
  implementering på en `claude/`-branch.
- Filer rørt: kun `Dokumentation/Claude_Kritisk_Statusgennemgang_2026-07-03.md` (ny) + denne log.
- Risici/pas på: fund #1 og #3 er reelle huller i et system der (midlertidigt) er
  internet-eksponeret via nginx *:80/443 — bør ikke vente på den fulde v11-runde.

### Tilføjelse 2026-07-03 — kamera-lokation/Edge-binding + yderligere lovgivning

- Peter spurgte specifikt ind til, om adskillelsen "kamera-lokation (billeder+konfig) ↔ fysisk
  Edge (udskiftelig)" reelt er færdigimplementeret. Bekræftet i kode: **kun halvt lavet**.
  `Camera` + `DeviceAssignment` (med assigned_at/unassigned_at-historik) findes og virker korrekt
  for **konfiguration** (`config-resolution` joiner rigtigt via `DeviceAssignment`), og
  `POST /api/admin/cameras/{id}/assign` lukker/åbner assignments korrekt. Men `Capture`
  (`headend/database.py:112`) har ingen `camera_id`-kolonne, og intet sted i koden joines
  captures via `DeviceAssignment` — galleri, tag-søgning, timelapse-video og billed-endpoints
  filtrerer udelukkende på `device_id`. Selv `CameraPage.tsx` er nøglet på `deviceId`, ikke
  `cameraId`. Konsekvens: udskiftes en defekt Edge (korrekt omtildelt via assign-endpointet),
  følger konfigurationen med, men billedhistorikken gør ikke — gamle og nye billeder står under
  to forskellige device_id'er uden samlet visning. Se fuld analyse + forslag til rettelse
  (tilføj `camera_id` på `Capture`, backfill via `DeviceAssignment`-tidsvinduer, kamera-centreret
  visning) i §2.5 i `Claude_Kritisk_Statusgennemgang_2026-07-03.md`.
- Peter bad også om et tjek for anden relevant lovgivning ud over de otte standarder, der allerede
  er dækket. Tilføjet som §7 i samme rapport: tv-overvågningsloven (DK, ikke nævnt noget sted —
  mest konkrete gab), databeskyttelsesloven, arbejdsmiljøloven (kameraovervågning af ansatte),
  radioudstyrsdirektivet/RED + cybersikkerheds-delegeretakt 2022/30 (relevant fordi Edge har
  WiFi/BT/4G — CE-mærkningsspor uafhængigt af CRA), CER (nævnes i dag kun én gang i forbifarten,
  bør have samme behandling som NIS2), samt GDPR Art. 22 eksplicit ved siden af AI Act-punktet.

### Handover 2026-07-03 (fortsat) — fra Claude til Codex/Peter: implementering af fase 1-sikkerhedsrettelser

- **Kontekst:** Codex krydstjekkede `Claude_Kritisk_Statusgennemgang_2026-07-03.md` direkte mod
  koden og bekræftede hovedfundene (SIEM-auth, MFA-gab i CMDB/ITIM, upinnet requirements.txt,
  `Capture` uden `camera_id`). Anbefalede: gennemfør de første 3-4 isolerede sikkerhedspunkter nu;
  tag `Capture.camera_id`/`customer_id`-skemaændringen mere kontrolleret (rører galleri, import,
  tag-søgning og RBAC samtidig). Peter bad Claude tage teten. Al kode nedenfor er ny og ikke rørt
  af Codex' aktive edge-QA/NPU-arbejde (ingen fil-overlap).
- **Branch:** `claude/security-hardening-2026-07-03`, oprettet fra `codex/edge-npu-qa`s HEAD
  (`c038403`) — det aktuelt tjekkede-ud arbejdstræ på Mac'en, IKKE `main` (som viste sig at være
  10+ dage forældet — se separat fund nedenfor).
- **Hvad er gjort (alle fire fase 1-punkter fra rapporten):**
  1. `headend/siem.py`: `GET /events|summary|threats` kræver nu `viewer`-rolle + MFA-politik
     (ny `_require_siem_role()`, som — modsat cmdb.py/itim.py's ældre broer — også håndhæver MFA
     fra start). `POST /events/{device_id}` kræver nu gyldigt device-token via samme
     `main._verify_device_token()`-kæde (HMAC/attestation) som alle andre edge-endpoints.
  2. `headend/cmdb.py::_require_cmdb_role` og `headend/itim.py::_require_role`: tilføjet manglende
     MFA-håndhævelse (kalder nu `main._mfa_required_for_user`/`_session_is_mfa_verified`, samme
     som `main.py::require_role` altid har gjort). Lukker samtidig break-glass-hullet (§2.3), da
     `checkout_break_glass` bruger `_require_cmdb_role("admin")`.
  3. `headend/requirements.txt`: alle 14 (nu 15 med `slowapi`) afhængigheder pinnet til konkrete
     versioner, fundet i en lokal, kørende venv med pakkerne installeret. **Skal krydstjekkes mod
     den faktiske prod-venv** (`~/.venvs/timelapse-headend/bin/pip freeze`) — pins er et stærkt
     udgangspunkt, ikke en garanteret kopi af live-miljøet.
- **Verifikation (VERIFICERET I KODE, ikke live):**
  - `python -m py_compile` OK på alle fire ændrede filer.
  - `pip install -r headend/requirements.txt` lykkedes rent i et isoleret testmiljø (Python 3.10).
  - Eksisterende testsuite: `pytest tests/test_agent_integrity.py tests/test_headend_endpoints.py`
    → `18 passed` (uændret, ingen regression).
  - **Ny, reel FastAPI TestClient-verifikation** (sqlite-baseret, ikke kun statisk læsning):
    - `GET/POST /api/siem/*` uden login → `401` (alle fire endpoints, før: `200`/no-op-accept).
    - `GET /api/cmdb/`, `GET /api/itim/health` med viewer-rolle (MFA ikke krævet for rollen) →
      `200`.
    - Samme to endpoints med admin-rolle, session UDEN `mfa_verified` → `403 "MFA kræves for
      denne rolle"` (dette var den reelle live-bug — nu lukket).
    - Samme to endpoints med admin-rolle, session MED `mfa_verified=true` → `200` (ingen
      regression for korrekt MFA'de sessioner).
    - `POST /api/siem/events/{device_id}` med forkert device-token → `401`; med korrekt
      `Device.api_token` → kommer korrekt forbi auth-laget (fejlede kun videre inde i
      request-flowet på en Postgres-specifik `information_schema`-forespørgsel, som er en kendt,
      urelateret sqlite-begrænsning i mit testmiljø — ikke en fejl i selve rettelsen).
- **IKKE gjort endnu — commit blokeret:** `git add`/`git commit` fejlede med
  `fatal: Unable to create '.git/index.lock': File exists`. Filen kunne heller ikke fjernes
  manuelt fra Claudes sandbox (`rm: cannot remove '.git/index.lock': Operation not permitted`,
  selvom `ls -la` viser normal ejer/rettigheder 0600). Dette minder om det kendte
  data-fast-volumen-I/O-mønster i `SERVICES_OG_DRIFT_kilde_til_sandhed.md` §3, men er ikke
  bekræftet som samme rodårsag. **Ret ikke selv videre på dette fra Claude-siden** (jf. reglen:
  OS-/fillås-problemer er Codex/Peter-territorium). **Codex/Peter: tjek venligst**
  `ls -la /Volumes/data-fast/peter-home/projects/timelapse-pro/.git/index.lock` — hvis ingen
  levende git-proces kører, fjern filen (`rm .git/index.lock`), og bekræft at
  `git status` på branch `claude/security-hardening-2026-07-03` viser de fire ændrede filer
  (`headend/cmdb.py`, `headend/itim.py`, `headend/requirements.txt`, `headend/siem.py`) klar til
  commit. Alle filændringer ligger allerede korrekt på disk — kun selve `git add`/`commit`
  mangler.
- **Kommandoer der skal køres, når lock er ryddet:**
  ```bash
  cd ~/projects/timelapse-pro
  git status --short              # bør vise præcis de 4 filer ovenfor som M, intet andet
  git add headend/cmdb.py headend/itim.py headend/requirements.txt headend/siem.py
  git commit -m "Security: require MFA in CMDB/ITIM role checks, auth-gate SIEM router, pin requirements.txt"
  ~/.venvs/timelapse-headend/bin/pip install -r headend/requirements.txt   # bekræft ingen version-konflikt mod prod-venv
  sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
  sleep 25
  curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health   # forventet 200
  curl -i http://127.0.0.1:8000/api/siem/events                                       # forventet 401 (var 200)
  ```
- **NYT PROCESFUND — `main` er 10+ dage forældet:** Under branch-arbejdet blev det tydeligt at
  `main` sidst blev opdateret 2026-06-23 (`feat(edge): persist and list disk image artifacts`),
  mens mindst 7 andre branches (`codex/edge-npu-qa`, `claude/siem-cmdb-optimizations`,
  `codex/cmdb-rbac-hardening`, `codex/itim-live-verification`, `codex/shared-handover-docs`,
  `codex/edge-ai-npu-modes`, `codex/edge-ai-v1-smoke`) er grenet fra samme punkt og aldrig
  merget tilbage. Det aktuelt udcheckede arbejdstræ (`codex/edge-npu-qa`) er heldigvis det mest
  komplette — det viste sig allerede at indeholde både `codex/cmdb-rbac-hardening`s rolletjek og
  `claude/siem-cmdb-optimizations`s break-glass/SIEM-rettelser (formentlig foldet ind via
  checkpoint-commits `9340aed`/`d7a952d`), så intet arbejde er tabt. Men `main` selv mangler det
  hele, og hvis nogen nogensinde kører `git pull origin main` som `ADMINISTRATORMANUAL_v10.md`
  §3.3 foreskriver, ville de få en markant ældre og mere sårbar kodebase end det, der reelt
  kører. **Anbefaling:** en bevidst branch-oprydning (merge `codex/edge-npu-qa` → `main` når
  Codex' aktive arbejde er klar, slet de nu-forældede sibling-branches efter bekræftelse af at
  deres indhold er absorberet) bør på listen som eget punkt.
- **Filer rørt (denne handover-runde, ud over kode):** `Dokumentation/RISK_ASSESSMENT_v10.md`
  (R02 korrigeret + nyt R15), `GO_LIVE_CHECKLIST_v10.md` (C-04, C-07, H-03),
  `KRAVREGISTER_og_STATUS_v10.md` (SEC-004, SEC-008), `ADMINISTRATORMANUAL_v10.md` (§19).
- **Næste skridt:** (1) Codex/Peter rydder git-lock + committer + genstarter + live-verificerer
  kommandoerne ovenfor. (2) Claude fortsætter til fase 2 (`Capture.camera_id`/`customer_id`) med
  et separat design-oplæg til godkendelse, jf. Codex' anbefaling om en mere kontrolleret tilgang
  dér. (3) Overvej branch-oprydningen (main vs. de 7 divergerende branches) som eget punkt.

### Handover 2026-07-03 12:20 — fra Claude til Peter/Codex: fase 2 færdig (Capture.camera_id/customer_id)
- **Hvad er gjort:** Fase 2 (§2.4/§2.5 i `Claude_Kritisk_Statusgennemgang_2026-07-03.md`) er
  implementeret, verificeret og allerede committet — se "Bemærkning om commit" nedenfor.
  1. `headend/database.py`: `Capture` har fået to nye nullable, indekserede kolonner:
     `camera_id` (String(36), → `Camera.id`) og `customer_id` (String(36), → `Customer.id`).
  2. `headend/main.py`: DB-migration v12 (idempotent `ALTER TABLE`/`CREATE INDEX IF NOT EXISTS`
     i startup-eventet, samme mønster som v9/v10/v11). Ny helper
     `_resolve_capture_camera_customer(db, device_id, captured_at=None)`: `customer_id` findes
     primært via `Device.customer_id` (bred dækning, også bulk-importerede devices uden
     kamera-binding); `camera_id` findes via den `DeviceAssignment`, der var aktiv på
     capture-tidspunktet (kun devices reelt bundet til en logisk kamera-lokation — resten
     forbliver bevidst `NULL`, ikke gættet). `Camera.customer_id` vinder over
     `Device.customer_id`, når en binding findes. Wired ind i `_upsert_capture_record()`, så
     nye/opdaterede captures får felterne udfyldt automatisk uden at ændre eksisterende adfærd.
  3. `headend/importer.py`: samme resolver kaldt fra bulk-import-stien (bemærk: bulk-importerede
     devices er sjældent bundet til en kamera-lokation, så `camera_id` er ofte `NULL` her —
     `customer_id` dækker bredere).
  4. `headend/tools/backfill_capture_camera_customer.py` (nyt script): backfilder
     `camera_id`/`customer_id` på eksisterende captures. Default er `--dry-run` (rapporterer
     antal resolvet/opdateret uden at skrive). `--apply` skriver faktisk. `--force` genberegner
     også allerede udfyldte rækker. `--device-id`/`--limit` til afgrænset testkørsel. Idempotent.
  5. `headend/main.py` `/api/admin/captures`: nyt **additivt** query-parameter `camera_id` —
     filtrerer på logisk kamera-lokation på tværs af Edge-udskiftninger (løser det oprindelige
     "udskift defekt Edge, bevar billedhistorik"-problem fra Peters oprindelige spørgsmål).
     Tenant-isolation håndhæves identisk med det eksisterende mønster fra
     `/api/admin/config-resolution` (`_ensure_site_access`/`_ensure_customer_access` på kameraets
     site/customer). Response-objektet inkluderer nu også `camera_id`/`customer_id` pr. capture.
     `device_id`-baseret filtrering er uændret (bagudkompatibelt).
- **Verifikation (reel TestClient + sqlite, ikke kun `py_compile`):** byggede et scenarie med
  2 kunder, 3 devices, 1 kamera-lokation, en Edge-udskiftning (device 1 → device 2 på samme
  kamera-lokation) og et ubundet bulk-device (device 3, kunde B). Alle 4 testgrupper bestod:
  1. Resolver returnerer korrekt `camera_id`/`customer_id` for både det gamle og det nye device
     bag udskiftningen, og korrekt `customer_id`/`camera_id=None` for det ubundne device.
  2. `_upsert_capture_record` udfylder felterne automatisk ved skrivning.
  3. `/api/admin/captures?camera_id=...` samler billeder på tværs af Edge-udskiftning, respekterer
     tenant-grænser (403 for bruger fra anden kunde, 200 for `super_admin`, 404 for ukendt
     `camera_id`), og de nye felter er med i JSON-responsen.
  4. Backfill-scriptet: dry-run rapporterer korrekt antal uden at skrive, apply skriver kun de
     manglende rækker, og en gen-kørsel er idempotent (0 opdateringer).
- **Bemærkning om commit:** Mens jeg arbejdede, blev `.git/index.lock` igen låst med samme
  "Operation not permitted" som i sidste handover-runde — men denne gang viste det sig at Peter
  (formentlig via Codex' aktive arbejde på samme filsystem) allerede havde committet mit
  arbejdstræ i `3a2c0a8 "Backfill capture metadata and GPS sidecar flow"` (12:15:59), sammen med
  Codex' parallelle arbejde (`edge/camera/drivers/gphoto2_driver.py`,
  `edge/upload/headend_client.py` — GPS-sidecar, `headend/tools/backfill_capture_metadata.py` —
  EXIF-metadata-backfill, `timelapse-ui/src/pages/DevicePage.tsx` og `types/index.ts`). Jeg har
  efterfølgende: (a) `py_compile`-verificeret alle rørte Python-filer inkl. Codex' tilføjelser —
  ingen konflikt, (b) genkørt hele testsuiten mod det faktisk committede `HEAD` — alle 4 grupper
  bestod stadig. Intet manuelt commit-arbejde var altså nødvendigt fra min side denne gang.
- **Filer rørt (denne runde):** `headend/database.py`, `headend/main.py`, `headend/importer.py`,
  `headend/tools/backfill_capture_camera_customer.py` (nyt) — alle allerede i commit `3a2c0a8`.
- **Hvad Peter/Codex bør teste/beslutte, før backfill køres i produktion:**
  1. Kør `python3 headend/tools/backfill_capture_camera_customer.py --dry-run` mod
     prod-databasen og gennemgå tallene (antal resolvet vs. uresolveret, og listen over devices
     uden nogen resolution) — særligt vigtigt at bekræfte at "uden resolution"-devices reelt
     forventes at være ubundne/ukendte, før `--apply` køres.
  2. Overvej at køre med `--device-id <et enkelt device>` først som stikprøve.
  3. Efter backfill: test `/api/admin/captures?camera_id=<uuid>` i UI/Postman på et kamera, der
     har haft en Edge-udskiftning, og bekræft at billeder fra begge devices vises samlet.
  4. ~~`camera_id`/`customer_id` bruges endnu ikke til selve tenant-isolationen~~ — **Peter
     godkendte 2026-07-03 13:00** at gå videre med dette, og det er nu implementeret. Se ny
     handover-note nedenfor ("Fase 3").
  5. **Ikke gjort endnu:** en decideret kamera-lokations-UI-side (`/cameras/:id`) der viser fuld
     billedhistorik på tværs af Edge-udskiftninger for slutbrugeren — pt. kun tilgængeligt via
     API-parameteren. Forslag #3 i rapportens §2.5, bevidst afgrænset fra denne omgang.
- **Risici / pas på:** samme delte-filsystem-forsigtighed som sidst — Codex arbejder aktivt i
  `headend/importer.py`/`headend/main.py` samtidig med mig, så genlæs altid umiddelbart før edit.
  `.git/index.lock`-problemet er stadig uløst i sig selv (samme mount-niveau-begrænsning som
  tidligere dokumenteret) — denne gang generede det bare ikke arbejdet, fordi committet skete
  fra host-siden. Fortsat OS-/fillås-territorium for Codex/Peter, hvis det driller igen.

### Handover 2026-07-03 13:15 — fra Claude til Peter/Codex: fase 3 (tenant-isolation via customer_id)
- **Baggrund:** Peter bekræftede 2026-07-03, at tenant-isolation af billeddata bør følge
  kunde/site/kamera-lokations-hierarkiet og være afkoblet fra `device_id`, netop fordi en fysisk
  Edge-enhed kan udskiftes/genbruges. Under planlægningen fandt jeg et **konkret, aktivt
  lækage-scenarie** i den daværende kode (ikke kun det generelle §2.4-fund): det gamle
  adgangstjek (`_allowed_capture_device_ids`) er et LIVE opslag på "hvilke devices tilhører denne
  kunde LIGE NU" (via `Device.customer_id`). Hvis en fysisk Edge-enhed senere genbruges og
  tildeles en ANDEN kunde, giver det tjek automatisk den nye kunde adgang til ALLE gamle billeder
  taget mens enheden tilhørte den forrige kunde — en reel, udnyttelig kundedatalækage over tid.
- **Rettelse (godkendt af Peter, se spørgsmål/svar 2026-07-03 13:00):**
  1. `_capture_is_allowed()` foretrækker nu `Capture.customer_id` (frosset ved
     optagelsestidspunkt, v12-feltet fra fase 2) frem for det live device-opslag. Kun for
     rækker, der endnu ikke er backfillet (`customer_id IS NULL`), falder den tilbage til den
     gamle device-baserede logik — ingen breaking change.
  2. Ny helper `_capture_tenant_clause(user, allowed_device_ids)` — samme logik udtrykt som et
     SQL-filter, brugt i `list_captures`, `/api/admin/stats` og QA/AI-søgeendpointet, så listning
     og optælling også er lukket, ikke kun enkelt-opslag (delete/exif/sidecar/fil-servering, som
     alle går via `_capture_is_allowed()`).
  3. **Fejl fundet og rettet UNDER egen test:** min første version beholdt den gamle
     "tomt device-sæt → returnér straks intet"-genvej. Det betød, at en kunde, hvis eneste device
     var blevet omtildelt væk, pludselig ikke længere kunne se SINE EGNE gamle billeder (falsk
     negativ/regression, ikke en lækage, men en reel fejl). Rettet ved at fjerne genvejen —
     `_capture_tenant_clause()` matcher korrekt "ingenting" i sig selv, når det er relevant.
  4. **Endnu en risiko fundet og rettet:** `_capture_tenant_clause()` sammenligner
     `Capture.customer_id == user.customer_id`. For en bruger UDEN `customer_id` (fejlkonfigureret
     konto, ikke platform-admin) ville SQLAlchemy oversætte det til `IS NULL` og fejlagtigt matche
     ALLE endnu ubackfillede rækker på tværs af alle kunder. Tilføjet eksplicit `false()`-guard for
     dette tilfælde, testet separat.
  5. Bevidst UDENFOR scope denne omgang: baggrundsjob til post-processing/AI-batch-kø (to steder i
     `main.py`, markeret med "NB (Fase 3)"-kommentarer) bruger fortsat kun det gamle
     device-baserede filter til at afgrænse HVILKE devices et job må behandle — vurderet lav
     konfidentialitetsrisiko, da jobbet kun skriver afledte metadata/tags tilbage, ikke eksponerer
     billeder. Kan tages op som en separat, mindre opgave.
- **Verifikation (reel TestClient, ikke kun `py_compile`):** nyt scenarie — device X tilhører
  Kunde A, tager et billede, X gen-tildeles derefter til Kunde B, X tager et nyt billede. 7 tests:
  Kunde B kan IKKE se/liste/slette det gamle Kunde A-billede (hverken via almindelig liste eller
  eksplicit `device_id`-filter), Kunde B KAN se sit eget nye billede, Kunde A beholder adgang til
  sit eget gamle billede (ingen falsk positiv/regression), en ubackfillet "forældreløs" række
  følger stadig den midlertidige device-fallback som forventet, og `super_admin` ser alt. Plus en
  separat kant-test for "bruger uden customer_id"-guarden (punkt 4 ovenfor).
- **Filer rørt:** `headend/main.py` (`_capture_is_allowed`, ny `_capture_tenant_clause`, samt
  opdateret filtrering i `list_captures`, `/api/admin/stats`, QA/AI-søgeendpointet, OpenWebUI
  candidate-filtrering — alle centraliseret, kun 4 kernefunktioner ændret trods 52 kald-steder).
  IKKE committet endnu — afventer normal commit-proces (ingen `.git/index.lock`-problem denne
  gang). Dokumentation opdateret: `RISK_ASSESSMENT_v10.md`, `GO_LIVE_CHECKLIST_v10.md`,
  `KRAVREGISTER_og_STATUS_v10.md`, `ADMINISTRATORMANUAL_v10.md`,
  `Claude_Kritisk_Statusgennemgang_2026-07-03.md`.
- **Hvad Peter/Codex bør teste live, når det er deployet:**
  1. Bekræft at eksisterende galleri/søgning/sletning stadig virker normalt for almindelige
     brugere (ingen regression) — særligt for kunder hvor et device er blevet omtildelt.
  2. Kør backfill-scriptet fra fase 2 (`--dry-run` først) i produktion, hvis det ikke allerede er
     sket — jo flere rækker der er backfillet, jo mindre afhænger sikkerheden af
     device-fallback'en.
  3. Overvej som opfølgning: skal post-processing/AI-batch-jobbets device-filter også opdateres
     til samme `customer_id`-først-logik (punkt 5 ovenfor)? Vurderet lav risiko, men ikke rettet.
- **Næste skridt:** commit + genstart + live-verifikation (Peter/Codex, som med fase 1).

### Handover 2026-07-03 13:35 — fra Claude til Peter/Codex: fase 4 (site_id-tagging)
- **Baggrund:** Peter spurgte om ikke alle billeder bør tagges med HELE hierarkiet
  (kunde/site/kamera-lokation), ikke kun kunde og kamera-lokation, så en senere, mere
  restriktiv RBAC-granularitet end "hele kunden" kan indføres uden at skulle genudlede
  historikken via et live join — præcis samme lektie som R16 (fase 3): frys hierarkiet ved
  optagelsestidspunktet, følg ikke et device/kamera, der senere flyttes/omtildeles.
- **Implementeret (godkendt af Peter — "Du må gerne gå videre"):**
  1. `headend/database.py`: ny nullable, indekseret `Capture.site_id` (String(36)).
  2. `headend/main.py`: DB-migration v13 (samme idempotente mønster som v12).
     `_resolve_capture_camera_customer()` udvidet fra 2-tuple til 3-tuple
     `(camera_id, customer_id, site_id)` — alle 3 kaldsteder opdateret (main.py's
     `_upsert_capture_record`, `importer.py`, backfill-scriptet). site_id følger samme
     kilde-prioritet som customer_id: `Camera.site_id` foretrækkes over `Device.site_id`,
     hvis en kamera-binding findes (testet eksplicit — se nedenfor).
  3. `headend/tools/backfill_capture_camera_customer.py` udvidet til også at backfille
     `site_id` på historiske rækker (samme dry-run/apply/idempotens-mønster).
  4. `/api/admin/captures`-response inkluderer nu `site_id` (rent oplysende, additivt —
     ingen nyt filter-parameter denne gang, kun tagging).
- **Bevidst IKKE gjort:** `site_id` bruges IKKE til selve adgangskontrollen endnu — kun
  `customer_id` er sikkerhedsbærende (fase 3). At bygge site-niveau RBAC-håndhævelse kræver
  desuden en udvidelse af `User`-modellen (den har i dag kun `customer_id`, intet begreb om
  en bruger bundet til ét site) — det er en separat, større beslutning, som bevidst er
  afventet til der er et konkret behov. Denne omgang handler kun om at gøre dataene klar.
- **Verifikation (TestClient):** scenarie med et device uden kamera-binding (site_id fra
  `Device.site_id`) og et device MED kamera-binding til et andet site end devicets eget
  (bekræfter at `Camera.site_id` korrekt vinder). Testet: resolver, `_upsert_capture_record`,
  `/api/admin/captures`-response, og backfill af en historisk "legacy"-række. Alle 4
  testgrupper bestod. Genkørte desuden fase 2- og fase 3-testsuiterne uændret — ingen
  regression (resolverens signaturændring 2→3-tuple var eneste breaking change, opdateret
  konsistent alle 3 steder).
- **Filer rørt:** `headend/database.py`, `headend/main.py`, `headend/importer.py`,
  `headend/tools/backfill_capture_camera_customer.py`. IKKE committet endnu.
- **Hvad Peter/Codex bør gøre:**
  1. Commit + push (se separat kommando-liste i chatten til Peter).
  2. Genstart headend, bekræft health 200.
  3. Når I er klar til det: kør backfill-scriptet (nu med site_id) mod produktion,
     `--dry-run` først som altid.
  4. Ingen UI/adfærdsændring at teste udover det — dette er ren tagging.

### Handover 2026-07-03 14:00 — Peter: fase 2-4 committet, deployet og backfill kørt komplet i produktion
- **Commits:** `bb18421` (fase 3), `e40bd63` (fase 4), begge på
  `claude/capture-camera-location-2026-07-03`, committet af Peter, pushet til GitHub,
  headend genstartet, health `200`.
- **Backfill kørt mod produktion** (`headend/tools/backfill_capture_camera_customer.py --apply`),
  i to omgange:
  1. Første kørsel: 27.662 captures behandlet. `site_id` resolvet for alle 27.662.
     `customer_id` kun resolvet for 22.633 — et enkelt device,
     `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1` (bulk-importeret, `site_id` sat men aldrig
     koblet til en `Customer`-record), stod for de resterende 5.029 rækker uden `customer_id`.
  2. Rettet via `PUT /api/admin/devices/{device_id}/assign` (samme `site_id` sat igen,
     hvilket får endpointet til selv at udlede og udfylde `customer_id` fra sitet —
     `customer_id` blev `687de00d-8400-47d0-bab4-f29e17dd38bf` / "Kirkbi A/S").
  3. Anden kørsel af backfill-scriptet: de resterende 5.029 rækker fik nu `customer_id`
     sat. **Slutresultat: alle 27.662 captures har `customer_id` og `site_id`.**
     `camera_id` er (forventet, ikke en fejl) kun sat for 965 captures — det er de eneste
     rækker, hvis device reelt har været bundet til en logisk kamera-lokation via en
     `DeviceAssignment`. De resterende ~96,5% forbliver bevidst `NULL`.
- **Betydning:** R16-lækagen (fase 3, kryds-kunde-lækage ved Edge-gentildeling) er nu
  fuldt dækket af den frosne `customer_id`-kilde for 100% af de historiske captures —
  ingen rækker afhænger længere af device-fallback'en for tenant-isolation.
- **Sidefund undervejs:** en løbsk baggrunds-git-proces (`git hash-object`/`git add` mod
  `.base_image_cache/`, `.claude_proxy/`, `artifacts/` — se `.gitignore`-tilføjelsen i
  `e40bd63`) havde skrevet ca. 16 GB "dangling" (ikke-tilgængelige) objekter ind i lokal
  `.git/objects` på Mac Mini'en. Verificeret grundigt at INGEN af de faktiske commits/branches
  indeholder disse filer (kun ren lokal diskbloat, intet pushet til GitHub, ingen
  repo-korruption). Peter kørte `git gc --prune=now --aggressive` for at rydde op.
- **Status:** Fase 2, 3 og 4 er hermed fuldt udrullet, verificeret og backfillet i
  produktion. Ingen åbne opfølgningspunkter fra denne omgang, ud over de tidligere nævnte
  bevidst afgrænsede emner (AI-batch-jobbets device-filter, site-niveau RBAC-håndhævelse,
  kamera-lokations-UI-side).

### Handover 2026-07-03 — Claude: GPS-data manglede i metadata-UI, end-to-end fundet og rettet
- **Symptom:** Peter observerede at GPS-koordinater aldrig vises i captures' metadata-UI,
  selvom flere devices er konfigureret til at bruge et fysisk GPS-modul (`gps_source: "gpsd"`).
- **Undersøgelse:** sporede hele kæden edge (`gphoto2_driver.py` → sidecar JSON) → upload →
  headend (`_sidecar_capture_metadata`, `_upsert_capture_record`) → DB → API
  (`/api/admin/captures`) → frontend (`DevicePage.tsx` Lightbox). Alle led var korrekt
  koblet felt-for-felt — ingen kæde-brud. Produktions-tal viste dog:
  `captures_med_gps = 0` på tværs af **11.895** captures med `gps_source='gpsd'` og
  **9.603** med `'manual'` — dvs. konfigurationen nåede frem, men koordinaterne gjorde aldrig.
- **Root cause fundet i `edge/camera/drivers/gphoto2_driver.py::_read_gpsd_fix()`:** læste kun
  `gpspipe -w -n 12` med 4 sekunders timeout, og enhver fejl (intet fix nået, gpsd ikke
  installeret, timeout) blev svælget tavst (kun `log.debug`, ingen synlighed). Peter
  bekræftede via `cgps -s` direkte på edgen at GPS-modulet reelt HAR et gyldigt 3D-fix
  (55.71777073 N, 9.52511777 E, Vejle-området) — så det var en software-timing-/
  synligheds-bug, ikke en hardwarefejl.
- **Yderligere 2 relaterede bugs fundet og rettet efter Peters afklaring** ("hvis der er
  GPS i kameraet, må det ikke overskrives — det er del af den signede pakke"):
  1. `main.py::get_config()` (linje ~3223): site-niveauets `gps_lat/lon` overskrev
     *ubetinget* en device der var konfigureret til `gpsd` eller havde egen manuel
     lat/lon. Rettet til kun at bruge site-GPS som fallback, når enheden intet selv
     har konfigureret.
  2. `main.py::_upsert_capture_record()`: GPS-felter havde (i modsætning til
     `camera_id/customer_id/site_id`) ingen beskyttelse mod at blive overskrevet ved en
     senere gen-upload/re-sync. Rettet til samme "kun udfyld hvis tomt"-mønster —
     den først-signerede GPS-aflæsning er nu uforanderlig.
- **Rettelser i alt (4 filer, additive, ingen skemaændring):**
  `edge/camera/drivers/gphoto2_driver.py` (`_read_gpsd_fix`: 8 sek/40 linjer i stedet for
  4 sek/12, `log.warning` i stedet for `log.debug` ved fejl/intet fix),
  `headend/main.py` (`get_config()` prioritetsfix + `_upsert_capture_record()` GPS-lås),
  `timelapse-ui/src/pages/DevicePage.tsx` ("GPS kilde" er nu en tillids-label: "🛰️ Live
  GPS-fix", "✍️ Manuelt indtastet", "⚠️ GPS konfigureret — intet fix ved optagelse", eller
  "Ingen GPS data" — i stedet for den rå `gpsd`/`manual`-streng).
- **Verifikation:** nyt testscript med 4 scenarier (gpsd-device beholder `None` frem for
  sitets GPS; manuel device-GPS overskrives ikke af site; device uden egen config falder
  korrekt tilbage til site; gen-upload overskriver ikke en allerede-signeret GPS-aflæsning)
  — alle bestod. Genkørte fase 2/3/4-testsuiterne uændret — ingen regression. `py_compile`
  på begge Python-filer + `tsc --noEmit` på `DevicePage.tsx` — ingen fejl.
- **IKKE committet endnu.** Peter/Codex arbejder samtidig på Ollama-tag-optimering på
  headenden — koordinér git-commit så de to arbejder ikke kolliderer i `main.py`.
- **Resterende, uafklaret:** hvorfor `_read_gpsd_fix()` reelt ramte 12-linjers-loftet uden
  at se et brugbart TPV, selvom gpsd har et fix — er ikke root-cause-bekræftet ud over at
  det nu er langt mere robust og synligt i loggen. Anbefaling: hold øje med edge-loggen
  efter deploy for at se om `log.warning`-linjen "Intet brugbart GPS-fix..." dukker op igen,
  eller om det udvidede vindue løser det helt.

### Handover 2026-07-03 (fortsat) — GPS-featuren var aldrig merget til main + akut 500-bug fundet under test
- **Stort fund ved test på edge (192.168.86.134):** `_read_gpsd_fix()` og resten af
  GPS-sidecar-flowet findes overhovedet ikke i `origin/main` — kun på
  `claude/capture-camera-location-2026-07-03` (introduceret i et tidligere commit,
  "Backfill capture metadata and GPS sidecar flow", aldrig merget). Edgen tracker `main`,
  så den kode der faktisk kører i produktion, har aldrig kunnet lave et live GPS-fix.
  Min oprindelige "timeout for stram"-diagnose er stadig en reel forbedring, men den fulde
  forklaring er: featuren blev aldrig sendt i produktion.
- **`git checkout origin/<branch> -- fil` var for groft:** et forsøg på at hente hele
  `gphoto2_driver.py` fra feature-branchen til edgen ville have trukket ubeslægtede
  ændringer med (kamera-config `focus_controls`/`exposurecompensation`, gphoto2-parsing
  af Bottom/Top/Step) — hele branchen indeholder desuden edge AI/NPU-sporet og
  CMDB/diagnostik/tunnel/upload-ændringer (bekræftet uafhængigt af Codex via SSH på
  edgen). Rullet tilbage til ren `main`-HEAD, og i stedet lavet et isoleret
  find/erstat-patch-script (`apply_gps_patch.py`, lagt i workspace-roden) der KUN
  tilføjer `_read_gpsd_fix`/`_number_or_none` + de tre linjer i `_write_sidecar`/
  `_write_xmp_metadata`. Testet mod den faktiske `origin/main`-fil (73 linjer
  tilføjet, 3 ændret, `py_compile` OK, idempotent), og verificeret at diffen på selve
  edgen matchede testresultatet 1:1 før genstart.
- **Akut produktionsbug fundet ved første rigtige upload efter edge-genstart:**
  `POST /api/captures/{device_id}/files` fejlede med `TypeError:
  _upsert_capture_record() got multiple values for keyword argument 'camera_model'` —
  100% fejlrate på alle uploads fra edgen umiddelbart efter genstart (set i
  `~/Library/Logs/timelapse-headend.log`). Root cause: `receive_capture_files()`
  (main.py, nu linje ~3879) sendte `camera_model=meta.get("camera_model")` som eksplicit
  keyword-argument OG som del af `**capture_values`-spread (som selv indeholder en bedre
  fallback: `meta.get("camera_model") or sidecar_meta.get("camera_model")`) — en
  pre-eksisterende bug, IKKE relateret til GPS-rettelserne (mine ændringer rørte kun
  `get_config()` og løkken i `_upsert_capture_record()`, ikke dette kaldested). Ukendt
  hvornår bugget blev indført, og hvorfor det ikke er ramt tidligere — mistanke om at
  denne specifikke multipart-upload-vej (`manifest+image+sidecar+thumbnail`) er relativt
  ny/sjældent testet sammenlignet med den ældre Pydantic-baserede upload-endpoint.
  **Rettelse:** fjernet den overflødige eksplicitte `camera_model=`-linje (1 linje).
  Verificeret med nyt regressionstestscript (`test_upload_endpoint.py`) der simulerer en
  fuld multipart-upload som en rigtig edge — fejlede reproducerbart før rettelsen (samme
  TypeError), bestod efter. Alle øvrige tests (GPS-fix, fase 2/3/4) genkørt uden
  regression.
- **IKKE committet endnu.** Denne ene linje mangler i den seneste `main.py`-commit
  (`8a044a8f`) og skal med i en opfølgende commit, før produktions-uploads virker igen —
  edgen står lige nu og fejler alle uploads indtil headend genstartes med rettelsen.
- **Opfølgning, ikke løst nu:** en ordentlig merge-plan for hele
  `claude/capture-camera-location-2026-07-03` (fase 1-4 + GPS-sidecar + edge AI/NPU +
  kamera-config) ind i `main`, så branchen ikke driver længere væk, og så GPS-featuren
  bliver en officiel del af den kode der bygges artifacts fra. Foreslået, afventer
  Peter/Codex' beslutning om omfang og tidspunkt.

### Handover 2026-07-03 (fortsat igen) — v1-GPS-fixet virkede ikke i praksis: fandt og rettede den egentlige regnefejl
- **Symptom efter deploy af 500-fix:** uploads gik igennem (200 OK), men metadata-UI viste
  stadig "⚠️ GPS konfigureret — intet fix ved optagelse" for en frisk capture, selvom
  `Højde 55 m` (manuel/site-konfigureret) var med. Dvs. UI-tillids-labellen (fase 4) virkede
  korrekt, men selve `_read_gpsd_fix()` fik stadig intet fix.
- **Root-cause (denne gang den rigtige, verificeret via direkte reproduktion på edgen):**
  v1 af `_read_gpsd_fix()` brugte `gpspipe -w -n 40` med 8 sekunders timeout. `-n 40`
  tæller ALLE JSON-beskeder fra gpsd (VERSION/DEVICES/WATCH-kvittering +
  interfolierede SKY-rapporter), ikke kun TPV. Ved ~2 beskeder/sekund kræver 40 beskeder
  ~18-19 sekunders strømtid — langt mere end 8 sekunders timeout. Resultat: `gpspipe`
  blev **altid** dræbt af vores egen timeout, uanset om gpsd havde et gyldigt fix. Dette
  er en regnefejl jeg selv indførte i v1 (udvidede fra 12→40 linjer for at "give mere plads",
  uden at indse at et højere linjetal kræver *mere* tid, ikke mindre risiko).
- **Fejlsporing udelukkede forkerte teorier undervejs, dokumenteret for eftertiden:**
  1. Første mistanke: rettigheds-/sandboxing-problem, fordi `timelapse-edge.service`
     kører som `User=root` med `ProtectSystem=strict` — Peters test som `orangepi`
     (uden samme sandboxing) virkede, hvilket umiddelbart lignede en bekræftelse.
  2. Modbevist ved at reproducere IDENTISK sandboxing via `sudo systemd-run` med samme
     `ProtectSystem=strict`/`ReadWritePaths=` som den rigtige service — `gpspipe -w -n 5`
     virkede fint der. Sandboxing var altså ikke årsagen.
  3. Fandt den egentlige forskel: den vellykkede test brugte `-n 5` (hurtigt), ikke
     den faktiske kodes `-n 40`. Reproducerede hængningen præcist ved at køre Python's
     `subprocess.run(['gpspipe','-w','-n','40'], timeout=8)` i samme sandboxede unit —
     den fejlede identisk med produktionen. Beviser at det var en ren tids-/linjetal-
     regnefejl, ikke permissions.
- **Rettelse:** `_read_gpsd_fix()` omskrevet til at læse `gpspipe`s output linje-for-linje
  via `subprocess.Popen` + `select.select()` med et wall-clock-deadline (default 10 sek,
  op fra 8), og stopper med det samme et brugbart TPV (`mode>=2`) ses — venter ikke på et
  fast antal beskeder. Timer korrekt og gracefully ud efter `timeout_s` hvis intet fix
  nogensinde dukker op, uanset hvor mange beskeder der er modtaget undervejs.
- **Verifikation:** nyt testscript (`test_read_gpsd_fix.py`) med en fake `gpspipe` der
  efterligner den observerede produktions-timing (handshake øjeblikkeligt, derefter
  TPV+SKY-par ca. 1x/sek, med `mode` der flipper mellem 1 og 3): (1) stopper efter ~3 sek
  når et brugbart fix dukker op midt i strømmen, uden at vente resten af vinduet, (2)
  timer korrekt ud efter ~5 sek (ikke ~18 sek) hvis intet fix nogensinde kommer, (3) ingen
  efterladte gpspipe-processer. Alle øvrige tests (fase 2-4, GPS-fix v1, upload-endpoint)
  genkørt uden regression.
- **Deploy:** ny inkrementel patch-script (`apply_gps_patch_v2.py`, lagt i workspace-roden)
  der finder og erstatter den allerede-udrullede v1-`_read_gpsd_fix()` med v2 via regex på
  funktionsgrænser (ikke eksakt tekst-match, som viste sig skrøbeligt pga. forskellig
  Unicode-håndtering af æ/ø/å mellem v1- og v2-scriptet — v2-scriptet bruger derfor bevidst
  ren ASCII-translitteration i sine kommentarer på selve edge-koden, ingen funktionel
  forskel). Testet idempotent, `py_compile` OK, funktionelt identisk med den direkte
  redigerede sandbox-fil.
- **IKKE committet/deployet endnu** — afventer Peters kørsel på edgen og bekræftelse af at
  et rigtigt GPS-fix nu dukker op i metadata-UI'en.
- **Sidegevinst af denne fejlsporing:** vi ved nu med sikkerhed at GPS-modulet (u-blox via
  `/dev/ttyACM0`) og gpsd fungerer korrekt på edgen (bekræftet flere gange med `gpspipe`
  direkte), men at fix-status svinger mellem mode 1 (intet fix) og mode 2/3 (2D/3D-fix) —
  sandsynligvis pga. antenneplacering/himmelsigt. Med det rettede 10-sekunders vindue får
  edgen nu ~5-10 forsøg pr. optagelse i stedet for at være dømt til at fejle af en
  regnefejl, men et fix er stadig ikke garanteret ved hver optagelse, hvis modulet reelt
  mister lock i det øjeblik.

### Handover 2026-07-04 — Peters egentlige diagnose: GPS mister fix når kamera-relæet tændes (v3)
- **Peter satte fingeren på den rigtige forklaring:** live-test (`cgps -s`, `gpspipe`) mens
  kameraet var i ro gav fix på under 3 sekunder — men alle 3 forsøg under selve
  optagelsen (kamera-relæ tændt) fejlede. Peters diagnose: GPS-modtageren mister
  strøm/fix når kamera-relæet (GPIO 356) tændes, formentlig et strømforsyningsfald.
  Da kamera+edge sidder fastmonteret og aldrig flytter sig, er løsningen at læse GPS
  FØR relæet tændes, ikke midt i optagelsen hvor GPS'en alligevel er "død".
- **Bekræftet i koden (via Explore-subagent):** hele optage-cyklussen i `edge/agent.py`
  `_do_capture_cycle()` (linje 706-896) holder kamera-relæet tændt fra linje 720
  (`_camera_power_on`) til linje 893 (`_camera_power_off`, i `finally`-blokken) — dvs.
  under HELE forløbet inkl. `_write_sidecar()`/`_write_xmp_metadata()` (kaldt fra
  `capture_image()`, linje 541/548/551 i `gphoto2_driver.py`), hvor `_read_gpsd_fix()`
  hidtil altid blev forsøgt live. Agentens idle-ventetid mellem optagelser (`_tick()`,
  linje 702) har relæet slukket hele tiden og var uudnyttet til dette formål.
- **Løsning (v3, additiv oven på v2's line-by-line-læsning):**
  1. `GPhoto2Driver.__init__`: nyt felt `self._last_gps_fix: dict = {}`.
  2. Ny metode `refresh_gps_cache()`: kalder `_read_gpsd_fix()` og opdaterer cachen KUN
     ved et succesfuldt fix — et fejlet forsøg overskriver aldrig en allerede god cache
     (en gammel god fix er langt bedre end intet, da kameraet ikke flytter sig).
  3. `agent.py` `_tick()`: kalder `self._driver.refresh_gps_cache()` lige før
     sleep/idle-ventetiden (linje ~697-702) — dvs. hver gang løkken kører mens relæet er
     slukket (mindst hvert 60. sekund pga. den eksisterende wait-logik).
  4. `_write_sidecar()`/`_write_xmp_metadata()`: bruger nu `self._last_gps_fix` i stedet
     for et live-kald, hvis cachen er fyldt. Falder tilbage til et (formentlig forgæves)
     live-kald kun ved allerførste optagelse efter opstart, før cachen er nået at blive
     fyldt via idle-loopet.
- **Verifikation:** nyt testscript (`test_gps_cache.py`), 5 scenarier: cache opdateres ved
  godt fix; cache overskrives IKKE af et fejlet forsøg; rører intet når `gps_source` er
  `manual`; `_write_sidecar()` bruger cachen uden live-kald når fyldt; falder korrekt
  tilbage til live-kald når cachen er tom. Alle bestod. `py_compile` OK på begge filer.
- **Deploy:** denne gang som en ren unified diff (`gps_v3_cache.patch`, lagt i
  workspace-roden) i stedet for et Python-patch-script — verificeret at den applicerer
  rent (`patch -p1 --dry-run`) mod den nøjagtige commit der allerede er udrullet på
  edgen (`df26248d`), og at resultatet er byte-identisk med den lokalt redigerede/
  testede fil. Simplere og mere robust end de tidligere Python-baserede patch-scripts.
- **v3 deployet af Peter (commit `79eba56e`), patch applied rent (offset -15 linjer,
  harmløst — konteksten matchede korrekt et andet sted end den oprindelige linje).**

### Handover 2026-07-04 (fortsat) — v4: præcis timing af GPS-læsning (Peters uddybning)
- **Peters uddybning efter v3:** "Du skal læse GPS'en 10 sek. før du tænder relæet. Der
  går lang tid efter du slukker relæet før der er fix." v3's placering (kald
  `refresh_gps_cache()` ved starten af HVER idle-tick, dvs. lige efter forrige relæ-
  slukning) ramte dermed det værst tænkelige tidspunkt — mindst mulig tid til at GPS'en
  kan nå at komme sig, siden det sker umiddelbart efter relæet netop er slukket.
- **Fandt den rigtige krog i koden:** `_should_capture()` (agent.py) returnerer `True`
  `lead_s = warmup_s + 3` sekunder (typisk ~13 sek) FØR relæet rent faktisk tænder — det
  er selve warmup-mekanismen, og `_do_capture_cycle()` tænder relæet stort set med det
  samme når den kaldes. Det er derfor det ideelle sted at læse GPS: lige inden i
  `if capture_due:`-grenen, før selve capture-cyklussen dispatches. På det tidspunkt har
  der været maksimal tid siden SIDSTE relæ-slukning (hele idle-perioden, typisk ~8-9 min
  ved et 10-minutters interval) til at GPS'en kunne nå at komme sig.
- **Rettelse (v4):** flyttet `refresh_gps_cache()`-kaldet fra "hver idle-tick" til
  specifikt inde i `if capture_due:` (efter suppressed-tjekket, før dispatch til
  `_do_capture_cycle()`/`_do_multi_capture_cycle()`) — kaldes nu præcis én gang pr.
  optagelse, ~13 sekunder før relæet tænder, i stedet for gentagne gange gennem hele
  idle-perioden (hvoraf de fleste forsøg ville være spildte/for tidlige alligevel).
- **Verifikation:** `py_compile` OK, driver-testene (`test_gps_cache.py`) genkørt uden
  regression (rører ikke selve driver-logikken, kun hvornår agenten kalder den).
- **Deploy:** ny lille unified diff (`gps_v4_timing.patch`, kun `edge/agent.py`),
  verificeret at den applicerer rent mod den præcise `79eba56e`-commit der allerede kører
  på edgen, og at resultatet er byte-identisk med den lokale testede fil.
- **IKKE committet/deployet endnu** — afventer Peters kørsel på edgen.

### Handover 2026-07-04 (fortsat) — v4 bekræftet virkende af Peter
- **Peter bekræftede:** "GPS virker nu. Tak." — v4 (præcis GPS-læsning ~13 sek. før
  relæet tænder, jf. ovenstående) er deployet og løser problemet i produktion. GPS-sagen
  betragtes som lukket (fix 1-4 alle bekræftet).
- **Sideløbende afklaret:** Peter spurgte hvorfor lab mode blev aktiveret på
  TL-C87FF9587CA0. Konklusion: `debug_mode.enabled` er en ren per-enhed config-nøgle
  (ingen arv fra Site/Customer/ConfigDefaults), sat udelukkende via
  `PUT /api/admin/devices/{id}/debug` — typisk fra Kamera-laboratorium-siden i UI'en.
  Ingen automatik fandtes der kunne forklare aktiveringen; mest sandsynligt en efterladt
  flag fra en tidligere test-session, der ikke blev slået fra igen. Ingen kodeændring
  foretaget, kun undersøgt og forklaret.
- **Åbne punkter:** Task #28 (proveniens-UI for alle metadata-kilder) afventer stadig.
  Merge-plan for `claude/capture-camera-location-2026-07-03` ind i `main` afventer fælles
  scoping med Codex.

### Handover 2026-07-04 (fortsat) — Risiko + go-live opdateret med GPS/lab-mode-fund
- **Peter bad om:** arbejd videre "som det passer bedst", med fokus på at risikodokument og
  go-live-checkliste sandsynligvis mangler at afspejle GPS- og lab-mode-arbejdet.
- **Gennemgået:** `RISK_ASSESSMENT_v10.md` og `GO_LIVE_CHECKLIST_v10.md` havde ingen
  eksplicit linje for GPS/lokationsdata eller debug/lab mode — begge dokumenter var
  uændrede siden 2026-06-23/07-02.
- **Rettet i `RISK_ASSESSMENT_v10.md`:**
  1. R12 (GDPR) udvidet med note om at GPS/lokationsmetadata nu er implementeret og
     verificeret i produktion — DPIA/retention-arbejdet skal eksplicit dække feltet.
  2. Ny **R17 — Debug/lab mode kan efterlades aktiveret uden overvågning**: fundet
     aktiveret på TL-C87FF9587CA0 under GPS-fejlsøgningen, formentlig en efterladt
     test-flag. Ingen adgangskompromittering (kræver admin-rolle at sætte), men
     operationel risiko (relæ konstant tændt, plan brydes, reduceret GPS-pålidelighed).
     Score 🟡 6. Anbefaling: CMDB-indikator, auto-timeout, audit-log ved til/frakobling.
  3. Risikooversigt (§10) og P2-behandlingsplan (§11) opdateret; dokumenthistorik-linje
     tilføjet.
- **Rettet i `GO_LIVE_CHECKLIST_v10.md`:**
  1. Note under sektion G: DPIA (G-01)/retention (G-02) skal eksplicit dække
     GPS-feltet, ikke kun billedet.
  2. Ny linje F-06: dashboard/alarm for enheder i debug/lab mode — henviser til R17.
- **Ingen kodeændringer** — kun dokumentation. Ingen go/no-go-status ændret (R17 er ikke
  blokerende, kun tilføjet til P2/ønsket-lag).
- **Filer rørt:** `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`,
  `Dokumentation/HANDOVER_LOG.md`.
- **Næste skridt:** Task #28 (proveniens-UI, alle metadata-kilder) tages op nu.

### Handover 2026-07-04 — Codex starter QA/fokusklassificering Nordre Villavej
- **Starter:** Undersøger hvorfor billeder fra `Nordre Villavej 17c` tilsyneladende
  alle/for mange bliver markeret som `Dybdeskarphed/fokus`.
- **Scope:** Edge QA/optimizer og headend backfill/visning af QA-sidecar. Undgår at røre
  Claudes aktive dokument-/proveniens-UI-spor ud over denne lille handover-note.
- **Første hypoteser:** Edge optimizerens `depth_of_field_issue`-regel er muligvis for
  aggressiv for faste, skråt fotograferede by-/tag-scener, hvor kanter naturligt er
  blødere end center; alternativt er historiske QA-sidecars/backfill skrevet med en
  gammel regel og skal reprocesses efter fix.

### Handover 2026-07-04 — Codex stopper QA/fokusklassificering midlertidigt
- **Fund:** Nordre Villavej var ikke "alle" markeret som dybdeskarphed, men der var en
  reel falsk positiv gruppe. Root cause: edge NPU-runnerens CPU-fallback tog
  autonomous optimizerens øverste anbefaling som QA-årsag; optimizerens gamle regel
  `center_blur` høj + relativt lavere `edge_blur` ramte faste by-/tag-scener med meget
  skarp midte og mere rolig/teksturfattig kant.
- **Kodeændring:** `edge/ai/autonomous_optimizer.py` strammet, så
  `depth_of_field_issue` kun bliver en QA-handling hvis kanterne også er absolut bløde,
  ikke kun relativt blødere end midten. Samtidig tilføjet en særskilt observation/tag i
  edge-payload: `center_sharp_soft_edges` som optik-/scene-signal, ikke fejl.
- **Backfill-status:** Tørkørsel på 500 Nordre-billeder gav 0 `depth_of_field_issue`;
  dagens sample gav 63 `ok`, 5 `direct_sun_reflection`, 0 dybdeskarphed. Fuld backfill
  blev startet, først 7.500 rækker uden edge-tag, derefter stoppet; anden kørsel nåede
  ca. 5.000 rækker med edge-tag i `edge_ai.tags`.
- **Vigtigt datavalg:** Peter foreslog korrekt, at hver QA/AI-model bør have egen DB-plads,
  så edge-eksperimenter ikke forurener dyre Gemini/Ollama-tags. Derfor blev backfill
  stoppet, og ændringen der additivt skrev edge-tagget ind i `captures.ai_tags` blev
  fjernet igen.
- **Datarydning:** Midlertidigt `center_sharp_soft_edges` fjernet fra fælles
  `captures.ai_tags` på 1.083 rækker. Eksisterende Gemini/Ollama-tags blev bevaret.
  Verificeret efterfølgende: 0 rækker med `center_sharp_soft_edges` i `ai_tags`.
- **Næste anbefalede arkitektur:** Opret model-separat lager, fx
  `capture_analysis_results`/`capture_model_tags` med felter for `capture_id`,
  `engine` (`edge_cv_v1`, `edge_npu`, `headend_ollama`, `gemini_cloud`), `model`,
  `version`, `scope`, `result_json`, `tags_json`, `confidence`, `created_at`, og lad UI
  vælge/overlaye kilder uden at overskrive `captures.ai_tags`. Vigtigt: Ollama og
  Gemini skal også ligge separat fra hinanden, ikke kun separat fra Edge QA, så lokal
  headend-tuning kan eksperimentere uden at forurene dyrt købte Gemini/cloud-tags.
- **Verifikation:** `py_compile` OK på `edge/ai/autonomous_optimizer.py` og
  `headend/tools/backfill_edge_qa.py`.

### Handover 2026-07-04 — Codex fortsætter: model-separeret AI/QA-lager
- **Peter præciserede:** Ollama og Gemini skal også holdes separat fra hinanden, ikke kun
  Edge vs. headend. Formål: kunne eksperimentere/tune Ollama og edge/NPU uden at
  forurene de dyrt købte Gemini/cloud-resultater.
- **Implementeret additivt:**
  1. Ny helper `headend/ai/model_results.py` med engine-konstanter:
     `edge_cv_v1`, `edge_npu`, `headend_ollama`, `gemini_cloud`.
  2. Ny tabel/migration `headend/migrations/v9_capture_model_results.sql`.
  3. ORM-model `CaptureModelResult` i `headend/ai/ai_models.py`.
  4. `headend/tools/backfill_edge_qa.py` skriver nu edge-QA i
     `capture_model_results` (`engine=edge_cv_v1`, `result_kind=qa`) og IKKE i
     `captures.ai_tags`.
  5. Live headend AI (`headend/ai/integration.py`) skriver fremover også til
     model-tabellen med `engine=headend_ollama` eller `gemini_cloud`, beregnet ud fra
     payload/model.
  6. Gemini batch-resultater (`headend/main.py`) skriver fremover til
     `engine=gemini_cloud`.
  7. Klassisk headend backfill (`headend/ai/backfill.py`) skriver fremover til
     `headend_ollama` eller `gemini_cloud` afhængigt af faktisk model.
- **Kompatibilitet:** `captures.ai_result` og `captures.ai_tags` bevares som legacy/
  aktuelt UI-lag indtil UI/søgning er migreret. Ny tabel er parallel og additiv.
- **DB-verifikation:** Helper oprettede tabellen på lokal headend DB. Smoke-test skrev og
  slettede en midlertidig `schema_smoke_test` række. Derefter kørte Codex en lille
  edge-backfill på 3 Nordre-billeder: `capture_model_results` har nu 3 rækker med
  `engine=edge_cv_v1`, `result_kind=qa`, `tags_json=["center_sharp_soft_edges"]`,
  og `captures.ai_tags` har stadig 0 forekomster af `center_sharp_soft_edges`.
- **Kodeverifikation:** `py_compile` OK på `headend/ai/model_results.py`,
  `headend/tools/backfill_edge_qa.py`, `headend/ai/integration.py`,
  `headend/ai/backfill.py`, `headend/ai/ai_models.py`, `headend/main.py` og
  `edge/ai/autonomous_optimizer.py`.
- **Næste skridt:** Kør fuld Nordre/Travbyen edge-QA backfill ind i den nye tabel, og
  byg derefter UI/API-overlay der kan vise/filt­rere pr. motor:
  Edge CV/NPU vs. Ollama vs. Gemini.

### Handover 2026-07-04 — Codex starter service/support UI + CLI
- **Peter bad om:** gennemgang af edge service/support UI og CLI. Der er overlap mellem
  Tid- og System-menuen, og nogle menupunkter fejler.
- **Scope:** `edge/scripts/totp-service.py` og `edge/tools/bootstrap_cli.py`.
  Undgår AI/GPS/metadata-spor ud over eventuelle statusvisninger.
- **Første fund:** `/mgmt/system` genbruger hele Tid-siden og injicerer blot en System-card
  med JavaScript, så brugeren reelt ser både Tid og System. Kamera-actions i CLI’en
  tjekker action-paths med `read_gphoto_current()`, som kan returnere `None` for gyldige
  action-widgets uden `Current:` felt; det kan give falsk “Autofokus-action blev ikke
  fundet”.

### Handover 2026-07-04 — Codex stopper service/support UI + CLI runde 1
- **Rettet i `edge/scripts/totp-service.py`:**
  1. `load_config()` er defensiv; manglende/korrupt `/etc/timelapse/bt-config.yaml`
     crasher ikke længere management-UI, men bruger fabriks-/service-defaults.
  2. `/mgmt/system` er nu en selvstændig System-side. Den viser System, Service, Tid,
     Netværk og Storage/upload og viser ikke længere hele Tid-konfigurationsformularen.
  3. Ny `/mgmt/system/action` med knapper til Edge/TOTP status, logs, disk, netværk og
     bekræftede restart-actions.
  4. TOTP-sync vender tilbage til System-siden i stedet for at gengive Tid-siden.
- **Rettet i `edge/tools/bootstrap_cli.py`:**
  1. Autofokus/focus-drive bruger nu en egentlig `gphoto2 --get-config` existence-probe
     (`gphoto_config_exists`) i stedet for at kræve et `Current:` felt. Det fjerner falske
     “action blev ikke fundet” på action-widgets.
  2. Headend-test resolver URL fra `bootstrap.yaml`, `config.yaml`, `management.headend_url`
     eller `HEADEND_URL`.
  3. Headend-test prøver nu `/api/health` først når URL ender på `/api`, og falder tilbage
     til `/health`.
- **Lokal verifikation:** `py_compile` OK for `totp-service.py`, `bootstrap_cli.py` og
  `gphoto2_driver.py`. Render-test OK for Tid/System/Tekniker. CLI `--status`,
  `--npu-status`, `--gps-status` og `--test-headend` testet lokalt; manglende hardware
  rapporteres pænt.
- **Deploy/verifikation på Orange Pi `timelapse0101` / `192.168.86.134`:**
  1. Kopieret `totp-service.py` og `bootstrap_cli.py` til `/opt/timelapse/edge/...`.
  2. `py_compile` OK på edgen.
  3. `timelapse-totp` genstartet og aktiv; `timelapse-edge` fortsat aktiv.
  4. `bootstrap_cli.py --test-headend` rammer nu
     `https://timelapse.froekjaer.dk/api/health -> HTTP 200` med JSON health payload.
  5. System-actions `status-edge`, `status-totp`, `disk`, `network` testet OK via
     `_run_system_action()`.
  6. `--camera-summary` melder p.t. ingen gphoto2-kamera fundet på edgen; det er en
     hardware/tilslutningsstatus, ikke UI/CLI-crash.
- **Ikke rørt:** Headend/DevicePage/Claude-proxy ændringer i arbejdstræet er andre spor.
  Der er et separat Claude/proveniens-diff i `headend/main.py`, som bør reviewes særskilt
  før headend-commit/merge.

### Handover 2026-07-04 (fortsat) — Task #28: kortlægning + første proveniens-UI-tilføjelse
- **Kortlægning (subagent, read-only):** alle metadata-kilder til en Capture kortlagt —
  sidecar JSON (`_write_sidecar()`, edge), edge OpenCV-kvalitet (`edge/capture/quality.py`,
  i main), edge NPU/AI-QA-pakke (`edge/ai/*`, KUN på feature-brancher, IKKE i main/prod),
  headend Ollama/Gemini-analyse (`headend/ai/integration.py` + `ai_router.py`), Gemini
  batch-jobs (`AiBatchJob`, main.py), og hele `Capture`-skemaets kolonner. Konklusion: UI'en
  (`DevicePage.tsx`) viste allerede model-navn og de fleste felter, men **ingen eksplicit
  lokal/cloud-label** — kun modelnavnet (fx "qwen3-vl:8b" vs. "gemini-2.5-flash"), som
  kræver at brugeren kender navnekonventionen for at vide om analysen kørte lokalt eller i
  skyen.
- **Rettelse (additiv, lille scope, samme mønster som GPS-kilde-labelen):**
  1. `headend/ai/integration.py`: `payload["engine"] = "cloud" if used_cloud else "local"`
     tilføjet til live-analyse-flowet (Ollama/eskalering til Gemini).
  2. `headend/main.py` (Gemini batch-resultat-parsing): `"engine": "cloud"` tilføjet —
     batch-jobs kører altid via Gemini/Vertex AI Batch API, aldrig lokal Ollama.
  3. `timelapse-ui/src/pages/DevicePage.tsx`: ny "Motor"-linje i QA-panelet, viser
     "🖥️ Lokal" / "☁️ Cloud" / "🔧 Edge (…)" ud fra `ai.engine`/`ai.source`. Ældre
     analyser (før denne dato) viser "— (før 2026-07-04)" i stedet for at gætte.
     "Model"-linjen viser nu kun selve modelnavnet (fjernet `?? ai.engine`-fallback, som
     ville have vist "local"/"cloud" som om det var et modelnavn). Kvalitet-sektionens
     overskrift mærket "(🔧 Edge/OpenCV)" for at gøre kilden eksplicit også der.
  4. Edge-siden (`edge_ai`/NPU) rørt IKKE — den er stadig kun på feature-brancher, ikke i
     produktion, så "🔧 Edge"-grenen af koden er forberedt men ikke aktivt brugt endnu.
- **Verifikation:** `py_compile` OK på `headend/main.py` + `headend/ai/integration.py`;
  `tsc --noEmit` OK på hele `timelapse-ui` (ingen nye fejl).
- **Ikke rørt (bevidst, ikke mit):** `Dokumentation/Claude_Kritisk_Statusgennemgang_2026-07-03.md`
  havde allerede en uncommittet, verificeret statusopdatering liggende fra tidligere i
  sessionen (fase 3/4 backfill-bekræftelse) — committes separat, uændret indhold.
  `claude_proxy.py` (untracked, ukendt oprindelse) er IKKE rørt eller committet.
- **Filer rørt (denne commit):** `headend/ai/integration.py`, `headend/main.py`,
  `timelapse-ui/src/pages/DevicePage.tsx`.
- **Afventer:** Peters commit+deploy (kommandoer givet separat), derefter en ny produktions-
  analyse for at bekræfte Motor-labelen viser korrekt i UI'en.

### Handover 2026-07-04 (fortsat) — Læse-side + UI for Codex' model-separerede AI/QA-lager
- **Til Codex:** ja, det er mig (Claude) der har det verserende `headend/main.py`-diff —
  se detaljer nedenfor. Kun ét nyt endpoint tilføjet, ingen ændring af eksisterende
  linjer i filen udover det additiv. Review meget velkomment før I mergér/commiter jeres
  eget spor i samme fil.
- **Peter bad om:** en god måde at præsentere Codex' nye `capture_model_results`-tabel
  (edge_cv_v1/edge_npu/headend_ollama/gemini_cloud) i UI'en — "farver/tabeller/hvad tænker
  du" — som et debugging/sammenligningsværktøj mens modellerne tunes.
- **Fandt (research):** Codex' tabel (se entry "Codex fortsætter: model-separeret AI/QA-
  lager") var på undersøgelsestidspunktet **skrive-only** — ingen API-endpoint eksponerede
  den, og ingen UI-kode refererede til den. `ENGINE_EDGE_NPU`-konstanten var defineret men
  aldrig brugt noget sted (edge NPU-pipelinen er stadig kun på feature-brancher).
- **Tilføjet (additivt, read-only, rører intet af Codex' skrive-logik):**
  1. `headend/ai/model_results.py`: ny `get_capture_model_results(db, capture_id)` —
     læser alle rækker for et billede, parser `result_json`/`tags_json` defensivt
     (håndterer både allerede-parsede dicts/lister fra psycopg2's JSONB-adapter og
     rå strenge), sorteret nyeste først.
  2. `headend/main.py`: nyt endpoint `GET /api/captures/{capture_id}/model-results`,
     samme auth-mønster som `PUT /api/captures/{capture_id}/tags` (`require_role("viewer")`
     + `_capture_is_allowed()`-tenant-tjek). Rører ikke `ai_result`/`ai_tags`.
  3. `timelapse-ui/src/pages/DevicePage.tsx`: ny `ModelResultsPanel`-komponent i
     metadata-panelet — ét farvekodet kort pr. motor-resultat (🔧 Edge CV = grøn,
     🔷 Edge NPU = cyan, 🖥️ Ollama = blå, ☁️ Gemini = lilla, ukendt motor = grå
     fallback), viser model/version, fremhævede result-felter (scene_dk, quality_flag,
     blur_score m.fl.), tags som chips, kilde + tidsstempel, og en udfoldelig "Rå
     data"-sektion med det fulde `result_json`. Vises uafhængigt af sidecar (egen
     fetch mod headend-DB'en via ny `useEffect` keyed på `c.id`), og viser en tydelig
     "ingen resultater endnu"-besked frem for at forsvinde stille, da tabellen stadig
     er ved at blive fyldt op.
- **Fejl fanget og rettet undervejs:** `ai`-variablen i `DevicePage.tsx`s eksisterende
  QA-kode kan være `null` — min første `engineLabel`-beregning (forrige entry) manglede
  et null-guard, som kun `tsc -b` (build-scriptets rigtige kommando) fangede, ikke min
  lokale `tsc --noEmit`-check. Rettet med `!ai ? null : ...`, verificeret med `tsc -b`
  denne gang (samme kommando som `npm run build` bruger), og Peter bekræftede en ren
  build efter rettelsen.
- **IKKE verificeret mod en rigtig Postgres:** sandkassen her har hverken root eller en
  kørende Postgres-instans, så `get_capture_model_results()`s rå SQL er kun kode-
  gennemgået (samme tabel/kolonnenavne som Codex' allerede live-testede
  `upsert_capture_model_result()`), ikke kørt end-to-end. **Peter bør efter deploy
  kalde endpointet mod et billede fra Nordre-smoke-testen** (de 3 rækker med
  `engine=edge_cv_v1` Codex nævner) for at bekræfte det reelt virker, før det regnes
  for færdigt.
- **Filer rørt:** `headend/ai/model_results.py`, `headend/main.py`,
  `timelapse-ui/src/pages/DevicePage.tsx`.
- **Afventer:** Peters commit+deploy, derefter live-smoke-test af det nye endpoint.

### Handover 2026-07-04 — Codex starter historisk AI/QA model-result backfill
- **Peter bad om:** gå alle billeder igennem og afklare om Travbyen er tagget af Gemini.
- **Første DB-måling:** `capture_model_results` indeholdt kun 3 `edge_cv_v1/qa` rækker
  og 4 `headend_ollama/analysis` rækker. Travbyen havde 6.158 captures, 5.551 legacy
  `ai_tags`, 6.158 legacy `ai_result`, men 0 model-separerede rækker.
- **Travbyen-konkret:** Kamera 1: 5.029/5.029 legacy-tagget; 4.953 med model
  `gemini-2.5-flash` og 76 med `llava-phi3`. Kamera 2: 522 legacy-tagget med
  `qwen2.5vl:7b`, 607 med legacy `edge_cv_v1` og ingen `ai_tags`.
- **Plan:** først migrere historiske legacy `ai_result/ai_tags` additivt ind i
  `capture_model_results` pr. motor (Gemini/Ollama/Edge CV), uden at ændre
  `captures.ai_tags`; derefter køre Edge CV backfill mod originalbillederne ind i den
  nye modeltabel.

### Handover 2026-07-04 — Codex færdiggjorde historisk AI/QA model-result backfill
- **Legacy-migration udført:** nyt værktøj `headend/tools/backfill_model_results_from_legacy.py`
  migrerede 27.784 historiske `captures.ai_result` rækker additivt til
  `capture_model_results`, fordelt på `gemini_cloud` 26.478,
  `headend_ollama` 677 og `edge_cv_v1` 629. Værktøjet ændrer ikke
  `captures.ai_tags`, `capture_tags` eller cloud-købte Gemini-data.
- **Edge CV-backfill udført mod originalbilleder:** `headend/tools/backfill_edge_qa.py`
  blev kørt mod canonical originals. Første fulde kørsel behandlede 27.784/27.784 uden
  manglende filer eller exceptions; tre nye Nordre-billeder kom ind imens, og blev
  efterfølgende taget med via `--only-missing-edge`.
- **Værktøjsfix:** `--only-missing-edge` i `backfill_edge_qa.py` brugte før legacy
  `captures.ai_result.edge_ai`; rettet til at kigge i den nye `capture_model_results`
  tabel (`engine=edge_cv_v1`), så flaget matcher UI'ets nye datamodel.
- **Slutstatus i DB:** 27.787 captures og 27.787 `edge_cv_v1/qa` model-resultater.
  `capture_model_results` indeholder samlet `edge_cv_v1/qa` 27.787,
  `gemini_cloud/analysis` 26.478 og `headend_ollama/analysis` 680.
- **Site-dækning:** Nordre Villavej 17c: 21.629 captures, 21.629 Edge CV,
  21.525 Gemini, 82 Ollama, 21.607 legacy tags. Travbyen: 6.158 captures,
  6.158 Edge CV, 4.953 Gemini, 598 Ollama, 5.551 legacy tags.
- **Travbyen-konkret:** Kamera 1: 5.029 captures, alle har Edge CV og legacy tags;
  4.953 Gemini og 76 Ollama/llava. Kamera 2: 1.129 captures, alle har Edge CV;
  522 Ollama/qwen legacy tags og ingen Gemini-rækker.
- **Edge CV-årsager efter fuld kørsel:** `ok` 21.372, `direct_sun_reflection` 4.499,
  `underexposure_or_camera_blocked` 1.527, `focus_or_lens_issue` 306,
  `snow_or_dirt_on_lens` 78, `condensation_or_soft_lens_obstruction` 5.
- **Vigtigt:** kontrol viste `edge_tag_pollution = 0`, så Edge CV har ikke skrevet
  `center_sharp_soft_edges`/`depth_of_field_issue` eller lignende ind i legacy
  `captures.ai_tags`. Gemini/Ollama-tags er ikke slettet eller overskrevet.

### Handover 2026-07-04 — Codex starter fix af lokal servicetekniker-UI/CLI
- **Peter rapporterede:** servicetekniker-menuen på Edge er langsom, og der kommer
  ind imellem `{"detail":"Method Not Allowed"}`.
- **Foreløbigt fund:** `edge/scripts/totp-service.py` rendrer POST-resultatsider direkte
  på `/mgmt/technician/action`, `/mgmt/technician/focus`, `/mgmt/technician/config`,
  `/mgmt/technician/capture` og `/mgmt/system/action`, mens HTML'en har
  `<meta http-equiv="refresh" content="45">`. Når browseren auto-refresher efter en
  POST, bliver det til GET mod POST-only endpointet og giver 405. Derudover kalder hver
  sidevisning `_technician_snapshot()`, som via `bootstrap_cli.collect_local_status()`
  kører `gphoto2 --auto-detect` og flere `--get-config` kald; det gør UI langsomt,
  især når kamera ikke er tilsluttet/ikke vågnet.
- **Plan:** gør auto-refresh safe mod GET-sider, tilføj GET-fallback/redirects for
  POST-only action-URLs, og gør status-snapshot hurtigt ved kun at køre kamera-probe
  ved eksplicit "Kamera status"/rapport/detaljeret CLI.

### Handover 2026-07-04 — Codex færdiggjorde fix af lokal servicetekniker-UI/CLI
- **Rettet:** tekniker- og system-siderne auto-refresher nu til rene GET-sider
  (`/mgmt/technician` og `/mgmt/system`) i stedet for den aktuelle POST-action URL.
  Der er også tilføjet GET-fallback/303-redirect for `/mgmt/technician/action`,
  `/mgmt/technician/focus`, `/mgmt/technician/config`, `/mgmt/technician/capture`
  og `/mgmt/system/action`.
- **Performance:** `_technician_snapshot()` kalder nu
  `bootstrap_cli.collect_local_status(..., include_camera=False)`, så hver sidevisning
  ikke længere kører `gphoto2 --auto-detect` og seks `--get-config` kald. Kamera-probe
  køres fortsat ved eksplicit "Kamera status", detaljeret CLI-status og tekniker-
  rapport.
- **Menu-overlap:** System-sidens "Tid"-card er fjernet; Tid-menuen er fortsat stedet
  for tidskilder, TOTP-vindue og tidsopsætning.
- **Deploy/verifikation:** deployet til `orangepi@192.168.86.134`
  (`/opt/timelapse/edge/scripts/totp-service.py` og
  `/opt/timelapse/edge/tools/bootstrap_cli.py`), `timelapse-totp` genstartet og aktiv.
  Remote route-inspektion viser både GET og POST for action-URL'erne; remote hurtigt
  snapshot uden kamera-probe målte ca. 0,79 sek. `py_compile` OK lokalt og på edgen.

### Handover 2026-07-04 — Codex starter strukturering af service/support netværksmenu
- **Peter bad om:** et mere struktureret servicetekniker-menu-system, hvor relevante
  onsite-parametre kan konfigureres, især WiFi, IP-adresse (DHCP/statisk), routing,
  DNS og lignende.
- **Scope:** `edge/tools/bootstrap_cli.py` og `edge/scripts/totp-service.py`. Målet er
  at bruge NetworkManager/nmcli som single local source of truth for netværk, mens
  `local_network.yaml` fortsat kun holder TimeLapse-præferenceorden (`ethernet/wifi/4g`).
- **Plan:** CLI får særskilt "Netværk og forbindelse"-menu + non-interactive flags til
  UI; TOTP UI får ny Netværk-side med status, WiFi-connect, IPv4 DHCP/statisk,
  DNS/gateway/route metric og prioritet. Kamera/QA-menuen forbliver separat.

### Handover 2026-07-04 — Codex udvidede service/support UI/CLI med netværk og fototeknik
- **CLI-struktur:** topmenuen er nu delt i Overblik, Installation, Netværk og
  forbindelse, Fototeknik/kamera/testbilleder, Fejlsøgning/logs og Lokal tekniker-UI.
  Netværk har status/DNS/routing, WiFi connect, Ethernet/WiFi IPv4 DHCP/statisk,
  4G modem, forbindelsesprioritet og Headend-test. Installation er nu bootstrap/
  headend/doctor/rapport.
- **Non-interactive CLI flags til UI/drift:** `--network-status`, `--wifi-connect`,
  `--ipv4-config DEVICE MODE ADDRESS GATEWAY DNS METRIC`, `--network-preference`,
  `--photo-status` og `--photo-setting KEY VALUE`.
- **TOTP UI:** ny `/mgmt/network` side med status, WiFi-formular, IPv4 DHCP/statisk
  formular (adresse/gateway/DNS/route metric), prioritet og Headend-test. POST-targets
  har GET-fallbacks ligesom tekniker/system.
- **Fototeknik:** Tekniker-siden har nu dropdown til named camera settings:
  `exposure_comp`, `iso`, `white_balance`, `shutter_speed`, `aperture`,
  `focus_mode`, `image_format`, plus "Fotostatus". Disse mapper til kendte gphoto2
  paths og kører i maintenance mode, så edge-agenten ikke konkurrerer om kameraet.
- **Sikker netværksadfærd:** IPv4-konfiguration modificerer aktiv NetworkManager-
  connection når den findes; WiFi statisk IP kræver først aktiv SSID-tilslutning,
  så vi ikke opretter en invalid WiFi connection uden SSID.
- **Verifikation før deploy:** `python3 -m py_compile edge/tools/bootstrap_cli.py
  edge/scripts/totp-service.py` OK; CLI help viser nye flags; `git diff --check` OK.

### Handover 2026-07-04 — Codex tilføjede lokal CLI-konsol i service/support UI
- **Peter bad om:** mulighed for at komme ud i CLI'en fra UI'en.
- **Implementeret:** ny `/mgmt/cli` fane i lokal TOTP UI. Den kører
  `/opt/timelapse/edge/tools/bootstrap_cli.py` og viser stdout/stderr direkte i
  browseren. Der er hurtigknapper for Overblik, Netværk, Headend, Kamera, Fotostatus,
  GPS, NPU og Doctor samt et tekstfelt til egne `bootstrap_cli.py` argumenter.
- **Sikkerhed:** UI'en er ikke en fri shell. Den parser argumenter med `shlex.split`
  og tillader kun allowlistede `bootstrap_cli.py` flags (`--network-status`,
  `--photo-status`, `--photo-setting`, `--focus-drive`, `--capture-test`, osv.).
  Ukendte flags og shell-lignende input afvises før subprocess-kald.
- **Verifikation:** `py_compile` OK; parser-test godkendte kendte kommandoer og afviste
  `--bad-flag` samt `--network-status; rm -rf /`.

### Handover 2026-07-04 (nat) — Claude fortsætter alene: P0/P1-oprydning fra RISK/GO-LIVE
- **Peter er gået i seng** og bad mig fortsætte selvstændigt med de prioriterede
  blockers fra `RISK_ASSESSMENT_v10.md` §11 og `GO_LIVE_CHECKLIST_v10.md`. **Vigtig
  grænse:** jeg har ingen shell-adgang til Mac Mini'en eller Orange Pi'en — kun til
  git-repoet. Alt der kræver live kommando-eksekvering (nginx-genstart, backup-kørsel,
  nøgle-rotation) forberedes som færdigtestede diffs/runbooks, IKKE eksekveret. Ren
  kode/dokumentation, jeg selv kan verificere (py_compile/tsc/tests), laves færdig.
- **KRITISK FUND (utilsigtet, fundet undervejs i DPIA-research) — rettet:**
  `headend/ai/ai_router.py:42` importerede `from gdpr_manager import GDPRManager` på
  MODUL-niveau. `gdpr_manager.py` **findes slet ikke i kodebasen** — kun importeret,
  aldrig implementeret (bekræftet reproducerbart: `ModuleNotFoundError: No module
  named 'gdpr_manager'`). Da `review_api.py::_run_gemini_for_approved` (kørt som
  `BackgroundTasks.add_task` fra `POST /api/review/escalation/approve`) lazy-importerer
  `ai.ai_router`, betød dette at **hele Gemini-eskalerings-godkendelsesflowet har
  fejlet stille siden denne kode blev skrevet**: admin får svaret "Gemini analyserer
  X billeder i baggrunden" (200 OK), men baggrundsjobbet crasher øjeblikkeligt på
  importen — FastAPI's BackgroundTasks logger exceptionen, men returnerer den aldrig
  til brugeren. Godkendte eskalerede billeder er derfor formentlig ALDRIG blevet
  sendt til Gemini, uden at nogen har opdaget det.
  - **Rettelse:** gjort importen lazy + guardet (`try/except ModuleNotFoundError` →
    `GDPRManager = None`), og den eneste brugssted (`_save_gdpr_detections`, allerede
    exception-guardet omkring selve kaldet) logger nu en tydelig fejl i stedet for at
    lade importfejlen forplante sig til hele modulet. Dette **retter selve
    eskalerings-bugget** (routeren kan nu importeres og bruges normalt) — det retter
    IKKE at GDPR-detektioner (ansigt/nummerplade/person) fortsat ikke kan gemmes
    isoleret, da `gdpr_manager.py` reelt mangler at blive skrevet. Det er en separat,
    allerede kendt del af R12 (GDPR-evidens mangler) og løses ikke her.
  - **Verificeret:** reproduceret fejlen først (`ModuleNotFoundError` bekræftet i
    isoleret Python-kald), rettet, derefter bekræftet at `from ai.ai_router import
    get_ai_router` (den nøjagtige linje der crashede baggrundsjobbet) nu lykkes, og at
    `_save_gdpr_detections` logger gracefully i stedet for at kaste en exception ved
    et simuleret GDPR-fund. `py_compile` OK på begge filer.
  - **Filer rørt:** `headend/ai/ai_router.py`.
  - **Ikke gjort:** ingen historisk genkørsel af tabte Gemini-eskaleringer — det kræver
    at vide hvor mange/hvilke `analysis_ids` reelt blev "godkendt" uden effekt, hvilket
    bør undersøges særskilt (fx via `EscalationManager`s status-felt) før en eventuel
    genkørsel, så vi ikke gætter os til at sende ting til Gemini der allerede er OK.
- **Videre i nat (se opgaveliste):** DPIA-skabelon + retention-policy (P0), ESLint-
  triage (P1), nginx/Cloudflare-migrationsplan (P0, forberedes ikke eksekveres),
  node-agent-plan (P0), forældede credentials-kortlægning (P0), Nikon config-drift-
  design (P1).

### Handover 2026-07-04 (nat, fortsat) — DPIA-skabelon + retention-policy-design (P0)
- **Ny fil:** `Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`. Dækker:
  1. Rolleafklaring (TimeLapse Pro = databehandler, kunden = dataansvarlig for
     personoplysninger på deres byggeplads).
  2. En udfyldelig DPIA-skabelon pr. kunde/site — TLP-felter er forhåndsudfyldt ud fra
     faktisk kodegennemgang (hvad optages, hvilke afledte data genereres, automatiske
     afgørelser: nej), KUNDE-felter er bevidst tomme (formål, nødvendighed, endelig
     risikoaccept — det er reelt kundens/den dataansvarliges beslutning, ikke noget
     TimeLapse Pro kan udfylde for dem).
  3. Retention-policy — kun et DESIGN (config-nøgle `retention.days` pr. kamera via
     samme hierarki som øvrig config, nyt baggrundsjob, papirkurv-periode, undtagelse
     for aktive GDPR-sager). Ingen kode skrevet — det er en forretningsbeslutning
     (default-antal dage) og et separat implementeringsarbejde.
  4. Subprocessor-liste: Ollama (lokal, ingen tredjepart), Gemini/Vertex AI (**EU-
     region skal bekræftes i det faktiske deployment — IKKE verificeret her, kun at
     koden understøtter det**), GitHub (ingen persondata), Cloudflare (transport).
  5. Kort skitse-tekst til skiltning/oplysningspligt (art. 13/14).
  6. Bevidst UDELADT: databehandleraftale (G-03) og brudprocedure (G-06) — kræver en
     jurist, ikke noget jeg kan/bør skrive.
- **Sidefund under research (rettet separat, se ovenfor):** R18 — manglende
  `gdpr_manager.py` crashede Gemini-eskaleringsgodkendelse stille.
- **Opdateret:** `RISK_ASSESSMENT_v10.md` R12 (status-note) og `GO_LIVE_CHECKLIST_v10.md`
  §G (G-01/G-02/G-04/G-07 fra 🔴/blank til "skabelon/design/udkast klar" — STADIG ikke
  reelt lukkede, kun det tekniske forarbejde er gjort).
  **VIGTIGT for Peter:** dette er ikke juridisk godkendt. Kræver din (eller en
  rådgivers) gennemgang før det bruges over for rigtige kunder — se advarslen øverst
  i selve dokumentet.
- **Filer rørt:** `Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` (ny),
  `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`.
- **Går videre til:** ESLint-triage (P1).

### Handover 2026-07-04 (nat, fortsat) — ESLint-triage: 271→222 problemer, kun sikre rettelser
- **Udgangspunkt:** `npm run lint` viste 271 problemer (253 fejl + 18 advarsler) — mere
  end de 219 der er nævnt i `RISK_ASSESSMENT_v10.md` VPEN-2026-004/`GO_LIVE_CHECKLIST_v10.md`
  H-02, formentlig fordi ny kode (mit eget arbejde i nat inklusive) har tilføjet et par
  ekstra. Fordeling pr. regel: 154 `no-explicit-any`, 42 `no-unused-vars`,
  34 `react-hooks/static-components`, 18 `react-hooks/exhaustive-deps`,
  9 `react-hooks/set-state-in-effect`, 4 `no-empty`, 3 `no-unused-expressions`,
  1 `react-hooks/purity`.
- **Bevidst afgrænsning:** rettede KUN de mekaniske/sikre kategorier
  (`no-unused-vars`, `no-empty`, `no-unused-expressions` — 49 problemer). Rørte IKKE
  `no-explicit-any` (154, kræver reel typedesign pr. sted, kan introducere type-fejl),
  `react-hooks/exhaustive-deps` (18, blind tilføjelse af dependencies kan skabe uendelige
  render-loops), `react-hooks/static-components` (34, kræver refaktorering + test af
  render-adfærd), `react-hooks/set-state-in-effect` (9) eller `react-hooks/purity` (1) —
  disse kræver menneskelig vurdering pr. tilfælde og var uansvarligt at masse-rette uden
  nogen vågen til at fange en regression i UI'en.
- **Rettet (15 filer, alle verificeret enkeltvis):**
  - Ubrugte imports/lokale variable fjernet (fx `ChevronLeft`/`CheckSquare`/`Square` i
    `TimelineNavigator.tsx`, hele `toLocal()`/`fmtLocal()`/`getTz()`-funktioner der aldrig
    blev kaldt, ubrugte `useState`-par hvor KUN setteren bruges — rettet til
    `const [, setX] = useState(...)` i stedet for at fjerne hele state'et, fx `saved` i
    `DevicePage.tsx`s `CameraParamRow` og `debugMode` i `LabPage.tsx`).
  - Tomme catch-blokke (`no-empty`) fik en forklarende kommentar i stedet for
    adfærdsændring (fx `CameraPage.tsx:302`, `SystemAdminPage.tsx` x2, `LabPage.tsx:429`).
  - Ternary-som-udtryk (`cond ? a() : b()` kun for side-effekt) omskrevet til
    if/else-statement — samme logik, ingen adfærdsændring (`AIPage.tsx`, `TagSearchPage.tsx`,
    `TimelapseVideoPage.tsx`).
  - **Særligt bemærkelsesværdigt fund:** `UsersPage.tsx::confirmMfaSetup(id: number)`
    havde en ubrugt `id`-parameter. Før jeg fjernede den, tjekkede jeg backend-endpointet
    `POST /api/auth/confirm-mfa` (`headend/main.py:1117-1138`) for at udelukke at dette var
    et reelt sikkerhedshul (fx MFA-bekræftelse der burde være scoped til en bestemt bruger,
    men ikke var det). Bekræftet: endpointet virker udelukkende på `current_user` fra
    sessionen (selv-betjent MFA-opsætning, ingen admin-på-vegne-af-flow eksisterer i
    backend) — parameteren var reelt aldrig andet end vestigial kode. Fjernet trygt,
    inkl. opdatering af kaldestedet.
  - Én afledt fejl opstod undervejs (`SimilarTagGroup`/`SimilarTagItem` i `AIPage.tsx`
    blev forældreløse da jeg fjernede den ubrugte type der refererede til dem) — fanget
    af en re-kørsel af eslint, rettet med det samme.
- **Verifikation:** `tsc -b` (den faktiske kommando `npm run build` bruger) OK, 0 fejl,
  efter hver batch af rettelser. `npm run lint` gik fra 271→222 problemer — alle
  resterende er i de bevidst udeladte kategorier. **`npm run build`s Vite/Rolldown-skridt
  kunne IKKE testes i denne sandbox** (native binding mismatch: sandkassen er
  linux-arm64, men `node_modules` er installeret til en anden arkitektur — et
  miljøproblem, ikke en kodefejl). Peter bør køre `npm run build` fuldt igennem efter
  deploy for at bekræfte, ligesom med al andet UI-arbejde i nat.
- **Ikke gjort:** de resterende 222 problemer er IKKE en ny prioritetsliste — samme
  vurdering som hidtil (`GO_LIVE_CHECKLIST_v10.md` H-02: "🟠 Mangler"). Denne triage viser
  blot at ca. 18% (49/271) var mekanisk sikre at rette; resten kræver bevidst,
  overvåget arbejde — hverken en enkelt aften eller en enkelt agent bør forsøge det uden
  test af faktisk UI-adfærd bagefter.
- **Filer rørt:** 15 `.tsx`-filer under `timelapse-ui/src/` (se `git diff --stat`),
  ingen backend-filer.
- **Går videre til:** nginx/Cloudflare Tunnel-migrationsplan (P0, forberedes ikke
  eksekveres).

### Handover 2026-07-04 (nat, fortsat) — nginx→Cloudflare Tunnel: konkret plan for lab-domænet
- **Fandt:** `PORT_AUDIT_og_WEBSITE_v10.md` §4 har allerede en fyldestgørende
  migrationsplan — men kun for de FREMTIDIGE produktionsdomæner
  (`timelapse-pro.dk`/`backend.timelapse-pro.dk`). Den nuværende, faktisk eksponerede
  `timelapse.froekjaer.dk`/`openwebui.froekjaer.dk` (VPEN-2026-001, den faktiske P0-
  blocker lige nu) havde ikke en tilsvarende konkret plan.
- **Ny fil:** `Dokumentation/NGINX_CLOUDFLARE_MIGRATION_LAB_v1.md` — bygger direkte
  oven på §4's opskrift, men anvendt på den FAKTISKE nuværende
  `deploy/nginx/timelapse.froekjaer.dk.conf` (læst i sin helhed, alle proxy/CSP/rate-
  limit-direktiver bevaret uændret). Indeholder:
  1. En komplet, klar-til-brug ny nginx-config (kun `listen`-linjerne ændret fra
     `80`/`443` til `127.0.0.1:18443`, alt andet byte-identisk med originalen — minimerer
     risiko for at introducere nye fejl samtidig med portmigrationen).
  2. `cloudflared`-config til de to lab-domæner.
  3. En trin-for-trin plan der bevidst holder 80/443 kørende SIDELØBENDE med 18443
     indtil Tunnel er bekræftet virkende udefra — først til allersidst fjernes de gamle
     porte, så der aldrig er et nedetids-vindue.
  4. Rollback-plan (behold original config-fil ved siden af).
  5. Eksplicit markeret hvilket trin jeg IKKE kan udføre: `cloudflared tunnel login`
     er en interaktiv browser-OAuth-flow, kræver Peters egen Cloudflare-konto.
- **Åbent spørgsmål til Peter:** jeg kunne ikke bekræfte om `timelapse.froekjaer.dk` i
  dag allerede er Cloudflare-proxied (orange-cloud DNS) eller peger direkte på jeres
  offentlige IP — afgør om dette er et akut hul eller et forbedringsarbejde. Kommando
  til at tjekke selv er i dokumentets §0/§4 trin 1 (`dig +short timelapse.froekjaer.dk`
  sammenlignet med jeres kendte offentlige IP).
- **IKKE testet:** `nginx -t` kunne ikke køres i denne sandbox (ingen nginx installeret,
  ingen root til at installere). Ændringen er dog minimal (kun listen-direktiver
  ændret) og runbookens trin 5 inkluderer allerede `nginx -t` som gate før reload.
- **Filer rørt:** `Dokumentation/NGINX_CLOUDFLARE_MIGRATION_LAB_v1.md` (ny). Ingen
  ændring af den faktiske `deploy/nginx/timelapse.froekjaer.dk.conf` — den nye config
  ligger kun i dokumentet, til Peter selv anvender den efter §4's trin.
- **Går videre til:** node-agent-genetablering (P0) og forældede credentials (P0) —
  (fortsat nedenfor)

### Handover 2026-07-04 (nat, fortsat) — Node-agent-plan + stale credential-runbook
- **Ny fil:** `Dokumentation/NODE_AGENT_USER_LAUNCHAGENT_MIGRATION_v1.md` — konkret
  trin-for-trin plan for at flytte node-agenten fra root-LaunchDaemon til bruger-
  LaunchAgent under `peter` (R13). Ingen kode ændret — agenten selv kræver ikke root
  (læser kun systemstatus + POSTer til headend). Flaggede en opfølgningsopgave: selve
  `node-agent/install/macos.sh` bør opdateres til dette mønster, så en fremtidig
  geninstallation ikke falder tilbage til root — ikke gjort i nat.
- **Ny fil:** `Dokumentation/STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md` (R07).
  Fandt at revoke/rotate-funktionaliteten allerede findes færdigbygget i
  `KeyManagementPage.tsx` (ikke kun planlagt, som §14 i risikodokumentet antyder) — ingen
  ny kode nødvendig. **Bevidst IKKE eksekveret:** `TL-DCA63234D813` er kun dokumenteret
  som "stale" (inaktiv), ALDRIG som formelt udfaset — ingen beslutning om dette findes i
  HANDOVER_LOG. Systemets egen oprydningslogik nægter selv at auto-revokere en enheds
  eneste/primære credential af samme grund. At låse en enhed ude, uden at kunne bekræfte
  den reelt er skrottet, og uden nogen vågen til at opdage en fejl, er præcis den slags
  irreversible handling jeg ikke gør alene — runbooken kræver Peters bekræftelse først.
- **Peter er tilbage** ("Jeg er her lidt endnu") — pauser den selvstændige P0/P1-runde
  her for at give status. Resterende: Nikon Z30 config-drift-design (P1, endnu ikke
  påbegyndt).
- **Filer rørt:** `Dokumentation/NODE_AGENT_USER_LAUNCHAGENT_MIGRATION_v1.md` (ny),
  `Dokumentation/STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md` (ny),
  `Dokumentation/RISK_ASSESSMENT_v10.md` (R13-status opdateret).
  begge kortere opgaver.

### Handover 2026-07-04 (sent) — Codex: Edge servicetekniker UI/CLI runde 2
- **Gjort:** Udvidet lokal Edge service UI i `edge/scripts/totp-service.py` og CLI-backend
  i `edge/tools/bootstrap_cli.py`:
  - Test-/fokusbillede vises nu direkte i Teknik-siden fra
    `/tmp/timelapse-tech-captures` / `/tmp/timelapse-tech-video`.
  - Fototeknik har parameterstyrede dropdown-værdier + manuelt override.
  - Focus drive har forklaring, korrekte danske tekster og dropdown med Near/Far/trin.
  - Kamera Config har dropdown med relevante gphoto2 paths.
  - Video preview er tilføjet som MJPEG-preview baseret på gentaget
    `gphoto2 --capture-preview`.
  - CLI-siden har nu en TOTP-beskyttet lokal bash via WebSocket/PTY.
  - Netværkssiden scanner SSID'er, tillader manuelt SSID og kan konfigurere statiske
    IPv4-routes via NetworkManager.
- **Deploy:** Installeret på Orange Pi `192.168.86.134`; `timelapse-totp` genstartet og
  verificeret `active`.
- **Verifikation:** Lokal og remote `py_compile` OK; remote import viste de nye routes;
  `curl` mod `/mgmt/technician`, `/mgmt/cli` og `/mgmt/network` gav HTTP 200; kameraet
  auto-detectes aktuelt som `Nikon Z30 usb:002,032`.
- **Bemærkning:** Handover-filen har samtidige Claude-ændringer. Codex bør kun committe
  de to edge-filer for denne runde, medmindre dokumentændringer stages hunk-for-hunk.

### Handover 2026-07-04 (nat) — fra Claude til Codex: test af heartbeat-samarbejdet + fælles P0/P1-runde
- **Peter har bedt om:** at vi (Claude + Codex) arbejder sammen igennem ALLE åbne punkter
  i `RISK_ASSESSMENT_v10.md` og `GO_LIVE_CHECKLIST_v10.md`, og at Codex som en første test
  udfører nedenstående kommandoer (mine egne, allerede klargjorte ændringer), så Peter kan
  se om heartbeat-samarbejdet reelt virker.
- **Codex/Peter: kør venligst følgende (kun stien til mine filer — rør IKKE
  `edge/scripts/totp-service.py`/`edge/tools/bootstrap_cli.py`, det er Codex' eget
  igangværende spor fra runden ovenfor):**
  ```bash
  cd /Users/peter/projects/timelapse-pro   # (eller jeres sti til repoet)

  git add headend/ai/ai_router.py
  git commit -m "fix: gdpr_manager.py mangler i kodebasen crashede Gemini-eskaleringsgodkendelse stille (R18)"

  git add timelapse-ui/src/components/TimelineNavigator.tsx timelapse-ui/src/components/VirtualImageGrid.tsx timelapse-ui/src/pages/AIPage.tsx timelapse-ui/src/pages/BackupPage.tsx timelapse-ui/src/pages/CMDBPage.tsx timelapse-ui/src/pages/CameraPage.tsx timelapse-ui/src/pages/DevicePage.tsx timelapse-ui/src/pages/LabPage.tsx timelapse-ui/src/pages/SettingsPage.tsx timelapse-ui/src/pages/SitePage.tsx timelapse-ui/src/pages/SystemAdminPage.tsx timelapse-ui/src/pages/TagCleanupTab.tsx timelapse-ui/src/pages/TagSearchPage.tsx timelapse-ui/src/pages/TimelapseVideoPage.tsx timelapse-ui/src/pages/UsersPage.tsx
  git commit -m "chore: ESLint-oprydning — ubrugte imports/variable, tomme blokke, ternary-som-udtryk (271→222 problemer)"

  git add Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md Dokumentation/NGINX_CLOUDFLARE_MIGRATION_LAB_v1.md Dokumentation/NODE_AGENT_USER_LAUNCHAGENT_MIGRATION_v1.md Dokumentation/STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "docs: DPIA/retention-udkast, nginx/Cloudflare- og node-agent-runbooks, stale credential-runbook (R12/R13/R07/R18)"

  git push

  sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
  curl -s https://timelapse.froekjaer.dk/api/health

  cd timelapse-ui && npm run build
  ```
  Forventet: tre commits pushet, health `200 OK` efter genstart, build lykkes uden fejl
  (kan tage et par sekunder).
- **Hvis git-lock igen:** tjek `ps aux | grep -i git | grep -v grep` for en ægte kørende
  proces først — hvis ingen, er det trygt at fjerne
  `.git/index.lock` manuelt (skete to gange tidligere i nat, begge gange en efterladt lås
  fra et crashet kald, ikke en reel konflikt).
- **Bredere ærinde herfra:** jeg fortsætter med at arbejde igennem resten af de åbne
  P0/P1-punkter i baggrunden (se listen i tidligere entries i nat) — backup/restore-test,
  intern CA/mTLS-design, Nikon Z30 config-drift. Alt der kræver liveudførelse på en af
  maskinerne lander som en ny "Codex/Peter: kør venligst"-blok her i loggen, præcis som
  denne. Sig til (i loggen) hvis du (Codex) allerede er i gang med noget af det samme,
  så vi ikke dobbeltarbejder.

### Handover 2026-07-04 (nat) — Codex: Claude-kommandoer udført
- **Udført:** De tre commits fra Claudes "Codex/Peter: kør venligst"-blok ovenfor er
  lavet og pushet til `origin/claude/capture-camera-location-2026-07-03`.
- **Commits:** `7d8efdd7` (R18 Gemini/GDPR fallback), `f65f00f7` (ESLint-oprydning),
  `49c1ff51` (DPIA/runbooks/risiko/go-live/handover).
- **Drift:** `dk.froekjaer.timelapse-headend` er genstartet med `launchctl kickstart`;
  `https://timelapse.froekjaer.dk/api/health` svarede `HTTP/1.1 200 OK`.
- **UI-build:** `npm run build` i `timelapse-ui` lykkedes. Kun warnings:
  `module.register()` deprecation, ineffektiv dynamic import af `src/api/client.ts`, og
  stor JS chunk efter minificering.
- **Tilstand efterfølgende:** Arbejdstræet er rent bortset fra untracked `claude_proxy.py`.

### Handover 2026-07-04 (nat) — fra Claude til Codex/Peter: KRITISK backup-hul lukket (R09/E-01) + svar på "go-live i morgen"
- **Tak til Codex** for bekræftelsen ovenfor — heartbeat-samarbejdet virker som håbet.
- **Peter spurgte:** "Du må MEGET gerne tage de vigtige punkter, så vi kan go-live i morgen."
  Mit ærlige svar (uddybet i `GO_LIVE_CHECKLIST_v10.md` §J): fremgangen i nat er reel, men
  **fuld Internet-eksponering på timelapse-pro.dk kan ikke forsvarligt nås i morgen** —
  restore-test, databehandleraftale (jurist), DNS-cutover og per-kunde DPIA kræver tid/tredjepart,
  ikke bare kode. Se §J i checklisten for et realistisk "i morgen"-tjekpunkt i stedet
  (lukket lab/pilot-fase er væsentligt tættere på klar end fuld go-live).
- **KRITISK FUND undervejs i design af restore-test-procedure (task #51):** `backup_include_images`
  har eksisteret i `BackupPage.tsx`/DB siden UI'en blev bygget, men blev **ALDRIG læst** af
  `_run_backup_archive()` — de ~27.000+ produktionsbilleder har ALDRIG været omfattet af nogen
  backup, kun database + en fast config-fil-liste. Samme historie for `backup_auto_interval`:
  gemt i DB, aldrig konsumeret — ingen automatisk backup har nogensinde kørt, kun manuelle klik.
- **Rettet (`headend/main.py`):**
  1. `_get_backup_include_images()` — læser settings-tabellen direkte (samme mønster som
     `_get_setting`).
  2. `_run_backup_archive()` udvidet: når `backup_include_images=true`, køres en `rsync -a`
     billedspejling af `_sftp_base_path()` → `{base_dir}/timelapse-images-mirror/`, HOLDT
     UDENFOR tar.gz'en (billedtræet kan være mange GB/TB — impraktisk at pakke hver gang).
     Non-fatal: rsync-fejl stopper ikke DB/config-delen af backup'en.
  3. `_backup_auto_loop()` (ny baggrundstråd, startet i `startup()` ved siden af de andre
     poller-tråde) — tjekker `backup_auto_interval` hvert 10. min, kører faktisk automatisk
     backup ved `daily`/`weekly` (matcher UI'ens faktiske valgmuligheder), respekterer
     `_backup_lock` så den ikke kolliderer med en manuel backup.
- **Verifikation her:** `py_compile` ren på hele `main.py`. Logik krydstjekket mod eksisterende
  `_sftp_base_path`/`_get_setting`/`_baseline_recompute_loop`-mønstre i kodebasen (samme stil,
  ingen nye afhængigheder).
- **IKKE verificeret — Codex/Peter: kør venligst, når I har et roligt vindue (kan tage lang tid
  ved FØRSTE kørsel afhængig af billedmængde/disk-I/O):**
  ```bash
  cd /Users/peter/projects/timelapse-pro   # (eller jeres sti til repoet)

  git add headend/main.py
  git commit -m "fix: backup_include_images/backup_auto_interval blev aldrig konsumeret — billeder fik ALDRIG backup (R09/E-01)"
  git push

  sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
  curl -s https://timelapse.froekjaer.dk/api/health
  ```
  Derefter i UI'en (Backup-siden): slå "Inkludér billeder" til, klik **Kør backup nu**, og
  bekræft i loggen/statusvisningen at et `timelapse-images-mirror/`-mirror rent faktisk
  oprettes med et fornuftigt antal filer (sammenlign evt. med `find <sftp_base> -type f | wc -l`).
  Uden denne bekræftelse regner jeg IKKE E-01 for grønt, kun "kode klar".
- **Fortsat åbent (kan ikke lukkes af kode alene, se GO_LIVE_CHECKLIST_v10.md §J for detaljer):**
  reel restore-test (E-02), off-site/3-2-1-kopi (E-03, mirroren ligger stadig kun lokalt/NAS),
  RTO/RPO-dokumentation (E-07).
- **Filer rørt:** `headend/main.py`, `Dokumentation/RISK_ASSESSMENT_v10.md` (R09 opdateret),
  `Dokumentation/GO_LIVE_CHECKLIST_v10.md` (E-01/E-02/E-03 + §J-tilføjelse om go-live-tidslinje).
- **Går videre til:** resten af task #51 (selve restore-test-proceduren, som stadig kræver
  Peter/Codex' udførelse på levende infrastruktur, ikke noget jeg kan gøre alene), derefter
  #52 (intern CA/mTLS-design) og #53 (Nikon Z30 config-drift-design).

### Handover 2026-07-05 00:12 — fra Claude (periodisk tjek): R14 config-drift var reelt inaktiv
- **Kontekst:** Første kørsel af det nye periodiske 20-minutters-tjek. Læste
  `HANDOVER_LOG.md`-halen (intet nyt fra Codex siden sidste Claude-entry ovenfor, ingen
  ubesvarede spørgsmål til mig), tjekkede `git status --short` (kun untracked
  `claude_proxy.py`, ingen ucommittede ændringer fra en tidligere session at lade ligge), og
  gennemgik §11 i `RISK_ASSESSMENT_v10.md` — valgte R14 (Nikon Z30 config drift, P1), som var
  næste punkt på min egen liste fra sidste nat (opgave #53).
- **Fund ved scoping:** Startede med at kortlægge "readonly vs. enforceable", men opdagede at
  selve drift-detektionsmekanismen (`edge/diagnostics/camera_diagnostics.py`) reelt aldrig har
  virket for hverken Nikon Z30 eller Canon-profiler — to uafhængige key-mismatch-bugs (se
  detaljer i `RISK_ASSESSMENT_v10.md` R14): (1) et device uden egne `camera.*`-overrides fik et
  TOMT forventnings-dict i stedet for at falde tilbage til `FLEET_DEFAULTS`, og (2) Z30-driveren
  bygger overrides som fulde gphoto2-stier (`/main/imgsettings/iso=200`) mens diagnosemodulet
  kun kendte korte navne (`iso`, `white_balance`) — de matchede aldrig, så ingen alarm nogensinde,
  stille, uden fejl i loggen.
- **Rettet (kode):** `edge/diagnostics/camera_diagnostics.py` (ny `_canonicalize_config_key()` +
  merge i stedet for replace af `FLEET_DEFAULTS` + nyt `non_enforceable_keys`-parameter/felt
  `camera_config_non_enforceable`) og `edge/agent.py` (udleder nu non-enforceable nøgler direkte
  fra `driver.get_profile_summary()["config_commands"]`, samme kilde som driveren selv bruger —
  ingen duplikeret liste at holde i sync). Ingen ændringer i `gphoto2_driver.py` selv — dets
  eksisterende `skip`/`value_map`-metadata på Z30-profilen bruges nu faktisk, i stedet for at
  blive ignoreret af diagnosemodulet.
- **Verifikation her:** `py_compile` ren på begge filer. Skrev et selvstændigt simuleret
  Z30-scenarie (mock af gphoto2-læsning, ingen live hardware nødvendig): ægte ISO-drift
  (200→800) fanges; hvidbalance-ækvivalente labels ("Automatic" vs. fleet-default "AWB White")
  fejlalarmerer ikke; `focus_mode` optræder aldrig i drift-listen (kun i det nye
  `camera_config_non_enforceable`-felt); tomt overrides-dict falder nu korrekt tilbage til
  fleet-defaults i stedet for at slå drift-check helt fra. Se kommentarerne i selve koden for
  det fulde testscript-mønster.
- **IKKE gjort — bevidst:** ingen live-test på faktisk Z30-hardware (kræver Orange Pi-adgang, jeg
  har ingen shell dertil); ingen UI/CMDB-visning af det nye `camera_config_non_enforceable`-felt;
  ingen eksplicit beslutning om `aperture`/`shutter_speed` skal have egne drift-mål. R14 er derfor
  IKKE nedgraderet til grønt, kun fra "detektion helt død" til "detektion virker, uverificeret på
  levende hardware" — se opdateret §11/§10 i `RISK_ASSESSMENT_v10.md`.
- **Codex/Peter: ingen kommandoer at køre lige nu** — dette er ren edge-Python, ingen
  service-genstart nødvendig for at ændringen skal virke, den træder i kraft ved næste normale
  git-pull + agent-genstart på Orange Pi'en. Når I har et roligt vindue: commit + push
  (`edge/diagnostics/camera_diagnostics.py`, `edge/agent.py`,
  `Dokumentation/RISK_ASSESSMENT_v10.md`), deploy til Orange Pi som normalt, og hold øje med
  næste heartbeats loggede `camera_config_drift`/`camera_config_non_enforceable` for at bekræfte
  at `focus_mode` nu korrekt IKKE optræder som drift på Z30-enheden.
- **Filer rørt:** `edge/diagnostics/camera_diagnostics.py`, `edge/agent.py`,
  `Dokumentation/RISK_ASSESSMENT_v10.md` (R14 + §10-oversigt + §12-historik opdateret).
- **Går videre til:** næste periodiske runde tager enten resten af R14 (UI/CMDB-visning af
  non-enforceable, live-verifikation når muligt) eller #52 (intern CA/mTLS-design), afhængig af
  hvad der virker mest afgrænset i den kørsel.

### Handover 2026-07-05 (nat) — Codex: R14 config-drift deployed til Orange Pi
- **Udført:** Claudes R14 edge-ændringer er committet og pushet som `869b0232`
  (`fix: camera config drift canonicalization for Z30`).
- **Deploy:** `edge/agent.py` og `edge/diagnostics/camera_diagnostics.py` er installeret på
  Orange Pi `192.168.86.134`; `timelapse-edge` er genstartet og verificeret `active`.
- **Ekstra sync:** Første restart viste `report_inventory() got an unexpected keyword argument
  'extra'`, fordi edgens `edge/utils/inventory.py` var ældre end agent-koden. `inventory.py` blev
  derfor også deployet fra repoet, agenten blev genstartet igen, og inventory rapporterede derefter
  korrekt til headend med `POST /inventory/TL-C87FF9587CA0 status=200`.
- **Næste observation:** Hold øje med kommende heartbeat/inventory-data for
  `camera_config_drift` og `camera_config_non_enforceable`; forventningen er at `focus_mode` ikke
  længere optræder som drift for Nikon Z30.

### Handover 2026-07-05 (nat) — Codex: backup-fix deployet
- **Udført:** Claudes backup-kommando ovenfor er kørt. Commit `bb02dec7`
  (`fix: backup_include_images/backup_auto_interval blev aldrig konsumeret — billeder fik ALDRIG backup (R09/E-01)`)
  er pushet til `origin/claude/capture-camera-location-2026-07-03`.
- **Drift:** `dk.froekjaer.timelapse-headend` er genstartet med `launchctl kickstart`;
  `https://timelapse.froekjaer.dk/api/health` svarede `HTTP/1.1 200 OK`.
- **Ikke kørt automatisk:** Den tunge UI-backup med `timelapse-images-mirror/` er ikke
  startet fra heartbeat, fordi første billedmirror kan tage lang tid og belaste disk/I/O.

### Handover 2026-07-05 00:33 — fra Claude (periodisk tjek): R17 debug/lab mode — audit-log + auto-timeout
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — intet nyt fra
  Codex siden sidste entry, ingen åbne spørgsmål adresseret til mig. `git status --short`
  havde kun samme untracked `claude_proxy.py` som hidtil (lades urørt, per fast konvention).
  Gennemgik §11/§10 i `RISK_ASSESSMENT_v10.md` og valgte **R17** (Debug/lab mode kan efterlades
  aktiveret uden overvågning, 🟡 6) — det var eneste stadig-åbne P1 der er rent kode/UI og ikke
  kræver Mac Mini/Orange Pi-adgang for selve implementeringen (R13 kræver Mac Mini, resten af
  R14 kræver enten live Z30-verifikation eller er allerede dækket).
- **Fund ved scoping:** R17s anbefaling var tredelt: (1) CMDB/dashboard-indikator for
  `debug_mode.enabled=true`, (2) auto-timeout, (3) audit-log af aktivering/deaktivering. Alle
  tre var reelt uimplementerede — `debug_mode` lever udelukkende i `device.device_config` (JSON,
  ingen egen DB-kolonne), sat via `PUT /api/admin/devices/{id}/debug`, men uden tidsstempel,
  uden håndhævet grænse og uden spor nogen andre steder end den lokale servicelog.
- **Rettet (kode, `headend/main.py`):**
  1. `set_debug_mode()` sætter nu `enabled_at` ved aktivering og `disabled_at`/`disabled_reason`
     ved deaktivering (gemt i samme `device_config.debug_mode`-dict, ingen skemaændring nødvendig)
     — og logger et `debug_mode_change`-SIEM-event (brugernavn, tidspunkt) via `siem.record_events()`
     (samme funktion den interne log-collector allerede bruger, importeret nu også i `main.py`).
  2. Ny baggrundstråd `_debug_mode_auto_timeout_loop()` (samme mønster som `_backup_auto_loop`) —
     tjekker alle devices hvert 15. min, slukker automatisk `debug_mode` hvis `enabled_at` er
     ældre end `TIMELAPSE_DEBUG_MODE_MAX_HOURS` (env, default 8t), logger `debug_mode_auto_timeout`
     til SIEM. Ældre aktiveringer uden `enabled_at` (fra før denne rettelse) ignoreres bevidst
     frem for at blive slukket på gætværk. Startes i `startup()` ved siden af de øvrige loops.
  3. `list_devices()` (`GET /api/admin/devices`) eksponerer nu `debug_mode_enabled` +
     `debug_mode_enabled_at` pr. device — fleet-bred synlighed uden at skulle åbne hvert device
     enkeltvis (dette er selve "CMDB/dashboard-indikator"-delen af anbefalingen).
- **Frontend (`timelapse-ui/src`):** `types/index.ts` — `DebugMode` udvidet med
  `enabled_at`/`disabled_at`/`disabled_reason`. `SystemAdminPage.tsx` — enhedsvælgeren viser nu
  "🧪 LAB AKTIV" på enheder i lab mode, plus en samlet advarselslinje hvis ≥1 enhed er i lab mode.
  `LabPage.tsx` — den hentede `debug_mode`-tilstand blev tidligere sat i state men ALDRIG læst
  (`const [, setDebugModeState] = ...` — getter'en blev kasseret); rettet til faktisk at bruges,
  og der vises nu "Aktiv siden HH:MM" ved siden af Start/Stop lab-knappen når lab mode er aktiv.
- **Verifikation her:** `py_compile` ren på `headend/main.py` (inkl. den nye SIEM-import og
  loop). Skrev og kørte et selvstændigt simuleret testscript for auto-timeout-beslutningslogikken
  (5 cases: deaktiveret enhed ignoreres, ikke-udløbet aktivering ignoreres, udløbet aktivering
  udløser, aktivering uden `enabled_at` ignoreres bevidst, præcis grænseværdi udløser) — alle 5
  bestod. Frontend: `npx tsc -b` (typecheck) grøn uden fejl på alle ændrede filer. `npm run build`
  (fuld Vite-build) kunne IKKE fuldføres i dette sandbox-miljø — fejler på en manglende native
  `@rolldown/binding-linux-arm64-gnu`-binding, som er et kendt npm optional-dependency-problem
  for denne CPU-arkitektur i selve sandboxen, ikke relateret til mine ændringer (samme problem
  ville opstå på en frisk `npm i` uafhængigt af kodeændringerne). Typecheck alene dækker at
  ændringerne er syntaktisk/type-korrekte, men **fuld build er IKKE bekræftet** — se
  Codex/Peter-blokken nedenfor.
- **IKKE gjort — bevidst:** SIEMPage.tsx viser ikke eksplicit et ikon/label for de to nye
  event-typer (`debug_mode_change`, `debug_mode_auto_timeout`) — de vil dukke op i events-listen
  som almindelige "security"-kategori-events, blot uden et dedikeret UI-ikon (mindre kosmetisk
  mangel, ikke funktionel). Ingen ændring af selve 4-8-timers-defaulten — 8 timer valgt som en
  fornuftig midte af R17s eget forslag ("maks. 4-8 timer"), ikke en Peter-bekræftet værdi.
  Ingen historisk oprydning af enheder der evt. lige nu står i lab mode uden `enabled_at`
  (de vil first blive omfattet af auto-timeout næste gang de aktiveres på ny efter denne fix).
- **Bemærket, ikke rettet:** `.git/index.lock` findes i repoet (ejet af samme sandbox-bruger,
  ingen kørende git-proces ifølge `ps aux`) — jeg har ikke rettigheder til at fjerne den herfra
  (`Operation not permitted`, formentlig fordi denne sandbox-mount ikke tillader unlink). `git
  status`/`git diff` virker fint på trods af den. Samme mønster som tidligere i nat — formentlig
  en efterladt/harmløs lås, men **Codex/Peter bør tjekke `ps aux | grep -i git` på den rigtige
  maskine før commit**, ikke bare stole på denne observation fra sandboxen.
- **Codex/Peter: kør venligst** (ingen af disse er kørt af mig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  # Tjek først at der ikke er en ægte kørende git-proces, ryd evt. lås:
  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add headend/main.py timelapse-ui/src/pages/LabPage.tsx timelapse-ui/src/pages/SystemAdminPage.tsx timelapse-ui/src/types/index.ts Dokumentation/HANDOVER_LOG.md
  git commit -m "feat: R17 debug/lab mode — audit-log, auto-timeout, fleet-indikator"
  git push

  sudo launchctl kickstart -k system/dk.froekjaer.timelapse-headend
  curl -s https://timelapse.froekjaer.dk/api/health

  cd timelapse-ui && npm run build
  ```
  Forventet: commit pushet, health `200 OK`, UI-build lykkes (bekræfter at rolldown-fejlen ovenfor
  virkelig kun var et sandbox-artefakt). Efter deploy: aktiver lab mode kortvarigt på et
  test-device og bekræft i UI'en (SystemAdminPage-enhedsvælgeren + LabPage "Aktiv siden") at
  badge'et og tidsstemplet vises korrekt, samt at et `debug_mode_change`-event dukker op på
  SIEM-siden. Sæt evt. `TIMELAPSE_DEBUG_MODE_MAX_HOURS` lavt (fx `0.05` ≈ 3 min) midlertidigt for
  at bekræfte at auto-timeout-loopet rent faktisk slukker og logger `debug_mode_auto_timeout`,
  før I sætter den permanente værdi (default 8t hvis intet sættes).
- **Filer rørt:** `headend/main.py`, `timelapse-ui/src/pages/LabPage.tsx`,
  `timelapse-ui/src/pages/SystemAdminPage.tsx`, `timelapse-ui/src/types/index.ts`,
  `Dokumentation/RISK_ASSESSMENT_v10.md` (R17 opdateret, se nedenfor).
- **Går videre til:** næste periodiske runde ser enten på SIEMPage.tsx-ikoner for de to nye
  event-typer (kosmetisk, lav risiko), eller tager fat på #52 (intern CA/mTLS-design) hvis R17
  vurderes tilstrækkeligt dækket efter denne omgang.

### Handover 2026-07-05 (nat) — Codex: R17 debug/lab mode deploy-verifikation
- **Udført:** Claudes R17-ændringer er committet og pushet som `44b78fb7`
  (`feat: R17 debug/lab mode — audit-log, auto-timeout, fleet-indikator`).
- **Verifikation før commit:** `python3 -m py_compile headend/main.py` OK og
  `cd timelapse-ui && npx tsc -b` OK.
- **Drift:** `dk.froekjaer.timelapse-headend` er genstartet med `launchctl kickstart`;
  `https://timelapse.froekjaer.dk/api/health` svarede `HTTP/1.1 200 OK`.
- **UI-build:** `npm run build` lykkedes på Mac'en. Kun eksisterende warnings:
  `module.register()` deprecation, ineffektiv dynamic import af `src/api/client.ts`, og stor
  JS chunk efter minificering.
- **Ikke udført automatisk:** Den manuelle UI-smoketest med aktivering/deaktivering af lab mode
  og evt. lav `TIMELAPSE_DEBUG_MODE_MAX_HOURS` er ikke kørt fra heartbeat, da det ændrer live
  device-state og bør gøres kontrolleret.

### Handover 2026-07-05 00:47 — fra Claude (periodisk tjek): docs-sync R17/F-06 (ingen kodeændring)
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — Codex' seneste to
  entries (R14-deploy og R17-deploy-verifikation) var ikke reflekteret i selve
  `RISK_ASSESSMENT_v10.md`/`GO_LIVE_CHECKLIST_v10.md` endnu: begge dokumenter sagde stadig at
  R17 var "rettet i kode, IKKE deployet/live-verificeret", mens Codex faktisk havde committet
  (`44b78fb7`), deployet, genstartet servicen (health 200 OK) og kørt `npm run build` med succes
  på den rigtige maskine. `git status --short` viste fortsat kun samme untracked `claude_proxy.py`
  som hidtil (ladt urørt).
- **Vurdering:** Ingen af de resterende P0/P1-punkter i §11 (nginx→Cloudflare Tunnel, R09
  restore-test, R12 DPIA/retention-kode, R13 node-agent, HMAC-migrering, MFA/WebAuthn, intern
  CA/mTLS) er rent kode/dokumentation jeg kan gøre færdigt alene i denne kørsel uden enten
  Mac Mini/Orange Pi-adgang eller en juridisk/organisatorisk beslutning fra Peter. I stedet for at
  tvinge et nyt kodeindgreb valgte jeg denne runde en ren dokumentations-synkronisering, som var
  reelt ukorrekt/bagud og kunne have fået Peter/Codex til at undervurdere hvor langt R17 faktisk
  er kommet.
- **Rettet (kun dokumentation, ingen kode rørt):**
  1. `RISK_ASSESSMENT_v10.md` §10 (samlet risikooversigt): R17-rækken opdateret fra
     "🟢 (kode) … ikke deployet" til "🟢 (deployet) … health 200 + npm run build OK; manuel
     UI-smoketest fortsat ikke kørt".
  2. `RISK_ASSESSMENT_v10.md` R17-detaljeafsnittet: status- og verifikationstekst opdateret med
     Codex' deploy-entry (commit, health-check, build), og det er nu eksplicit at KUN den
     manuelle funktionelle smoketest (aktiver/deaktiver + kortvarig lav
     `TIMELAPSE_DEBUG_MODE_MAX_HOURS`) resterer — ikke build/deploy generelt.
  3. `RISK_ASSESSMENT_v10.md` §11 P2-listen: punkt 7 (CMDB-indikator/auto-timeout for debug/lab
     mode) markeret gennemstreget med note om at koden er deployet, kun smoketest udestår.
  4. `RISK_ASSESSMENT_v10.md` §12 (dokumenthistorik): ny linje for denne opdatering.
  5. `GO_LIVE_CHECKLIST_v10.md` F-06: opdateret fra "🟡 Ønsket" til "🟢 Deployet 2026-07-05 …
     kun manuel smoketest på live device udestår".
- **Verifikation her:** Ren tekst-/tabelredigering, ingen kode rørt — verificeret ved at
  genlæse de ændrede afsnit og bekræfte at markdown-tabellernes `|`-struktur stadig er intakt
  (ingen ekstra/manglende pipes), og at intet i teksten nu modsiger HANDOVER_LOG's faktiske
  hændelsesforløb. `git status --short` uændret bortset fra de to redigerede
  Dokumentation-filer.
- **IKKE gjort — bevidst:** Har ikke sat R17/F-06 til fuldt grønt/lukket — den manuelle
  live-smoketest (badge, "Aktiv siden", SIEM-event, faktisk auto-timeout-udløsning) er stadig
  ikke kørt af nogen, så begge dokumenter fastholder eksplicit at dette udestår. Har ikke rørt
  R13/R14/R09/R12 eller andre P0/P1-punkter denne runde.
- **Codex/Peter: ingen kommandoer nødvendige for selve denne ændring** (ren dokumentation) —
  men når I har et vindue til den udestående R17-smoketest (aktiver lab mode på et testdevice,
  bekræft badge + "Aktiv siden" + SIEM-event `debug_mode_change`, sæt evt.
  `TIMELAPSE_DEBUG_MODE_MAX_HOURS` lavt midlertidigt og bekræft `debug_mode_auto_timeout`), så
  markér venligst R17/F-06 fuldt grønt i begge dokumenter bagefter.
- **Filer rørt:** `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`.
- **Går videre til:** næste periodiske runde ser på enten SIEMPage.tsx-ikoner for
  `debug_mode_change`/`debug_mode_auto_timeout` (kosmetisk), eller #52 (intern CA/mTLS-design)
  hvis intet nyt er dukket op fra Codex i mellemtiden.

### Handover 2026-07-05 01:06 — fra Claude (periodisk tjek): SIEMPage.tsx-ikoner for debug_mode-events
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — ingen nye
  Codex-entries siden min 00:47-entry, intet åbent spørgsmål adresseret til mig. `git status
  --short` viste fortsat kun samme untracked `claude_proxy.py` (ladt urørt, fast konvention).
  Gennemgik §11/§10 i `RISK_ASSESSMENT_v10.md` og §J i `GO_LIVE_CHECKLIST_v10.md`: alle
  resterende P0/P1-punkter (nginx→Cloudflare Tunnel, R09 restore-test, R12 DPIA/retention, R13
  node-agent, HMAC-migrering, MFA/WebAuthn, intern CA/mTLS) kræver enten Mac Mini/Orange
  Pi-adgang eller en organisatorisk/juridisk beslutning fra Peter — ingen af dem var afgrænselige
  til denne ene kørsel. Tog derfor det selv-noterede "går videre til"-punkt fra min forrige
  entry: den kosmetiske SIEMPage.tsx-mangel for R17s to nye event-typer.
- **Fund ved scoping:** Bekræftede med `grep` at `EVENT_META` i
  `timelapse-ui/src/pages/SIEMPage.tsx` ikke havde entries for `debug_mode_change` eller
  `debug_mode_auto_timeout` — de ville derfor vises i events-listen/oversigten med det generiske
  `Activity`-fallback-ikon og selve event_type-strengen som label i stedet for en dansk label.
  Rent kosmetisk (ingen funktionel fejl), men gjorde SIEM-siden mindre læsbar for disse to nye
  R17-eventtyper.
- **Rettet (kode, `timelapse-ui/src/pages/SIEMPage.tsx`):** Importerede `Bug` og `Timer` fra
  `lucide-react` (begge findes i den installerede lucide-react v1.7.0) og tilføjede to
  `EVENT_META`-entries: `debug_mode_change` → `Bug`-ikon, amber (`text-amber-600`), label
  "Debug/lab mode ændret"; `debug_mode_auto_timeout` → `Timer`-ikon, lilla (`text-purple-500`),
  label "Debug/lab mode auto-timeout". Ingen ændring af logik, API eller datamodel — ren
  visuel/labelmæssig tilføjelse, samme mønster som de øvrige `EVENT_META`-entries.
  `RISK_ASSESSMENT_v10.md` R17-afsnittet fik en kort tilføjelse der noterer denne kosmetiske
  opfølgning uden at ændre R17s status/score.
- **Verifikation her:** `npx tsc -b` (typecheck, hele UI) grøn uden fejl efter ændringen —
  bekræfter at de nye imports/typer er korrekte og intet andet blev brudt. `git status --short`
  viser kun den forventede ene ændrede fil (`SIEMPage.tsx`) plus dokumentationsopdateringen; ingen
  andre filer rørt. Fuld `npm run build` ikke forsøgt igen i denne runde (samme kendte
  rolldown-sandbox-begrænsning som tidligere entries — ikke relateret til denne ændring, og
  tsc-typecheck dækker at ændringen er syntaktisk/type-korrekt).
- **IKKE gjort — bevidst:** Ingen ændring af selve R17-statussen/scoren (fortsat 🟢 deployet,
  manuel smoketest udestår, se tidligere entries). Ingen ændring af backend, database eller
  event-generering — kun visnings-metadata i frontend.
- **Bemærket, ikke rettet:** `.git/index.lock` findes fortsat i repoet fra sandbox-siden
  (samme harmløse, ikke-fjernbare lås som tidligere entries har beskrevet — `git status`/`git
  diff` virker fint alligevel). Codex/Peter bør som altid tjekke `ps aux | grep -i git` på den
  rigtige maskine før commit, ikke stole blindt på denne observation.
- **Codex/Peter: kør venligst** (ingen af disse er kørt af mig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add timelapse-ui/src/pages/SIEMPage.tsx Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "feat: SIEM UI-ikoner for debug_mode_change/debug_mode_auto_timeout (R17 kosmetisk opfølgning)"
  git push

  cd timelapse-ui && npm run build
  ```
  Forventet: commit pushet, `npm run build` lykkes (rent frontend-ikon-tillæg, ingen
  service-genstart nødvendig — ingen backend/API-ændring i denne commit).
- **Filer rørt:** `timelapse-ui/src/pages/SIEMPage.tsx`, `Dokumentation/RISK_ASSESSMENT_v10.md`.
- **Går videre til:** næste periodiske runde tager enten #52 (intern CA/mTLS-design) hvis intet
  nyt er dukket op fra Codex, eller den udestående R17 manuelle smoketest hvis Codex/Peter i
  mellemtiden har fået et vindue til at køre den og efterlader spørgsmål om resultatet.

### Handover 2026-07-05 (nat) — Codex: SIEM debug-mode ikonopfølgning udført
- **Udført:** Claudes kosmetiske R17-opfølgning er committet og pushet som `077450be`
  (`feat: SIEM UI-ikoner for debug_mode_change/debug_mode_auto_timeout (R17 kosmetisk opfølgning)`).
- **Verifikation:** `cd timelapse-ui && npx tsc -b` OK før commit. Efter push lykkedes
  `npm run build` på Mac'en; kun de kendte warnings om `module.register()`, ineffektiv dynamic
  import af `src/api/client.ts` og stor JS chunk.
- **Drift:** Ingen service-genstart udført eller nødvendig; ændringen er kun frontend
  event-metadata/ikoner.

### Handover 2026-07-05 01:28 — fra Claude (periodisk tjek): #52 intern CA/mTLS-design
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — ingen nye
  Codex-entries siden Codex' seneste SIEM-ikon-bekræftelse (`077450be`, efterfølgende docs-commit
  `72a89e43`), intet åbent spørgsmål adresseret til mig. `git status --short` viste fortsat kun
  samme untracked `claude_proxy.py` (ladt urørt) plus den kendte harmløse `.git/index.lock`
  (`git status`/`git log` virker fint alligevel — samme mønster som tidligere nævnt). Gennemgik
  §11/§10 i `RISK_ASSESSMENT_v10.md` igen: alle P0-punkter (Cloudflare Tunnel-migrering, R09
  restore-test, DPIA/retention R12, node-agent R13, global HMAC-enforcement) kræver stadig enten
  Mac Mini/Orange Pi/Cloudflare-adgang eller en juridisk/organisatorisk beslutning fra Peter. Tog
  derfor mit eget "går videre til"-punkt fra flere tidligere entries: #52 (intern CA/mTLS-design),
  som hidtil kun har været en overskrift, ikke et faktisk udfoldet forslag.
- **Udført (rent design/dokumentation, ingen kode rørt):** Læste først den faktiske device-auth-kode
  for at forankre designet i virkeligheden i stedet for at gætte: bootstrap-flow
  (`headend/main.py:1640,1765`), bearer-token-sammenligning (`:2071`), HMAC-request-signatur
  (`:2098-2127`), HMAC-enforcement-tælling fra R15 (`:2503,2585-2655`), og
  provisioneringspakke-generering (`_build_bootstrap_yaml`, `:9438`). Bekræftede ved `grep` at der
  **ingen PKI-kode findes i dag** (`cryptography`/`x509`/`generate_private_key` findes ikke i
  `headend/`/`edge/` — eneste træffere er Fernet-symmetrisk kryptering i `cmdb.py`, urelateret).
  Skrev derefter `Dokumentation/Claude_Intern_CA_mTLS_Design_2026-07-05.md`: Root CA → ny Issuing
  CA → device client cert (ECDSA P-256, CN/SAN = `device_id`), mTLS foreslået lagt **ved siden af**
  det eksisterende HMAC-lag (ikke erstatning, jf. defense-in-depth), CRL fremfor OCSP given
  fleet-størrelsen, og en udvidelse af det allerede spec'ede Key Mgmt UI (§14) med Issuing
  CA-status og cert-spærring.
- **Den konkrete blocker jeg identificerede (§6 i notatet):** valget mellem (A) Cloudflare Access
  mTLS/service tokens ved tunnel-indgangen, (B) ende-til-ende mTLS direkte til nginx/Headend, eller
  (C) en hybrid, afhænger af Cloudflare-planniveau/dashboard-konfiguration som jeg ikke har adgang
  til. Dette er sandsynligvis **hele grunden til** at #52 er blevet skubbet foran mig i flere
  runder nu — det er ikke en kodeopgave før dette arkitekturvalg er truffet.
- **Verifikation her:** Ren dokumentation — verificeret ved at genlæse hele det nye notat for intern
  konsistens (§4 PKI-hierarki matcher §7 nøglelivscyklus matcher §9 implementeringsplan), og ved at
  genlæse de opdaterede afsnit i `RISK_ASSESSMENT_v10.md` (§13.3, §11 P1.2, §12) for at bekræfte at
  markdown-tabellernes `|`-struktur stadig er intakt. Ingen kode/kørende systemer rørt.
- **IKKE gjort — bevidst:** Intet CA-nøglegenereringsscript skrevet, ingen ændring af
  `headend/main.py`/`edge/agent.py`, ingen ændring af selve R05/R07/R08-scoren (§13 var allerede
  markeret "ikke implementeret" — det er stadig sandt, nu blot med et konkret forslag klar til
  godkendelse). Har bevidst IKKE gættet på Cloudflare-planniveau eller truffet §6-valget selv —
  det er en netværkstopologi-/kontobeslutning, ikke noget kode kan afgøre.
- **Codex/Peter: ingen kommandoer at køre** (ren dokumentation, ingen deploy/service-genstart
  nødvendig). Når I har et vindue: læs `Claude_Intern_CA_mTLS_Design_2026-07-05.md` §6 og §10 og
  afgør (1) hvilken mTLS-model der passer til jeres Cloudflare-plan, (2) om 6-måneders
  cert-levetid stadig er ønsket, (3) om HMAC-laget skal bevares permanent ved siden af mTLS. Først
  derefter kan implementeringsplanen (§9 i notatet) sættes i gang.
- **Filer rørt:** `Dokumentation/Claude_Intern_CA_mTLS_Design_2026-07-05.md` (ny),
  `Dokumentation/RISK_ASSESSMENT_v10.md` (§13.3, §11 P1.2, §12 opdateret).
- **Går videre til:** næste periodiske runde ser på #53 (Nikon Z30 config-drift — resten af R14:
  UI/CMDB-visning af `camera_config_non_enforceable`, jf. entry 2026-07-05 00:12) hvis intet nyt
  er dukket op fra Codex, eller på Peters §6-beslutning hvis den er lagt i mellemtiden.

### Handover 2026-07-05 01:55 — fra Claude (periodisk tjek): R14 UI-visning + fundet uafhængig diagnostics-bug
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — ingen nye
  Codex-entries siden mit eget #52-notat, intet åbent spørgsmål adresseret til mig. `git status
  --short` viste fortsat kun samme untracked `claude_proxy.py` (ladt urørt) plus den kendte
  harmløse `.git/index.lock`. Tog mit eget "går videre til"-punkt: #53/resten af R14 —
  UI/CMDB-visning af `camera_config_non_enforceable` (feltet edge-siden allerede udstiller siden
  entry 00:12, men aldrig vist noget sted).
- **Fund ved scoping (utilsigtet, en reel, uafhængig bug):** Da jeg sporede hvordan
  `camera_config_drift`/`camera_config_non_enforceable` faktisk når frem til UI'en, opdagede jeg
  at `GET /api/admin/devices/{device_id}` (`headend/main.py::get_device_detail`) henter den
  seneste `Diagnostic`-række (`diag = db.query(Diagnostic)...first()`) men **ALDRIG serialiserer
  den i responsen** — ingen `"diagnostics"`-nøgle i JSON-svaret overhovedet. `git log -L
  12390,12390:headend/main.py` viser dette har været sådan siden commit `c7cb285b` (~15. april
  2026). Konsekvens: HELE "Hardware diagnostik"/"Kamera diagnostik"-panelet på enhedssiden
  (`DevicePage.tsx` → `StatsTab`) har vist tomt for enhver enhed i produktion i månedsvis — CPU-
  temp, SSD, NTP-offset, batteri, lukkertæller, config-drift, alt sammen. Stille fejl: frontend
  tjekker defensivt `diagnostics &&`/`diagnostics?.` overalt, så hverken en JS-fejl eller en
  synlig fejlbesked opstod — panelet forsvandt bare fuldstændig fra siden, uden at nogen (mig
  inklusive, i tidligere runder) opdagede det før nu.
- **Rettet (kode, ingen live services rørt):**
  1. `headend/main.py::get_device_detail` bygger nu en `"diagnostics"`-dict fra `diag` med alle
     felter frontendens `Diagnostic`-type forventer, og returnerer den. Ren tilføjelse — ingen
     eksisterende nøgler i responsen ændret eller fjernet.
  2. Ny kolonne `Diagnostic.cam_non_enforceable_json` (`headend/database.py`), skrevet ved hvert
     heartbeat (`headend/main.py` ~linje 3628) fra edge-feltet
     `camera_config_non_enforceable`, og inkluderet i den nye diagnostics-serialisering.
  3. Selvhelende, idempotent DB-migration **v14** tilføjet i `startup()` (samme mønster som
     v9–v13 i samme funktion): `ALTER TABLE diagnostics ADD COLUMN cam_non_enforceable_json TEXT`
     — kører automatisk ved næste headend-genstart. **Ingen manuel SQL-kommando nødvendig.**
  4. Frontend: `timelapse-ui/src/types/index.ts` (nyt felt i `Diagnostic`-typen),
     `timelapse-ui/src/pages/DevicePage.tsx` (ny grå info-boks under drift-sektionen der lister
     non-enforceable parametre med samme danske labels som drift-visningen — delt
     `CAM_PARAM_LABELS`-konstant, udtrukket fra `DriftBadge` for at undgå duplikering).
  5. `RISK_ASSESSMENT_v10.md`: R14-afsnittet, §10-oversigten, §11 P1.2 og §12-historikken
     opdateret med både UI-fixet og diagnostics-bugfundet.
- **Verifikation her:** `python3 -m py_compile headend/main.py headend/database.py` ren.
  `npx tsc -b` (hele UI) grøn uden fejl. Selvstændig Python-simulering af hele kæden (edge-payload
  → heartbeat-lagring → device-detail-serialisering → frontend-JSON-parsing) i et isoleret script
  bekræfter at `camera_config_drift` og `camera_config_non_enforceable` round-tripper korrekt
  gennem alle lag, og at et tomt non-enforceable-array håndteres uden fejl. `git status --short`
  viser præcis de 4 forventede ændrede filer (`headend/database.py`, `headend/main.py`,
  `timelapse-ui/src/types/index.ts`, `timelapse-ui/src/pages/DevicePage.tsx`) — ingen andre filer
  rørt.
- **IKKE gjort — bevidst:** ingen live-test mod faktisk Postgres-instans eller Orange Pi (kræver
  Mac Mini-adgang, har jeg ikke); R14-scoren nedgraderes IKKE til grøn — den grundlæggende "ikke
  verificeret på levende Z30-hardware"-status fra tidligere runder står fortsat ved magt, dette
  lukker kun UI-delen. Ingen ændring af selve drift-detektionslogikken fra entry 00:12.
- **Codex/Peter: kør venligst når I har et vindue** (ingen af disse er kørt af mig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add headend/database.py headend/main.py timelapse-ui/src/types/index.ts \
          timelapse-ui/src/pages/DevicePage.tsx Dokumentation/RISK_ASSESSMENT_v10.md \
          Dokumentation/HANDOVER_LOG.md
  git commit -m "fix: serialize diagnostics in device detail response + R14 non-enforceable UI"
  git push

  cd timelapse-ui && npm run build
  ```
  Deploy: pull + genstart `headend`-servicen på Mac Mini'en som normalt (v14-migrationen kører
  automatisk ved opstart, ingen manuel `ALTER TABLE` nødvendig), samt normal frontend-deploy.
  **Forventet effekt efter deploy:** enhedssidens "Statistik"-fane viser nu faktisk
  Hardware/Kamera-diagnostik-panelerne igen (har været tomme siden ~15. april) — værd at
  stikprøvetjekke på et par enheder efter deploy for at bekræfte at CPU-temp/SSD/batteri m.v.
  rent faktisk vises.
- **Filer rørt:** `headend/database.py`, `headend/main.py`, `timelapse-ui/src/types/index.ts`,
  `timelapse-ui/src/pages/DevicePage.tsx`, `Dokumentation/RISK_ASSESSMENT_v10.md`.
- **Går videre til:** næste periodiske runde stikprøvetjekker om Codex/Peter har fået deployet
  denne rettelse og om diagnostics-panelet rent faktisk viser data igen; ellers næste punkt er
  Peters §6-beslutning (intern CA/mTLS) hvis den er truffet, eller den udestående R17
  live-smoketest.

### Handover 2026-07-05 (nat) — Codex: diagnostics device-detail fix deployet
- **Udført:** Claudes diagnostics/R14-rettelse er committet og pushet som `4de7e918`
  (`fix: serialize diagnostics in device detail response + R14 non-enforceable UI`).
- **Verifikation før commit:** `python3 -m py_compile headend/main.py headend/database.py` OK og
  `cd timelapse-ui && npx tsc -b` OK.
- **Drift:** `dk.froekjaer.timelapse-headend` er genstartet med `launchctl kickstart`;
  `https://timelapse.froekjaer.dk/api/health` svarede `HTTP/1.1 200 OK`. DB-migration v14 kører
  automatisk i startup.
- **UI-build:** `npm run build` lykkedes på Mac'en. Kun kendte warnings:
  `module.register()` deprecation, ineffektiv dynamic import af `src/api/client.ts`, og stor
  JS chunk efter minificering.
- **Ikke udført automatisk:** UI-stikprøve på DevicePage/Statistik er ikke klikket igennem fra
  heartbeat, da API'en kræver autentificeret session/MFA. Bør tjekkes manuelt i UI'et: at
  Hardware/Kamera-diagnostik-panelet igen viser CPU/SSD/batteri/kamera-drift på et par enheder.

### Handover 2026-07-05 02:06 — fra Claude (periodisk tjek): H-02 ESLint-gate i CI (ratchet)
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — ingen nye
  Codex-entries siden diagnostics-deploy-bekræftelsen (`1a2bafb1`), intet åbent spørgsmål
  adresseret til mig. `git status --short` viste fortsat kun samme untracked `claude_proxy.py`
  (ladt urørt) plus den kendte harmløse `.git/index.lock`. Ingen af de udestående P0-punkter i
  §11 kan rykkes uden Mac Mini/Cloudflare/juridisk adgang, og Peters §6-beslutning (CA/mTLS) samt
  R17-live-smoketesten er stadig ikke besvaret. Valgte derfor P1.5 — **H-02 ESLint-gate i
  CI** — som hidtil kun har været et åbent punkt uden konkret forslag.
- **Analyse først:** Læste `.github/workflows/ci.yml` — bekræftede at der **ingen ESLint-step
  findes i dag** (kun `tsc --noEmit` + `npm run build` i `ui-check`-jobbet). Kørte
  `npx eslint . -f json` i `timelapse-ui/` og talte selv op: **204 fejl + 18 advarsler = 222**,
  hvilket bekræfter tallet der allerede stod i `GO_LIVE_CHECKLIST_v10.md` H-02. At kræve alle 222
  rettet før en gate kan aktiveres er urealistisk i én kørsel (kræver manuel gennemgang, jf.
  tidligere entries) — H-02's faktiske krav er "ingen NYE fejl", altså en ratchet, ikke en
  nul-fejl-gate.
- **Udført (rent CI/tooling, ingen produktkode rørt):**
  1. Ny `timelapse-ui/scripts/eslint-gate.mjs`: kører `eslint . -f json`, summerer
     fejl+advarsler, sammenligner mod en baseline-fil, exit 1 hvis flere problemer end baseline,
     exit 0 (med forslag om at sænke baseline) hvis færre eller uændret.
  2. Ny `timelapse-ui/.eslint-baseline.json`: `{"total": 222, "errors": 204, "warnings": 18,
     "updated": "2026-07-05"}` — matcher den dokumenterede status. Sænkes manuelt fremover i
     takt med oprydning (ingen automatisk nedjustering — bevidst, for at undgå at en gate
     stille sænker sig selv ved en fejl).
  3. `timelapse-ui/package.json`: nyt script `"lint:gate": "node scripts/eslint-gate.mjs"`.
  4. `.github/workflows/ci.yml`: nyt step "ESLint gate (H-02 — ingen nye fejl)" i `ui-check`-
     jobbet, mellem `tsc --noEmit` og `npm run build` — kører før build, så en regression
     stopper pipelinen tidligt.
  5. `RISK_ASSESSMENT_v10.md` (§11 P1.5) og `GO_LIVE_CHECKLIST_v10.md` (§H, H-02) opdateret til
     at afspejle at gaten er kodet, men endnu ikke committet/kørt i en rigtig CI-pipeline.
- **Verifikation her:** Kørte `node scripts/eslint-gate.mjs` direkte — rapporterer korrekt "204
  fejl, 18 advarsler (222 i alt)" mod baseline 222, exit 0. Simulerede derefter en regression ved
  midlertidigt at sætte baseline til 0 i en kopi — scriptet fejlede korrekt med exit 1 og en klar
  fejlbesked, hvorefter jeg gendannede den rigtige baseline-fil (verificeret ved at gencatte
  filen efter gendannelse). Bekræftede desuden at `.github/workflows/ci.yml` fortsat er gyldig
  YAML-struktur (visuel gennemlæsning af diff — kun to linjer tilføjet, ingen eksisterende steps
  rørt). Ingen `.py`-filer rørt i denne runde, så `py_compile` ikke relevant.
- **IKKE gjort — bevidst:** Ingen af de 222 eksisterende ESLint-problemer rettet — det var
  bevidst uden for scope for denne runde (kræver manuel gennemgang case for case, jf. tidligere
  entries om de 49 mekaniske fejl 2026-07-04). Gaten er derfor **ikke afprøvet i en rigtig
  GitHub Actions-runner** — kun lokalt i sandbox. Har bevidst IKKE selv committet/pushet
  (`.github/workflows/`-ændringer bør efter konvention ses af Peter/Codex først, særligt da det
  er en CI-adfærdsændring, ikke bare produktkode).
- **Bemærket, ikke rettet:** En efterladt `timelapse-ui/eslint_stderr.log` (tom, 0 bytes, fra
  min egen test-kørsel) kunne ikke slettes fra sandbox-siden (samme fillås-mønster som
  `.git/index.lock` i tidligere entries — "Operation not permitted" ved `rm`, men tømning til 0
  bytes lykkedes). Harmløs, men bør ryddes op/committes ikke af Peter/Codex.
- **Codex/Peter: kør venligst** (ingen af disse er kørt af mig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock
  rm -f timelapse-ui/eslint_stderr.log   # tom testfil, se note ovenfor

  git add .github/workflows/ci.yml timelapse-ui/package.json timelapse-ui/scripts/eslint-gate.mjs \
          timelapse-ui/.eslint-baseline.json Dokumentation/RISK_ASSESSMENT_v10.md \
          Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "ci: add ESLint ratchet gate (H-02) — fail only on new problems above baseline 222"
  git push
  ```
  Forventet: næste CI-kørsel på `main` (eller først synlig ved et efterfølgende PR/push, da
  `ui-check` trigges på push/PR til `main`) viser det nye "ESLint gate"-step som grønt (222 ≤
  222). Værd at bekræfte at selve GitHub Actions-runneren rent faktisk kører steppet og ikke
  fejler af miljøårsager (fx `npm ci` uden `--include=dev` — burde være fint, da eslint allerede
  er i `devDependencies`, men ikke testet i den rigtige runner af mig).
- **Filer rørt:** `.github/workflows/ci.yml`, `timelapse-ui/package.json`,
  `timelapse-ui/scripts/eslint-gate.mjs` (ny), `timelapse-ui/.eslint-baseline.json` (ny),
  `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`.
- **Går videre til:** næste periodiske runde bekræfter om Codex/Peter har committet og om CI
  rent faktisk er grøn med det nye step; ellers ser den på P1.4 (per-target deployment status)
  hvis intet nyt er dukket op, eller på Peters §6-beslutning (CA/mTLS) / R17-smoketest hvis en af
  dem er besvaret i mellemtiden.

### Handover 2026-07-05 (nat) — Codex: H-02 ESLint ratchet gate committet
- **Udført:** Claudes H-02 CI-gate er verificeret lokalt, committet og pushet som `68805577`
  (`ci: add ESLint ratchet gate (H-02) — fail only on new problems above baseline 222`).
- **Verifikation:** `cd timelapse-ui && node scripts/eslint-gate.mjs` rapporterede `204 fejl,
  18 advarsler (222 i alt)` mod baseline 222 og exit 0.
- **Oprydning:** Tom testfil `timelapse-ui/eslint_stderr.log` og stale `.git/index.lock` blev
  fjernet før commit. `claude_proxy.py` ligger fortsat untracked og urørt.
- **Ikke verificeret:** GitHub Actions-runneren er ikke tjekket fra heartbeat; næste push/PR til
  relevant branch bør vise om det nye "ESLint gate"-step også er grønt i CI-miljøet.

### Handover 2026-07-05 02:26 — fra Claude (periodisk tjek): P1.4/HLTH-008 — global update-status blev sat af ét device i multi-target rollouts
- **Kontekst:** Periodisk 20-minutters-tjek. Læste `HANDOVER_LOG.md`-halen — ingen nye
  Codex-entries siden H-02-commit-bekræftelsen (`68805577`/`6e3d54e9`), intet åbent spørgsmål
  adresseret til mig. `git status --short` viste fortsat kun samme untracked `claude_proxy.py`
  (ladt urørt), samt en forbigående `.git/index.lock`-advarsel fra selve `git status`-kaldet
  (kendt harmløst mønster fra tidligere runder). Ingen af de reelle P0-punkter kan rykkes uden
  Mac Mini/Cloudflare-adgang, og Peters §6-beslutning (CA/mTLS) samt R17-smoketesten er stadig
  ubesvarede. Tog derfor mit eget "går videre til"-punkt fra kl. 02:06: **P1.4 — per-target
  deployment status**.
- **Fund (dokumenterne var forældede):** `RISK_ASSESSMENT_v10.md`, `GO_LIVE_CHECKLIST_v10.md`,
  `KRAVREGISTER_og_STATUS_v10.md` og `SYSTEM_HEALTH_REGISTER.md` (HLTH-008) beskrev alle punktet
  som helt åbent/manglende ("kun global status på PendingUpdate", "ingen separat target-tabel").
  Kodegennemgang viste at `headend/database.py::UpdateTarget` (tabel `update_targets`) samt
  `/api/updates/{id}/flow-status` og `UpdatesPage.tsx`s per-device visning faktisk har
  eksisteret siden juni 2026 (`git log -S`: `flow-status`-endpointet siden commit `b3666709`,
  14. juni). Dokumenterne var altså ikke bare forsinkede — de beskrev en virkelighed der aldrig
  har været sand i denne form.
- **Den reelle, stadig-aktuelle bug (fundet ved at spore hvorfor risikoen alligevel føltes
  reel):** `headend/main.py::report_update` (`/api/updates/report`) satte hidtil den GLOBALE
  `PendingUpdate.status` direkte fra ÉT enkelt device's rapport, uden hensyn til `scope`. For
  `scope=global/customer/site` (flere targets) betød det at ét device alene kunne gøre en hel
  rollout "deployed" eller "rolled_back", mens resten af flåden stadig var undervejs — præcis
  den risiko HLTH-008 beskriver, bare med en forældet begrundelse. Bemærkelsesværdigt: samme fils
  `_update_flow_stage()` forudsatte allerede (via "Edge arbejder"/"Afventer Edge
  heartbeat"-grenene) at `PendingUpdate.status` burde blive stående på `approved` indtil alle
  targets er færdige — så rettelsen følger kodens eget eksisterende designintent, ikke ny
  adfærd. Sidegevinst: `deployed_count` blev aldrig inkrementeret ved success (kun
  `failed_count` ved fejl/rollback) — allerede noteret som uafklaret i `Update_Flow_v10.md`
  linje 549 ("count-felterne bør harmoniseres").
- **Rettet i kode (kun `headend/main.py`, ingen live services rørt):** I `report_update`:
  1. For `scope="device"` (ét target, eller intet `device_id` i payload) er adfærden **uændret**
     — øjeblikkelig flip af global status, som hidtil (dette er den hyppigst testede sti, fx
     QA E2E-eksemplet i `Update_Flow_v10.md`). `deployed_count` inkrementeres nu også her
     (bugfix).
  2. For multi-target scopes (`global`/`customer`/`site`) flippes global status IKKE længere fra
     ét enkelt report. I stedet beregnes et rollup ved hvert report: `_resolve_update_targets()`
     giver det fulde forventede target-sæt; `deployed_count`/`failed_count` sættes altid til de
     faktiske tal fra `update_targets`-rækkerne; global status flippes først til `deployed` når
     ALLE targets har rapporteret `deployed`, eller til `rolled_back` (konservativt, ved
     blandet udfald) når alle targets er i terminal-tilstand men ikke alle lykkedes.
- **Verifikation her:** `python3 -m py_compile headend/main.py headend/database.py` ren. Da hele
  `main.py` kræver FastAPI/Postgres-stack der ikke er tilgængelig i sandbox, byggede jeg i
  stedet en isoleret Python-simulering af selve rollup-algoritmen (1:1 genskabt logik, ingen
  mocking af ukendt adfærd) og kørte 3 scenarier: (a) 3-device site-rollout hvor 2 melder
  `deployed` og 1 stadig er `downloading` → global status forbliver `approved`,
  `deployed_count=2`; det 3. device melder `deployed` → global status flipper først da til
  `deployed`, `deployed_count=3`; (b) `scope=device`, ét device melder `deployed` → status
  flipper øjeblikkeligt som hidtil, og `deployed_count` går nu korrekt til 1 (var tidligere
  fastfrosset på 0 — bekræftet bug); (c) `scope=global`, 2 devices hvor det ene melder
  `deployed` og det andet `rolled_back` → begge terminale, status sættes konservativt til
  `rolled_back`, `deployed_count=1`, `failed_count=1`. Alle 3 scenarier gav forventet resultat.
  `git status --short` viser kun `headend/main.py` ændret (plus den kendte untracked
  `claude_proxy.py`) — ingen andre filer rørt.
- **IKKE gjort — bevidst:** Ingen live-test mod faktisk Postgres-instans eller en rigtig
  multi-device rollout (kræver Mac Mini-adgang). Ingen ændring af `force_rollback`,
  `promote_update` eller auto-deploy-evaluate-endpointerne — kun `report_update` er rørt.
  R06-residualrisikoen nedgraderes IKKE fuldt til grøn før live-verificeret.
- **Dokumenter opdateret (kun tekst, ingen kode):** `RISK_ASSESSMENT_v10.md` (R06, §11 P1.4,
  §12-historik), `GO_LIVE_CHECKLIST_v10.md` (§K "Per-target update status"),
  `KRAVREGISTER_og_STATUS_v10.md` (UPD-012), `SYSTEM_HEALTH_REGISTER.md` (HLTH-008 — fuld
  korrektion af den forældede evidens).
- **Codex/Peter: kør venligst når I har et vindue** (ingen af disse er kørt af mig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add headend/main.py Dokumentation/RISK_ASSESSMENT_v10.md \
          Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/KRAVREGISTER_og_STATUS_v10.md \
          Dokumentation/SYSTEM_HEALTH_REGISTER.md Dokumentation/HANDOVER_LOG.md
  git commit -m "fix: multi-target update rollout status no longer flipped by single device report (HLTH-008)"
  git push
  ```
  Deploy: genstart `headend`-servicen på Mac Mini'en som normalt. Ingen DB-migration nødvendig
  (ingen skemaændring). **Værd at stikprøvetjekke efter deploy:** kør en multi-device
  test-rollout (fx `scope=site` med 2+ test-enheder) og bekræft i `UpdatesPage.tsx` at
  update'en forbliver "Godkendt"/"approved" indtil ALLE enheder har rapporteret, og først
  derefter viser "Deployet" (eller "Rullet tilbage" ved blandet udfald).
- **Filer rørt:** `headend/main.py`, `Dokumentation/RISK_ASSESSMENT_v10.md`,
  `Dokumentation/GO_LIVE_CHECKLIST_v10.md`, `Dokumentation/KRAVREGISTER_og_STATUS_v10.md`,
  `Dokumentation/SYSTEM_HEALTH_REGISTER.md`.
- **Går videre til:** næste periodiske runde bekræfter om Codex/Peter har committet/deployet
  denne rettelse og evt. kørt en live multi-device-test; ellers ser den på Peters §6-beslutning
  (CA/mTLS) eller R17-smoketesten hvis en af dem er besvaret, eller på H-04/H-05/H-06 i
  GO_LIVE_CHECKLIST §H hvis intet nyt er dukket op.

### Handover 2026-07-05 (nat) — Codex: HLTH-008 multi-target rollout status deployet
- **Udført:** Claudes HLTH-008/P1.4 rettelse er committet og pushet som `61802951`
  (`fix: multi-target update rollout status no longer flipped by single device report (HLTH-008)`).
- **Verifikation før commit:** `python3 -m py_compile headend/main.py headend/database.py` OK.
- **Drift:** `dk.froekjaer.timelapse-headend` er genstartet med `launchctl kickstart`;
  `https://timelapse.froekjaer.dk/api/health` svarede `HTTP/1.1 200 OK`.
- **Ikke udført automatisk:** Live multi-device rollout-test er ikke kørt fra heartbeat, da den
  ændrer update-state for rigtige enheder. Bør testes kontrolleret med 2+ test-enheder: global
  update-status skal blive på `approved` indtil alle targets er terminale.

### Handover 2026-07-05 — fra Claude (periodisk tjek): docs-sync efter Codex' commits/deploy (H-02, HLTH-008)

- **Kontekst:** Periodisk 20-minutters-tjek. Læste HANDOVER_LOG-halen — seneste entry er Codex'
  bekræftelse af at HLTH-008-rettelsen er committet (`61802951`), pushet og deployet (headend
  genstartet, `/api/health` 200 OK). Ingen nyt spørgsmål adresseret til Claude. `git status
  --short` viste udelukkende samme kendte untracked `claude_proxy.py` (urørt, som hidtil) — ingen
  uncommittede rester fra tidligere sessioner.
- **Fund:** `RISK_ASSESSMENT_v10.md` (§11 P1.4/P1.5, R06-korrektion, §12-historik),
  `GO_LIVE_CHECKLIST_v10.md` (§H H-02, §K per-target status), `KRAVREGISTER_og_STATUS_v10.md`
  (UPD-012) og `SYSTEM_HEALTH_REGISTER.md` (HLTH-008) var alle bagud ift. HANDOVER_LOG: de sagde
  stadig "afventer commit/push" for både H-02 (ESLint-gate, faktisk pushet af Codex som `68805577`
  ifølge en tidligere Codex-entry) og HLTH-008/P1.4 (faktisk committet som `61802951` OG deployet
  med bekræftet health-check, per entrien lige ovenfor). Samme mønster som tidligere docs-sync-
  runder (fx R17 2026-07-05 nat) — dokumenterne opdateres ikke automatisk når Codex committer.
- **Rettet (kun tekst, ingen kode rørt):** Opdaterede de 4 dokumenter til at afspejle den
  faktiske status: H-02 sat til 🟢 (kode pushet som `68805577`, resterer kun bekræftelse af grøn
  GitHub Actions-kørsel); HLTH-008/UPD-012/P1.4 sat til 🟢 (kode committet `61802951`, deployet,
  health OK — resterer kun en faktisk live multi-device-rollouttest, IKKE kun "commit/push" som
  dokumenterne fejlagtigt stadig sagde). R06-residualrisiko-teksten justeret til "🟢 4 i kode og i
  produktion" (var "i kode" alene). Tilføjet ny §12-historik-linje.
- **Verifikation her:** Ren tekstredigering af 4 `.md`-filer — ingen `.py`/kode rørt, så
  `py_compile` ikke relevant. Genlæste hvert redigeret afsnit efter ændring for at bekræfte at
  markdown-struktur og tabelformattering er intakt (ingen ødelagte `|`-tabeller). `git status
  --short` bekræftede bagefter at kun de 4 tilsigtede `.md`-filer er ændret (plus den kendte
  untracked `claude_proxy.py`, urørt).
- **IKKE gjort — bevidst:** Ingen kodeændringer denne runde. Ingen forsøg på at bekræfte GitHub
  Actions-runner-status eller køre en live multi-device-rollout (kræver hhv. GitHub-adgang og
  Mac Mini-adgang, som heartbeat ikke har).
- **Codex/Peter: kør venligst når I har et vindue** (ingen kode ændret, kun docs — normal commit-
  konvention gælder stadig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/GO_LIVE_CHECKLIST_v10.md \
          Dokumentation/KRAVREGISTER_og_STATUS_v10.md Dokumentation/SYSTEM_HEALTH_REGISTER.md \
          Dokumentation/HANDOVER_LOG.md
  git commit -m "docs: sync H-02/HLTH-008 status after commit+deploy (docs had gone stale)"
  git push
  ```
- **Filer rørt:** `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`,
  `Dokumentation/KRAVREGISTER_og_STATUS_v10.md`, `Dokumentation/SYSTEM_HEALTH_REGISTER.md`.
- **Går videre til:** næste periodiske runde tjekker om GitHub Actions-runneren viser H-02-gaten
  grøn, eller om en live multi-device-rollouttest (HLTH-008) er udført; ellers Peters §6-beslutning
  (CA/mTLS), R17-smoketesten, eller H-04/H-05/H-06 i GO_LIVE_CHECKLIST §H hvis intet nyt er dukket op.

### Handover 2026-07-05 — fra Claude (periodisk tjek): H-05 kontrakttest afslørede REGRESSION i den deployede HLTH-008-fix — multi-target rollouts flipper aldrig status (fastfrosset på "approved")

- **Kontekst:** Periodisk 20-minutters-tjek. Læste HANDOVER_LOG-halen — seneste entry er min egen
  docs-sync (§11 P1.4/P1.5, R06, §12) efter at Codex committede/pushede/deployede både H-02
  (`68805577`) og HLTH-008 (`61802951`). Intet nyt spørgsmål adresseret til mig. `git status
  --short` viste udelukkende samme kendte untracked `claude_proxy.py` (urørt) — ingen uncommittede
  rester fra tidligere sessioner rørt. Ingen af de reelle P0-punkter (Cloudflare Tunnel-migrering,
  off-site backup, DPIA, node-agent, stale credentials) kan rykkes uden Mac Mini/Cloudflare/
  juridisk adgang, og Peters §6-beslutning (CA/mTLS) samt R17-smoketesten er stadig ubesvarede.
  Tog derfor mit eget "går videre til"-punkt: **H-05 i GO_LIVE_CHECKLIST §H — "Python test-suite
  med edge/headend contract-tests"** (🟡 Ønsket, helt åben, ingen `headend/tests/`-mappe fandtes).
- **Opsætning (denne runde, ikke tidligere muligt):** Opdagede at `headend/database.py` faktisk
  understøtter SQLite via `DATABASE_URL`-miljøvariablen (bruges allerede til noget andet i
  produktion — se linje 43-46) — det betyder at `headend/main.py` KAN importeres og køres i
  sandbox'en uden Postgres, hvis man bygger et minimalt, isoleret virtuelt miljø med kun de
  moduler `main.py` reelt importerer på modul-niveau (`fastapi`, `sqlalchemy`, `slowapi`,
  `python-jose`, `bcrypt`, `passlib`, `python-multipart`, `python-dotenv` — `webauthn`/`pyotp`/
  `google-genai` importeres kun lazily inde i funktioner og var ikke nødvendige). Den eksisterende
  `headend/venv/` i repoet er en macOS-venv (binær `Exec format error` i Linux-sandbox) og kunne
  ikke genbruges direkte, men et helt nyt venv i `/tmp` med de pinnede versioner fra
  `requirements.txt` virkede og kunne importere `main.py` uden fejl.
- **Skrevet:** `headend/tests/test_report_update_rollup.py` — en RIGTIG kontrakttest der kalder
  den faktiske `report_update()`-funktion i `main.py` direkte (ikke via HTTP/TestClient, for at
  undgå `@app.on_event("startup")`-bivirkninger som baggrundstråde/log-collector — FastAPI's
  `@app.post`-dekorator returnerer selve funktionen uændret, så direkte kald er ækvivalent for
  denne funktions logik) mod en frisk, midlertidig SQLite-fil. 4 testcases: (1) multi-target
  site-rollout hvor 2 devices er terminale og 1 stadig kører → status skal blive "approved"; alle
  3 rapporterer "deployed" → status skal flippe til "deployed"; (2) `scope="device"` skal fortsat
  flippe øjeblikkeligt (uændret sti); (3) blandet udfald (1 deployed, 1 rolled_back) → konservativ
  "rolled_back"; (4) rene fremskridtsstatusser (queued/downloading/…) må aldrig flippe status.
- **FUND — den deployede `61802951`-fix virker ikke som tiltænkt:** 2 af de 4 tests fejlede FØR
  jeg rettede noget: både "alle targets bliver til sidst deployed" og "blandet udfald" testen
  fejlede med `assert 'approved' == 'deployed'` / `'rolled_back'`. Rodårsag fundet ved at spore
  koden: `database.py` linje 73 sætter `SessionLocal = sessionmaker(..., autoflush=False, ...)`.
  I `report_update()` tilføjes/ændres dette devices EGEN `UpdateTarget`-række (`db.add(target)`
  eller feltopdateringer på en eksisterende) — men fordi autoflush er slået fra, bliver denne
  ændring IKKE sendt til databasen før et eksplicit `db.commit()`/`db.flush()`. Rollup-koden
  længere nede kalder `db.query(UpdateTarget).filter_by(pending_update_id=u.id)...all()` for at
  tælle hvor mange targets der er terminale — men denne forespørgsel går direkte mod DB'en og ser
  IKKE den lige tilføjede/ændrede, endnu ikke flush'ede række. Konsekvens: netop det SIDSTE device
  i en multi-target rollout (det der reelt ville gøre alle targets terminale) tælles ALDRIG med i
  sin egen afsluttende rapport — `len(statuses) == total` bliver derfor aldrig sandt, og global
  status flipper aldrig til `deployed`/`rolled_back`. Rollout'en hænger fast på "approved" for
  evigt (indtil et helt urelateret, efterfølgende device-report for samme update tilfældigvis
  får den forsinkede række med — hvilket i praksis sjældent/aldrig sker for en allerede afsluttet
  rollout). **Dette er reelt værre end den oprindelige HLTH-008-risiko** (for-tidlig flip er
  erstattet af en flip der aldrig sker), og det er i PRODUKTION nu, da `61802951` er deployet.
- **Rettet i kode (kun `headend/main.py`, 1 linje + kommentar):** Tilføjet `db.flush()` i
  `report_update()` umiddelbart før rollup-forespørgslen (samme sted som den eksisterende
  HLTH-008-kommentar), så dette devices egen, netop tilføjede/ændrede `UpdateTarget`-række er
  synlig for forespørgslen der tæller terminale targets. Ingen anden logik ændret.
- **Verifikation:** `python3 -m py_compile headend/main.py headend/database.py` ren. Byggede
  minimal venv i `/tmp/hvenv` (se ovenfor) og kørte `pytest headend/tests/test_report_update_rollup.py
  -v`: 2 fejl FØR flush-rettelsen (nøjagtig de scenarier hvor sidste device fuldfører rollout'en),
  4/4 bestået EFTER. Dette er en test af den FAKTISKE kode i `main.py` — ikke en isoleret
  simulering (i modsætning til forrige rundes verifikation af selve `61802951`-fixet). Ingen live
  Postgres/produktions-DB rørt; testen bruger udelukkende en midlertidig SQLite-fil.
- **IKKE gjort — bevidst:** Ingen commit/push. Ingen live-test mod faktisk produktions-rollout
  (kræver Mac Mini-adgang). Ingen ændring af andre dele af `report_update()`, `_resolve_update_
  targets()` eller `_update_flow_stage()`.
- **Dokumenter opdateret (kun tekst):** `SYSTEM_HEALTH_REGISTER.md` (HLTH-008 genåbnet til 🟠/P0
  med fuld regressions-analyse), `RISK_ASSESSMENT_v10.md` (R06 residualrisiko genopjusteret til
  🟠 8, §11 P1.4 un-strike'et, ny §12-historik-linje), `GO_LIVE_CHECKLIST_v10.md` (§K genopjusteret
  til P0), `KRAVREGISTER_og_STATUS_v10.md` (UPD-012 genopjusteret til 🟠).
- **Codex/Peter: kør venligst SNAREST — dette er en aktiv produktionsregression, ikke kun docs**
  (kode + ny testfil, ingen af delene committet af mig):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add headend/main.py headend/tests/test_report_update_rollup.py \
          Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/GO_LIVE_CHECKLIST_v10.md \
          Dokumentation/KRAVREGISTER_og_STATUS_v10.md Dokumentation/SYSTEM_HEALTH_REGISTER.md \
          Dokumentation/HANDOVER_LOG.md
  git commit -m "fix: flush update_targets before multi-target rollup so last device is counted (HLTH-008 regression)"
  git push
  ```
  Verificér lokalt før commit hvis I vil (kræver et venv med fastapi/sqlalchemy/slowapi/
  python-jose/bcrypt/passlib/python-multipart/python-dotenv/pytest installeret — se
  `headend/tests/test_report_update_rollup.py`s docstring for præcis opskrift):
  ```bash
  cd /Users/peter/projects/timelapse-pro/headend
  python3 -m pytest tests/test_report_update_rollup.py -v
  ```
  Deploy: genstart `headend`-servicen på Mac Mini'en som normalt (samme som ved `61802951`).
  Ingen DB-migration nødvendig. **Værd at stikprøvetjekke efter deploy:** kør en multi-device
  test-rollout (`scope=site`, 2+ enheder) og bekræft at update'en rent faktisk skifter til
  "Deployet" (eller "Rullet tilbage") når alle enheder har rapporteret — IKKE kun at den forbliver
  "Godkendt" undervejs (det sidste var allerede bekræftet af `61802951`; det nye at bekræfte er at
  den rent faktisk kommer i mål).
- **Filer rørt:** `headend/main.py`, `headend/tests/test_report_update_rollup.py` (ny fil),
  `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`,
  `Dokumentation/KRAVREGISTER_og_STATUS_v10.md`, `Dokumentation/SYSTEM_HEALTH_REGISTER.md`.
- **Går videre til:** næste periodiske runde bekræfter om Codex/Peter har committet/deployet
  flush-rettelsen og evt. kørt en live multi-device-test; ellers ser den på H-05 (flere
  contract-tests, fx for `_resolve_update_targets`/`promote_update`/`force_rollback`), Peters
  §6-beslutning (CA/mTLS), eller R17-smoketesten hvis en af dem er besvaret i mellemtiden.

### Handover 2026-07-05 03:2x — fra Claude (periodisk tjek): H-05 udvidet med flere contract-tests + endnu et gap fundet (device-decommission midt i rollout)

- **Kontekst:** Periodisk 20-minutters-tjek. Læste HANDOVER_LOG-halen — seneste entry er min
  egen forrige runde (flush-regression i `report_update()`, 1-linjes fix + ny test,
  IKKE committet endnu). `git status --short` uændret siden da: samme 4 `.md`-filer +
  `headend/main.py` + `headend/tests/` (ny) + den kendte untracked `claude_proxy.py` —
  ingen ny Codex-entry, intet committet/pushet af flush-fixet endnu. Kørte
  `tests/test_report_update_rollup.py` igen for at bekræfte baseline stadig er 4/4 grøn med
  den uncommittede fix i arbejdstræet (den var).
- **Fund (gennemgang, ingen ny bug i denne omgang):** Læste `promote_update()`,
  `force_rollback()` og `_auto_approve_update_for_target()` linje for linje for at lede efter
  samme autoflush-mønster som HLTH-008-regressionen (dvs. en `db.query(...)` der forudsætter at
  en lige tilføjet/ændret række allerede er synlig). Fandt INGEN tilsvarende bug: `promote_update()`
  kalder allerede `db.flush()` efter `db.add(prod_update)` før den efterfølgende brug;
  `force_rollback()` sætter kun status og committer uden mellemliggende query;
  `_auto_approve_update_for_target()` flusher allerede efter `db.add(ticket)`. Denne gennemgang var
  selve arbejdet denne runde (negativt resultat er stadig et resultat — bekræfter at
  flush-regressionen var isoleret til `report_update()`, ikke et bredere mønster i update-flow-koden).
- **Skrevet:** `headend/tests/test_update_lifecycle.py` (ny fil, 9 tests) — supplerer H-05:
  1. `_resolve_update_targets()` for alle 5 scopes (device/site/customer/global/eksplicit
     `target_device_ids`, inkl. device-scope mod et device der ikke findes i CMDB → tom liste,
     ingen crash).
  2. `force_rollback()` — status flipper til `rollback_requested`; 404 for ukendt update-id.
  3. **Ny edge case fundet og dokumenteret (test, ikke rettet):** hvis et device fjernes fra
     CMDB (`Device`-rækken slettet — fx decommissioned/udskiftet hardware, jf. R16-mønsteret)
     MIDT i en igangværende multi-target rollout, EFTER det selv har rapporteret en
     ikke-terminal status (`downloading`), tæller `_resolve_update_targets()` det fjernede
     device ikke længere med i `total`. Konsekvens: rollup'en flipper global status til
     `deployed`, så snart de RESTERENDE devices er terminale — selvom det fjernede device reelt
     aldrig afsluttede sin egen installation. Dette er en separat, snævrere risiko end
     HLTH-008-flush-bugget (som er dækket af flush-fixet) — det kræver et device der fysisk
     forsvinder fra CMDB midt i en rollout, hvilket er sjældnere end "et device rapporterer bare
     langsomt". Testen bekræfter dette er den FAKTISKE nuværende opførsel (ikke en hypotese).
- **Verifikation:** `python3 -m pytest tests/ -v` → 13/13 bestået (4 eksisterende +
  9 nye). `python3 -m py_compile headend/main.py headend/database.py` ren (ingen kode ændret,
  kun ny testfil). `git status --short` bekræftede bagefter at kun `headend/tests/test_update_lifecycle.py`
  er tilføjet ift. sidste runde — ingen andre filer rørt denne gang.
- **IKKE gjort — bevidst:** Ingen rettelse af device-decommission-gap'et (kræver en
  produktbeslutning: skal et device der forsvinder fra CMDB midt i en rollout tælles som
  "aldrig terminal" for evigt, blokere rollout'en permanent, eller behandles som nu? Alle tre
  har afvejninger — bør besluttes af Peter, ikke antaget af mig). Ingen commit/push (samme
  konvention som hidtil — kode+tests afventer Codex/Peters commit sammen med flush-fixet).
- **Codex/Peter:** intet nyt hastende at køre ud over den allerede rapporterede
  flush-fix-commit fra forrige runde (se ovenfor). Når I committer, tag også
  `headend/tests/test_update_lifecycle.py` med i samme `git add`:
  ```bash
  git add headend/tests/test_update_lifecycle.py
  ```
  (kan tilføjes til den tidligere foreslåede `git add`-linje for flush-fixet).
- **Filer rørt:** `headend/tests/test_update_lifecycle.py` (ny fil). Ingen andre filer.
- **Går videre til:** næste periodiske runde bekræfter om flush-fixet + de nye tests er
  committet/deployet og om en live multi-device-test er kørt; ellers vurderer den
  device-decommission-gap'et ovenfor som et nyt, lille RISK_ASSESSMENT/GO_LIVE-punkt (kræver
  først Peters produktbeslutning om ønsket adfærd), eller ser på Peters §6-beslutning (CA/mTLS)
  / R17-smoketesten hvis en af dem er besvaret i mellemtiden.

### Handover 2026-07-05 03:4x — fra Claude (periodisk tjek): H-06 lukket — repo-rod README var stadig `create-vite`-boilerplate

- **Kontekst:** Periodisk 20-minutters-tjek. Læste HANDOVER_LOG-halen — seneste entry er min
  egen forrige runde (H-05 udvidet, device-decommission-gap dokumenteret som test, IKKE
  committet). `git status --short` uændret siden da: samme 4 `.md`-filer + `headend/main.py`
  (flush-fix) + `headend/tests/` (2 filer, 13 tests) + kendt untracked `claude_proxy.py` —
  ingen ny Codex-entry, intet committet/pushet/deployet endnu. Ingen ny live-info om Peters
  §6-beslutning (CA/mTLS) eller R17-smoketesten. Da tre på hinanden følgende runder allerede har
  brugt kredit på `report_update()`/update-lifecycle-kontrakttests (H-05), og videre arbejde der
  nu kræver enten en produktbeslutning (device-decommission) eller adgang jeg ikke har (live
  test), valgte jeg i stedet et andet, helt uafhængigt og fuldt afsluttet ønsket punkt fra samme
  GO_LIVE_CHECKLIST §H: **H-06 — "README opdateret (ikke Vite-template)"**.
- **Fund:** Repo-rodens `README.md` (`/Users/peter/projects/timelapse-pro/README.md`, ikke
  `timelapse-ui/README.md`) var stadig 100% uændret `create-vite`-skabelonen ("React + TypeScript
  + Vite... This template provides a minimal setup...") — ingen omtale af headend, edge,
  timelapse-ui, node-agent, website, tests eller `Dokumentation/`. Der findes intet
  `package.json` i repo-roden (kun i `timelapse-ui/`), så dette er tydeligvis en fejlagtigt
  efterladt fil fra dengang `timelapse-ui` blev scaffoldet, ikke et bevidst tomt monorepo-README.
- **Rettet:** Erstattede `README.md` med et reelt projekt-README: kort formål/status-linje
  (LAB/pre-production, peger til `Dokumentation/00_START_HER.md` og
  `GO_LIVE_CHECKLIST_v10.md`/`RISK_ASSESSMENT_v10.md` for detaljer — README'et duplikerer
  bevidst IKKE arkitektur/sikkerhedsindhold, kun "kom i gang"), en tabel over mappestrukturen
  (`headend/`, `edge/`, `timelapse-ui/`, `node-agent/`, `website/`, `deploy/`, `tests/`,
  `Dokumentation/`), copy-paste lokal opsætning for headend (venv + `DATABASE_URL=sqlite:///`
  til lokal test, jf. samme SQLite-mønster som H-05-testene bruger), UI (`npm install`/`dev`/
  `build`/`lint:gate`) og edge (pointer til Installationsguide Del B/C), test-kommandoer
  (`pytest tests/`, `cd headend && pytest tests/ -v`, `npm run lint:gate`), samt et kort
  sikkerheds-/compliance-afsnit (SABSA/ISO 27001/IEC 62443/CRA/GDPR/NIS2/AI Act) med pointer til
  `Dokumentation/`.
- **Verifikation:** Ren dokumentationsændring, ingen kode rørt. Tjekkede at antal
  markdown-kodeblok-afgrænsninger (` ``` `) er lige (6 — balanceret, ingen ufuldstændige
  fences), og læste filen igennem for korrekthed mod faktisk repo-struktur (`ls` af alle nævnte
  mapper, `timelapse-ui/package.json`-scripts, `headend/requirements.txt`) før commit-forslag.
  Ingen `py_compile`/`pytest` relevant (ingen `.py`/`.ts`-filer ændret).
- **Også opdateret (samme runde, konsistens):** `GO_LIVE_CHECKLIST_v10.md` §H — H-06 sat til
  🟢 med beskrivelse af rettelsen; H-05-rækken fik samtidig en statusopdatering (var stadig
  plain "🟡 Ønsket" selvom 13 tests reelt er skrevet af tidligere runder) så tabellen ikke
  modsiger `RISK_ASSESSMENT_v10.md` §11 P1.4/HANDOVER_LOG. Ingen ændring i
  `KRAVREGISTER_og_STATUS_v10.md` — der findes ikke en tilsvarende README-linje der, og det er
  ikke et krav-register-punkt.
- **IKKE gjort — bevidst:** Ingen ændring af `timelapse-ui/README.md` (ikke undersøgt denne
  runde — kan være et separat, mindre punkt hvis det også er uændret Vite-boilerplate). Ingen
  commit/push (samme konvention — afventer Codex/Peter, kan tages sammen med de øvrige
  uncommittede filer nedenfor).
- **Codex/Peter: kør venligst når I har et vindue** (README + docs, ingen kodeadfærd ændret —
  kan committes uafhængigt af flush-fix/tests, eller samlet):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt) rm -f .git/index.lock

  git add README.md Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "docs: replace stale create-vite README with real project README (H-06)"
  git push
  ```
  (Kan evt. laves som ét samlet commit med de øvrige uncommittede filer —
  `headend/main.py`, `headend/tests/`, `RISK_ASSESSMENT_v10.md`,
  `KRAVREGISTER_og_STATUS_v10.md`, `SYSTEM_HEALTH_REGISTER.md` — se forrige to entries. README-
  ændringen er uafhængig og kan også committes for sig, hvis I foretrækker mindre commits.)
- **Filer rørt:** `README.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`.
- **Går videre til:** næste periodiske runde bekræfter om noget af det ovenstående (flush-fix,
  H-05-tests, README) er committet/deployet; ellers kigger den på `timelapse-ui/README.md` (er
  den også stadig Vite-boilerplate?), H-04 (`deploy/launchd/...plist` ikke-secret version,
  🟠 Mangler i §H), device-decommission-gap'et (kræver Peters produktbeslutning), eller Peters
  §6-beslutning (CA/mTLS) / R17-smoketesten hvis en af dem er besvaret i mellemtiden.

### Handover 2026-07-05 (nat) — Codex: HLTH-008 regression + H-05 tests + H-06 README udført
- **Udført:** Den aktive HLTH-008 regression er committet og pushet som `1e3c3321`
  (`fix: flush update_targets before multi-target rollup so last device is counted (HLTH-008 regression)`).
  Committen inkluderer `db.flush()`-rettelsen, `headend/tests/test_report_update_rollup.py`,
  `headend/tests/test_update_lifecycle.py` og de tilhørende statusdokumenter.
- **Tests:** `python3 -m py_compile headend/main.py headend/database.py` OK. Midlertidigt venv i
  `/tmp/tlp-hvenv` blev oprettet efter test-docstringen, og
  `/tmp/tlp-hvenv/bin/python -m pytest tests/test_report_update_rollup.py tests/test_update_lifecycle.py -v`
  gav `13 passed, 7 warnings`.
- **Deploy:** `dk.froekjaer.timelapse-headend` er genstartet med `launchctl kickstart`;
  `https://timelapse.froekjaer.dk/api/health` svarede `HTTP/1.1 200 OK`.
- **README/H-06:** Repo-README-oprydningen er committet og pushet separat som `9dda9923`
  (`docs: replace stale create-vite README with real project README (H-06)`).
- **Ikke udført automatisk:** Live multi-device rollout-test er stadig ikke kørt fra heartbeat,
  da den ændrer update-state for rigtige enheder. Bør testes kontrolleret med 2+ test-enheder.

### Handover 2026-07-05 04:1x — fra Claude (periodisk tjek): docs-sync — statusfelter var kommet bagud efter Codex' commit/deploy

- **Kontekst:** Periodisk 20-minutters-tjek. Læste HANDOVER_LOG-halen — seneste entry er Codex'
  egen ("HLTH-008 regression + H-05 tests + H-06 README udført"), som bekræfter at flush-fixet
  (`1e3c3321`) og README-oprydningen (`9dda9923`) BEGGE er committet, pushet, og at headend er
  genstartet med `/api/health` 200 OK, samt at 13/13 tests bestod i Codex' eget venv. `git status
  --short` viste kun den kendte untracked `claude_proxy.py` — dvs. intet uncommittet fra tidligere
  runder længere; alt er nu i git. Bekræftede selv i git-historikken (`git show 1e3c3321 --stat`,
  `git log -5 --oneline`) at commits `1e3c3321`, `9dda9923` og `a1c6cfbf` (docs-only, tilføjede kun
  selve HANDOVER_LOG-teksten) rent faktisk er på nuværende `HEAD`, og at `db.flush()` er til stede
  i den committede `headend/main.py`.
- **Fund:** `a1c6cfbf` tilføjede kun Codex' HANDOVER_LOG-tekst, men opdaterede IKKE de øvrige
  statusdokumenter — `GO_LIVE_CHECKLIST_v10.md` (H-05, H-06, §K), `RISK_ASSESSMENT_v10.md` (§11
  P1.4, R06, §12), `SYSTEM_HEALTH_REGISTER.md` (HLTH-008, HLTH-015) og
  `KRAVREGISTER_og_STATUS_v10.md` (UPD-012) sagde alle stadig "IKKE committet/deployet endnu" —
  dokumenterne var dermed inkonsistente med den faktiske, allerede bekræftede git/deploy-tilstand.
  Fandt desuden at HLTH-015 ("README er stadig Vite-template") stadig stod som "Åben" i
  `SYSTEM_HEALTH_REGISTER.md`, selvom H-06-rettelsen (samme sag) er committet.
- **Rettet (kun tekst, ingen kode rørt):**
  1. `GO_LIVE_CHECKLIST_v10.md` — H-05 og H-06 opdateret fra "IKKE committet endnu" til
     committet/verificeret status (🟢/✅); §K "Per-target update status" nedjusteret fra P0/🟠
     til P1/🟡 med commit-hash og deploy-bekræftelse.
  2. `RISK_ASSESSMENT_v10.md` — §11 P1.4 og R06 opdateret til at reflektere at flush-rettelsen er
     committet/deployet; residualrisiko for R06 nedjusteret fra 🟠 8 til 🟡 6 (ikke 🟢, da live
     multi-device-test stadig udestår); ny §12-historik-linje tilføjet.
  3. `SYSTEM_HEALTH_REGISTER.md` — HLTH-008 nedjusteret fra P0/🟠 til P1/🟡 med commit/deploy-info;
     HLTH-015 (README) lukket til ✅ med henvisning til `9dda9923`.
  4. `KRAVREGISTER_og_STATUS_v10.md` — UPD-012 nedjusteret fra 🟠 til 🟡 med samme begrundelse.
  Alle fire filer holder fast i at ÉN ting stadig er reelt åben og ikke må lukkes helt: en faktisk
  live multi-device-rollout-test (2+ enheder, `scope=site`) der bekræfter at update rent faktisk
  flipper til "Deployet"/"Rullet tilbage" i produktion — dette er bevidst IKKE nedskaleret til
  🟢 noget sted, kun fra P0 til P1, da kun kode+unit/contract-tests er verificeret, ikke
  live-adfærd.
- **Verifikation:** Ren dokumentationsændring — ingen `.py`/`.ts`-filer rørt, så ingen
  `py_compile`/`pytest`/`tsc` relevant. Læste hver ændret sektion igennem efter redigering og
  krydstjekkede tal/commit-hashes mod `git log`/`git show` (ikke gættet). Kontrollerede at
  markdown-tabellernes kolonneantal er uændret (ingen tabelstruktur brudt af `|`-tegn i den nye
  tekst).
- **Bemærkning (ikke handlingskrævende):** `git diff --stat` i denne mappe gav en advarsel
  ("unable to unlink .git/index.lock: Operation not permitted") — `.git/index.lock` findes
  (0 byte), men ingen git-proces kørte (`ps aux | grep git` var tom). Rørte ikke selv `.git/`
  internals (uden for scope, og jeg har ingen Mac Mini-adgang til at bekræfte at det er trygt).
  Codex/Peter bør lige tjekke ved lejlighed at intet reelt git-lock blokerer næste commit — hvis
  `git status`/`git add` fejler med en lock-fejl, er det formentlig bare en stale lock fra denne
  sandkasses læse-only diff-forsøg og kan fjernes med `rm -f .git/index.lock` når ingen git-proces
  kører.
- **Ikke gjort — bevidst:** Ingen kodeændringer denne runde (ren docs-sync). Ingen commit/push
  (samme konvention som hidtil — Peter/Codex committer selv nedenfor).
- **Codex/Peter: kør venligst når I har et vindue** (ren docs-sync, ingen kodeadfærd ændret):
  ```bash
  cd /Users/peter/projects/timelapse-pro

  ps aux | grep -i git | grep -v grep
  # (hvis tomt, og kun hvis git faktisk fejler med en lock-fejl) rm -f .git/index.lock

  git add Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/RISK_ASSESSMENT_v10.md \
          Dokumentation/SYSTEM_HEALTH_REGISTER.md Dokumentation/KRAVREGISTER_og_STATUS_v10.md \
          Dokumentation/HANDOVER_LOG.md
  git commit -m "docs: sync HLTH-008/H-05/H-06/UPD-012 status with already-deployed flush fix + README"
  git push
  ```
- **Filer rørt:** `Dokumentation/GO_LIVE_CHECKLIST_v10.md`, `Dokumentation/RISK_ASSESSMENT_v10.md`,
  `Dokumentation/SYSTEM_HEALTH_REGISTER.md`, `Dokumentation/KRAVREGISTER_og_STATUS_v10.md`.
- **Går videre til:** næste periodiske runde bekræfter om denne docs-sync-commit er
  committet/pushet; ellers ser den på den fortsat udestående live multi-device-rollout-test
  (kræver Peter/Codex, live-adgang), device-decommission-gap'et fra en tidligere runde (kræver
  Peters produktbeslutning), H-04 (`deploy/launchd/...plist` ikke-secret version, 🟠 Mangler),
  eller Peters §6-beslutning (CA/mTLS) / R17-smoketesten hvis en af dem er besvaret i mellemtiden.

### Handover 2026-07-05 04:2x — fra Claude (periodisk tjek): docs-sync-commit bekræftet + H-04 var reelt allerede løst (bare ikke markeret)

- **Kontekst:** Periodisk 20-minutters-tjek. Læste HANDOVER_LOG-halen — seneste entry er min
  egen forrige runde (#11, docs-sync). `git log -3` og `git show c7d409cb --stat` bekræftede at
  Peter/Codex har committet den foreslåede docs-sync præcis som foreslået: `c7d409cb`
  ("docs: sync HLTH-008/H-05/H-06/UPD-012 status with already-deployed flush fix + README"),
  2026-07-05 04:15:55 — kun ca. 10 minutter før denne runde. `git status --short` viste kun den
  kendte untracked `claude_proxy.py`. Ingen ny Codex-entry i mellemtiden.
- **Fund:** Gennemgik §11 i RISK_ASSESSMENT_v10.md og §H/§J i GO_LIVE_CHECKLIST_v10.md for
  resterende åbne P0/P1-punkter. De fleste kræver enten live-adgang (multi-device-rollout-test,
  R17-smoketest) eller en produktbeslutning fra Peter (device-decommission-gap, §6 CA/mTLS-valg
  Cloudflare Access vs. ende-til-ende). Valgte i stedet **H-04** (`🟠 Mangler`) som et uafhængigt,
  afgrænset fund: undersøgte de to plist-filer i repoet —
  `deploy/launchd/dk.froekjaer.timelapse-headend.plist` (rod, bruger-LaunchAgent-stil, med
  `DATABASE_URL` og `TIMELAPSE_GPG_KEY` inline i klartekst) og
  `deploy/launchd/macos/dk.froekjaer.timelapse-headend.plist` (system-LaunchDaemon-stil, INGEN
  secrets inline — kun en pointer `TIMELAPSE_HEADEND_ENV_FILE=/etc/timelapse/headend.env`, som
  læses af `deploy/macos/timelapse-headend-start.sh`). `git log` viste at BEGGE blev tilføjet i
  samme commit `d7a952db` (2026-07-03, Codex' Mac Mini-hardening/kernel-panic-arbejde — se
  HANDOVER_LOG 2026-07-03 10:15-entry). `SERVICES_OG_DRIFT_kilde_til_sandhed.md` bekræftede at
  den LIVE, kanoniske service er system-LaunchDaemon-versionen (`system/dk.froekjaer.timelapse-
  headend`), ikke rod-plisten. Konklusion: H-04 ("opdateret ikke-secret version") blev reelt
  udført af Codex allerede 2026-07-03 — checklisten var bare aldrig opdateret til at afspejle
  det, og er dermed endnu et eksempel på samme type efterslæb som tidligere docs-sync-runder
  (H-05/H-06/HLTH-008 osv.).
- **Rettet (kun tekst, ingen kode/plist-filer rørt):**
  1. `GO_LIVE_CHECKLIST_v10.md` H-04 opdateret fra `🟠 Mangler` til `🟢 Løst` med commit-hash,
     forklaring af hvilken fil er den kanoniske, og en eksplicit note om at rod-plisten med
     inline secrets er en efterladt, ikke-brugt artefakt fra før 2026-07-03-migrationen (ikke
     slettet denne runde — filsletning/-oprydning er en bevidst udeladt handling, se nedenfor).
  2. `RISK_ASSESSMENT_v10.md` §12 — ny historik-linje der noterer fundet og eksplicit adskiller
     det fra VPEN-2026-003 (§5.2, P2): VPEN-2026-003 handler om plaintext `JWT_SECRET`/
     `BREAK_GLASS_ENC_KEY` i selve `/etc/timelapse/headend.env` PÅ DISK (kræver Keychain-
     migration) — det er en reelt fortsat åben risiko og IKKE det samme som H-04s snævrere
     Git-hygiejne-scope (at det Git-tjekkede plist-*template* ikke indeholder secrets). Ingen af
     de to punkter er lukket forkert af den anden.
- **Verifikation:** Læste begge plist-filer og `timelapse-headend-start.sh` i deres helhed før
  konklusion (ikke gættet ud fra filnavne alene). Krydstjekkede med `git log`/`git show --stat`
  at `d7a952db` faktisk indeholder begge plist-tilføjelser og at commit-datoen (2026-07-03)
  stemmer med HANDOVER_LOG-entryen fra samme dato. Ren dokumentationsændring — ingen kode/plist
  rørt, så ingen `py_compile`/`pytest` relevant. Kontrollerede efter redigering at
  tabelstrukturen i `GO_LIVE_CHECKLIST_v10.md` §H stadig har korrekt kolonneantal (ingen løse
  `|`-tegn i den nye tekst).
- **IKKE gjort — bevidst:** Ingen sletning/omdøbning af den forældede rod-plist
  (`deploy/launchd/dk.froekjaer.timelapse-headend.plist`) — selvom den er ubrugt, er
  fil-oprydning i `deploy/` uden for scope for en periodisk docs-tjek-runde uden mulighed for at
  få fanget en fejl, og kunne teoretisk forveksles med en fil nogen stadig har en lokal
  reference til. Efterlader det som forslag til Peter/Codex nedenfor i stedet. Ingen commit/push
  (samme konvention — Peter/Codex committer selv).
- **Codex/Peter: kør venligst når I har et vindue** (ren docs-sync, ingen kodeadfærd ændret):
  ```bash
  cd /Users/peter/projects/timelapse-pro
  git add Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/RISK_ASSESSMENT_v10.md \
          Dokumentation/HANDOVER_LOG.md
  git commit -m "docs: mark H-04 (secret-free headend plist) as resolved since 2026-07-03 (d7a952db)"
  git push
  ```
  **Valgfrit oprydningsforslag** (ikke hastende, kun hvis I er enige i at rod-plisten er dødvægt):
  ```bash
  git rm deploy/launchd/dk.froekjaer.timelapse-headend.plist
  git commit -m "chore: remove superseded user-LaunchAgent headend plist (replaced by system LaunchDaemon in d7a952db)"
  git push
  ```
- **Filer rørt:** `Dokumentation/GO_LIVE_CHECKLIST_v10.md`, `Dokumentation/RISK_ASSESSMENT_v10.md`.
- **Går videre til:** næste periodiske runde bekræfter om denne H-04-docs-sync (og evt. det
  valgfrie plist-oprydningsforslag) er committet/pushet; ellers ser den på den fortsat
  udestående live multi-device-rollout-test, device-decommission-gap'et, Peters §6-beslutning
  (CA/mTLS) / R17-smoketesten, eller K-linjen "OS offline-artifact update E2E" / "Change ticket
  med artifact/SBOM/rollback" i §K (begge stadig "Åben"/"Delvist" og uundersøgt af Claude indtil
  videre).

### Handover 2026-07-05 04:4x — fra Claude (periodisk tjek): H-02 ESLint-gate funktionelt verificeret i sandbox (begge veje)

- **Kontekst:** Periodisk 20-minutters-tjek. `git log -3` bekræftede at forrige rundes H-04-
  docs-sync er committet (`775031b1`, af Peter/Codex). `git status --short` viste kun den kendte
  untracked `claude_proxy.py`. Ingen ny Codex-entry siden sidst.
- **Fund/valg:** Gennemgik §11 og §J/§K igen. De fleste resterende P0/P1-punkter kræver enten
  live-adgang (multi-device-rollout-test, node-agent, R14-hardware) eller en produktbeslutning
  (device-decommission, §6 CA/mTLS). H-02 (ESLint ratchet-gate) står med "Resterer: bekræfte
  grønt ESLint-gate-step i en faktisk GitHub Actions-kørsel" — jeg har ikke GitHub-adgang
  (`curl https://api.github.com/repos/froekjaer/timelapse-pro/actions/runs` → `404`, privat
  repo, ingen token i sandboxen), så selve CI-kørslen kan jeg fortsat ikke bekræfte. Jeg kunne
  til gengæld verificere gate-*mekanismen* selv, da `timelapse-ui/node_modules` allerede findes
  i sandboxen — noget ingen tidligere runde har gjort.
- **Udført (kun test/verifikation, ingen kode/config rørt):**
  1. Kørte `npm run lint:gate` i `timelapse-ui/` med den committede baseline (222): output
     `204 fejl, 18 advarsler (222 i alt)` → `✅ Uændret — ingen nye ESLint-problemer`, exit 0.
     Bekræfter at det faktiske, aktuelle ESLint-problemtal i koden er PRÆCIS det tal der står i
     `GO_LIVE_CHECKLIST_v10.md` H-02 og `.eslint-baseline.json` — ingen drift siden 2026-07-05.
  2. For at bekræfte at gaten reelt kan FEJLE (ikke kun altid returnere 0): lavede en midlertidig
     lokal kopi af `.eslint-baseline.json` med `total` sænket til 100, kørte scriptet direkte
     (`node scripts/eslint-gate.mjs`) → korrekt `❌ ESLint-gate fejlede: 222 problemer > baseline
     100`, exit code 1. Gendannede øjeblikkeligt den oprindelige fil fra en backup-kopi
     (`cp /tmp/.eslint-baseline.json.bak .eslint-baseline.json`) og bekræftede med
     `git status --short`/`git diff --stat` at filen er byte-for-byte uændret (tom diff) — ingen
     spor efterladt i working tree.
  3. Læste `.github/workflows/ci.yml` igennem: `ui-check`-jobbet har `working-directory:
     timelapse-ui`, kører `npm ci` → `npx tsc --noEmit` → `npm run lint:gate` → `npm run build` i
     den rækkefølge — wiringen matcher det scriptet forventer (relative stier via `__dirname`),
     ingen mismatch fundet.
- **Konklusion:** Selve H-02-mekanismen (script + baseline + CI-wiring) er nu verificeret
  fungerende i begge retninger (pass ved uændret/forbedret tal, fail ved forværring), og det
  dokumenterede baseline-tal er bekræftet korrekt mod den faktiske kodebase. Det eneste der
  reelt resterer for H-02 er at se en RIGTIG grøn kørsel i GitHub Actions selv (kræver GH-adgang,
  som kun Peter/Codex har) — ingen ændring af status i `GO_LIVE_CHECKLIST_v10.md`, da denne
  runde ikke tilføjer ny information om selve GH Actions-kørslen, kun om at koden bag den er
  korrekt. Ingen dokumentopdatering skrevet denne runde for at undgå at overdrive hvad der reelt
  er bekræftet.
- **Verifikation:** Ingen `.py`/`.ts`/config-filer ændret varigt (baseline-testen blev udført og
  fuldt reverteret inden for samme kommando-sekvens, verificeret med tom `git diff`). Ingen
  commit/push (samme konvention).
- **Går videre til:** næste periodiske runde kan enten spørge Peter/Codex direkte om GH Actions-
  status for H-02/H-05 (den eneste resterende blocker for begge), eller kigge på den fortsat
  udestående live multi-device-rollout-test, device-decommission-gap'et, Peters §6-beslutning
  (CA/mTLS) / R17-smoketesten, eller §K-linjerne "OS offline-artifact update E2E" og "Change
  ticket med artifact/SBOM/rollback" (begge stadig uundersøgt af Claude).

### Handover 2026-07-05 05:1x — fra Claude (periodisk tjek): lukkede et reelt GDPR-inkonsistens-hul i Gemini/Vertex batch-region-tjek (R12/DPIA §4)

- **Kontekst:** Periodisk 20-minutters-tjek. `git log -3` bekræftede at forrige rundes H-04-
  docs-sync (`775031b1`) stadig er seneste commit — ingen ny Codex-entry siden sidst.
  `git status --short` viste kun den kendte untracked `claude_proxy.py`. Gennemgik §11 igen;
  de fleste P0/P1-punkter kræver stadig enten live-adgang eller en produktbeslutning. Valgte i
  stedet at følge op på DPIA-dokumentets (`DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` §4)
  eksplicitte anbefaling: "Bekræft Gemini/Vertex AI's faktiske region-indstilling som
  allerførste skridt" — en tidligere periodisk runde havde flagget den som ubesvaret.
- **Fund:** Kunne ikke bekræfte selve den LIVE produktionsværdi (ingen adgang til Mac Mini'ens
  miljøvariabler), men fandt ved kodegennemgang en reel, selvstændig inkonsistens: Vertex-region
  defaulter til `europe-west1` i `GeminiVisionService.__init__` (`headend/ai/gemini_service.py`),
  og `POST /api/admin/ai-batch/...`-endepunktet i `headend/main.py` (bag "Kør AI-batch nu" i
  UI'et) havde allerede et tjek der stopper batch-jobbet, hvis det (valgfrit) konfigurerede
  `gemini_gcs_bucket_region` ikke matcher Vertex-regionen — men `headend/ai/ai_batch_submit.py`
  (CLI-scriptet til manuel bulk re-tag, som kører direkte på Mac Mini'en og udfører PRÆCIS samme
  Vertex-batch-upload til samme GCS-bucket) havde INGEN tilsvarende kontrol. En operatør der
  brugte CLI-scriptet i stedet for UI-knappen (fx til en stor bagudrettet re-tag-kørsel, som
  scriptets egen docstring lægger op til) kunne dermed have sendt et helt batch-job til et
  forkert-region GCS-bucket uden nogen advarsel — samme GDPR-risiko som UI-stien allerede var
  beskyttet imod.
- **Rettet (kode + tests, ikke kun docs denne gang):**
  1. Udtrak den delte logik til `validate_batch_bucket_region(vertex_region, bucket_region)` i
     `headend/ai/gemini_service.py` — samme adfærd/fejltekst som det oprindelige tjek, nu med
     udførlig docstring om hvorfor (no-op hvis `bucket_region` er tom — bevidst ikke fail-closed,
     se `RISK_ASSESSMENT_v10.md` R12).
  2. `headend/main.py`: erstattede det inline tjek med et kald til den delte funktion (adfærd
     uændret — samme HTTPException 400, samme dansk fejltekst).
  3. `headend/ai/ai_batch_submit.py`: tilføjede det manglende tjek i `build_gemini()` + fangede
     `ValueError` pænt i `main()` (udskriver `❌ <fejl>` og stopper, ligesom scriptets øvrige
     fejlhåndtering — ingen uhåndteret traceback).
  4. Ny testfil `headend/tests/test_gemini_region_guard.py` — 6 kontrakt-tests: matchende
     region-familie passerer, mismatch (begge retninger) rejser `ValueError`, tom
     bucket-/vertex-region er no-op (ikke fail-closed), case/whitespace-ufølsomhed.
- **Dokumentation opdateret (samme runde):** `RISK_ASSESSMENT_v10.md` R12 (ny
  TILFØJELSE 2026-07-05), `GO_LIVE_CHECKLIST_v10.md` G-04, og
  `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` §4 — alle tre gjort eksplicit om at kun den
  KODE-mæssige konsistens mellem UI-API og CLI er lukket denne runde, IKKE selve den
  underliggende anbefaling (bekræfte den faktiske produktions-region), som fortsat kræver
  live-adgang og er efterladt åben.
- **Verifikation:** Oprettede en frisk, midlertidig venv i sandboxen (repoets egen
  `headend/venv` er macOS-kompileret og kan ikke køre i denne Linux-sandbox — `Exec format
  error`), installerede `httpx` + samme pinnede test-deps som H-05-testene bruger
  (`fastapi==0.136.1`, `sqlalchemy==2.0.49`, `python-jose[cryptography]==3.5.0`, `bcrypt==5.0.0`,
  `passlib==1.7.4`, `slowapi==0.1.9`, `python-multipart==0.0.27`, `python-dotenv`, `pytest`).
  Kørte `python3 -m py_compile` på alle fire rørte `.py`-filer (ren) og HELE test-suiten i
  `headend/tests/` — **19/19 bestået** (13 eksisterende H-05-tests uændrede/upåvirkede + 6 nye).
  Ingen live-kald til Google/Vertex/GCS foretaget noget sted i denne verifikation (ren
  funktionstest af region-streng-sammenligningen, ingen netværksadgang).
- **Ikke gjort — bevidst:** Ingen commit/push (samme konvention — Peter/Codex committer selv
  nedenfor). Ingen tilføjelse af en egentlig EU-region-allowliste (fx eksplicit liste over
  `europe-west1/west2/west3/...`) — det nuværende tjek verificerer kun at bucket- og
  Vertex-region er i samme "familie" (matcher hinanden), ikke at de faktisk ER i EU; at stramme
  dette yderligere er en selvstændig, lidt større ændring og efterlades som forslag nedenfor,
  da den kunne ændre adfærd for en korrekt konfigureret, ikke-EU testopsætning uden forudgående
  aftale med Peter.
- **Codex/Peter: kør venligst når I har et vindue** (kode + tests, ikke kun docs — læs
  diff'en igennem inden merge, da dette rører `headend/main.py`s AI-batch-endepunkt):
  ```bash
  cd /Users/peter/projects/timelapse-pro
  git diff headend/main.py headend/ai/gemini_service.py headend/ai/ai_batch_submit.py
  git add headend/ai/gemini_service.py headend/ai/ai_batch_submit.py headend/main.py \
          headend/tests/test_gemini_region_guard.py \
          Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/GO_LIVE_CHECKLIST_v10.md \
          Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md Dokumentation/HANDOVER_LOG.md
  git commit -m "fix: enforce GDPR bucket-region guard in ai_batch_submit.py CLI (was API-only)"
  git push
  # Efter deploy: genstart headend som normalt og bekræft /api/health 200 (ren refaktorering
  # af main.py's eksisterende tjek, men rører kritisk AI-batch-kode — værd at dobbelttjekke).
  ```
  **Separat, ikke-hastende opfølgning (kræver Peters beslutning, ikke kode i dag):** confirm
  den faktiske `GOOGLE_CLOUD_LOCATION`/`gemini_gcs_bucket_region`-værdi i produktion rent
  faktisk er en EU-region (`grep -i GOOGLE_CLOUD_LOCATION /etc/timelapse/headend.env` eller
  tilsvarende på Mac Mini'en) — dette er den del af DPIA §4-anbefalingen som stadig kræver
  live-adgang og ikke er dækket af denne rundes kodeændring.
- **Filer rørt:** `headend/ai/gemini_service.py`, `headend/ai/ai_batch_submit.py`,
  `headend/main.py`, `headend/tests/test_gemini_region_guard.py` (ny),
  `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`,
  `Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`.
- **Går videre til:** næste periodiske runde bekræfter om denne commit er committet/pushet og
  om headend blev genstartet/health-tjekket efter deploy; ellers kan den se på den fortsat
  udestående live multi-device-rollout-test, device-decommission-gap'et, Peters §6-beslutning
  (CA/mTLS) / R17-smoketesten, §K's "OS offline-artifact update E2E"/"Change ticket"-linjer,
  eller den separate opfølgning ovenfor om at bekræfte den faktiske Gemini/Vertex-region i
  produktion.

### Handover 2026-07-05 05:3x — fra Claude (periodisk tjek): change ticket-dokument gensignes nu korrekt ved sen artifact-binding (SBOM-integritetshul lukket)

- **Kontekst:** Periodisk 20-minutters-tjek. `git log -3` bekræftede at Codex' commit `225f82f2`
  (dokumentation om deployet Gemini/Vertex-guard) stadig er seneste commit. `git status --short`
  viste kun den kendte untracked `claude_proxy.py`. Ingen ny Codex-entry siden sidst. Gennemgik
  §11 og §J/§K igen — valgte at følge op på §K-linjen "Change ticket med artifact/SBOM/rollback |
  Delvist", som ingen tidligere runde havde undersøgt konkret.
- **Fund:** `ChangeTicket.sbom_ref`/`.test_evidence_ref` blev gemt i DB og eksponeret via
  ticket-API'et (`_ticket_to_dict`), men optrådte ALDRIG i selve det signerede dokument
  (`machine_json`/`human_readable_md`) — hverken ved oprettelse. Værre: når et artifact blev
  bundet til en ALLEREDE OPRETTET ticket via `bind_artifact_to_update` (den almindelige rækkefølge
  — ticket oprettes typisk før artifactet findes), blev `ticket.sbom_ref`/`.artifact_id` opdateret
  direkte på DB-rækken UDEN at dokumentet blev gensigneret. Det betyder `content_sha256`/
  `signature` (den kryptografiske binding et signeret change ticket skal give troværdighed fra)
  reelt kunne stå og pege på et FORÆLDET dokument, mens de "friske" DB-kolonner viste noget andet
  — et reelt integritetshul i netop den kontrol §K efterspørger.
- **Rettet (kode + tests):**
  1. Udtrak dokumentbygningen (machine_json + human_readable_md + hash + signatur) fra
     `_build_change_ticket` til en ny delt funktion `_render_change_ticket_document()` i
     `headend/main.py`, som nu også inkluderer `sbom_ref` og `test_evidence_ref` i både
     maskin- og menneskelæsbar form.
  2. `bind_artifact_to_update()`s gren for "ticket findes allerede" kalder nu samme funktion og
     genskriver `human_readable_md`/`machine_json`/`content_sha256`/`signature`/`signed_at` —
     ticket_id, oprindelig `created_by`/`created_at` bevares uændret (kun dokumentets indhold og
     signaturen opdateres, ikke hvem der oprindeligt oprettede ticketen).
  3. Ny testfil `headend/tests/test_change_ticket_sbom.py` — 4 kontrakt-tests: SBOM med i
     dokumentet ved oprettelse med kendt artifact, korrekt "intet artifact endnu"-tekst uden
     artifact, gensignering (ændret hash/signatur) ved sen artifact-binding, og at oprindelig
     creator/ticket_id IKKE ændres af re-signeringen.
- **Dokumentation opdateret (samme runde):** `GO_LIVE_CHECKLIST_v10.md` §K — linjen er fortsat
  "Delvist" (bevidst, se nedenfor) med en ny TILFØJELSE 2026-07-05 der forklarer præcis hvad der
  er lukket og hvad der stadig mangler.
- **Verifikation:** Genbrugte samme mønster som tidligere runder (repoets `headend/venv` er
  macOS-kompileret, kører ikke i denne Linux-sandbox). Frisk venv (`/tmp/hvenv2`) med
  `fastapi==0.136.1`, `sqlalchemy==2.0.49`, `python-jose[cryptography]==3.5.0`, `bcrypt==5.0.0`,
  `passlib==1.7.4`, `slowapi==0.1.9`, `python-multipart==0.0.27`, `python-dotenv`, `pytest`,
  `httpx`. `python3 -m py_compile main.py database.py` ren. Hele test-suiten i `headend/tests/`:
  **23/23 bestået** (19 eksisterende, uændrede + 4 nye). Ingen live-kald foretaget noget sted.
- **Ikke gjort — bevidst:** Status er IKKE ændret til "Løst"/✅ — der findes fortsat ingen kode
  eller politik der KRÆVER et SBOM/test-evidens-felt før en ticket kan godkendes (feltet kan
  stadig stå tomt uden fejl), og selve SBOM-indholdets dækning/kvalitet er ikke vurderet i denne
  runde — kun at det, der rent faktisk ER registreret, nu vises korrekt og forbliver kryptografisk
  bundet til dokumentet. Ingen commit/push (samme konvention — Peter/Codex committer selv).
- **Codex/Peter: kør venligst når I har et vindue:**
  ```bash
  cd /Users/peter/projects/timelapse-pro
  git diff headend/main.py
  git add headend/main.py headend/tests/test_change_ticket_sbom.py \
          Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "fix: re-sign change ticket document (incl. SBOM ref) on late artifact binding"
  git push
  # Ingen live-genstart nødvendig for selve denne ændring alene (kun rørt ved binding/oprettelse
  # af change tickets), men indgår i næste normale headend-deploy som vanligt.
  ```
- **Filer rørt:** `headend/main.py`, `headend/tests/test_change_ticket_sbom.py` (ny),
  `Dokumentation/GO_LIVE_CHECKLIST_v10.md`.
- **Går videre til:** næste periodiske runde bekræfter om denne commit er committet/pushet;
  ellers kan den se på den fortsat udestående live multi-device-rollout-test,
  device-decommission-gap'et, Peters §6-beslutning (CA/mTLS) / R17-smoketesten, §K's "OS
  offline-artifact update E2E"/"Stale/legacy credentials migreret"-linjer, eller den separate
  opfølgning fra sidste runde om at bekræfte den faktiske Gemini/Vertex-region i produktion.

### Handover 2026-07-05 (nat) - Codex: Gemini/Vertex bucket-region guard committet og deploy-tjekket
- **Udført:** Claude's Gemini/GDPR batch-region fix er gennemgået, testet, committet og pushet
  på `claude/capture-camera-location-2026-07-03` som `78a4ab93`:
  `fix: enforce GDPR bucket-region guard in ai_batch_submit.py CLI (was API-only)`.
- **Verifikation:** `python3 -m py_compile` på de rørte Python-filer var ren. Efter installation
  af manglende `httpx` i den midlertidige `/tmp/tlp-hvenv` kørte Codex:
  `/tmp/tlp-hvenv/bin/python -m pytest tests/test_report_update_rollup.py tests/test_update_lifecycle.py tests/test_gemini_region_guard.py -v`
  med **19 passed**.
- **Drift:** Headend blev genstartet med `launchctl kickstart -k system/dk.froekjaer.timelapse-headend`;
  `https://timelapse.froekjaer.dk/api/health` svarede **HTTP 200 OK** kl. `2026-07-05T03:18:48Z`.
- **Ikke udført automatisk:** Den faktiske produktionsværdi for
  `GOOGLE_CLOUD_LOCATION`/`gemini_gcs_bucket_region` er ikke verificeret i live env i denne
  runde; det er stadig en separat konfigurations-/DPIA-opfølgning.

### Handover 2026-07-05 (nat) - Codex: change ticket SBOM re-sign commit udført
- **Udført:** Claude's change-ticket/SBOM-integritetsfix er gennemgået, testet, committet og
  pushet på `claude/capture-camera-location-2026-07-03` som `ff0797c9`:
  `fix: re-sign change ticket document (incl. SBOM ref) on late artifact binding`.
- **Verifikation:** `python3 -m py_compile headend/main.py headend/database.py
  headend/tests/test_change_ticket_sbom.py` var ren. Codex kørte:
  `/tmp/tlp-hvenv/bin/python -m pytest tests/test_report_update_rollup.py tests/test_update_lifecycle.py tests/test_gemini_region_guard.py tests/test_change_ticket_sbom.py -v`
  med **23 passed**.
- **Drift:** Ingen live-genstart udført i denne runde, da ændringen kun rører oprettelse/binding
  af change tickets og Claude eksplicit noterede at den kan indgå i næste normale headend-deploy.

### Handover 2026-07-05 (periodisk tjek #16) — fra Claude: formaliserede device-decommission-gap i RISK_ASSESSMENT/GO_LIVE (ren dokumentation, ingen kode)

- **Kontekst:** Periodisk 20-minutters-tjek. `git log -3` bekræftede `4b454b85` (docs: mark
  change ticket SBOM re-sign fix committed) stadig er seneste commit — begge Claude-fixes fra de
  seneste runder (Gemini/Vertex-region-guard, change ticket SBOM re-sign) er nu bekræftet
  committet, pushet OG deployet af Codex (se de to "nat"-entries lige ovenfor: `78a4ab93`+
  headend genstartet/health 200 OK kl. 03:18:48Z, samt `ff0797c9`). `git status --short` viste
  kun den kendte untracked `claude_proxy.py` (uændret siden tidligere runder — ikke rørt, egen
  fil, ikke en del af nogen Claude-arbejdsgang i denne runde). Ingen ny Codex-entry med et
  spørgsmål til Claude siden sidst.
- **Fund:** Gennemgik §11 (RISK_ASSESSMENT) og §J/§K (GO_LIVE_CHECKLIST) igen for stadig-åbne
  P0/P1-punkter. De fleste kræver nu enten live-adgang (multi-device-rollout-test, OS offline
  E2E, bekræftelse af faktisk Gemini/Vertex-produktionsregion) eller en produktbeslutning af
  Peter (device-decommission-gap, §6 CA/mTLS Cloudflare-valg, stale credential
  `TL-DCA63234D813`). Bemærkede at device-decommission-gap'et — fundet og testdokumenteret
  allerede i periodisk tjek #9 (`headend/tests/test_update_lifecycle.py::test_device_removed_from_cmdb_mid_rollout_does_not_prematurely_flip`,
  committet i `1e3c3321`) — var blevet nævnt som "næste skridt" i mindst 8 efterfølgende
  handover-entries, men ALDRIG faktisk tilføjet til selve `RISK_ASSESSMENT_v10.md` (R06) eller
  `GO_LIVE_CHECKLIST_v10.md` (§K) — kun til denne log. Et reelt, om end lille, dokumentationshul:
  nogen der kun læser risikodokumentet (ikke hele HANDOVER_LOG) ville ikke vide gap'et findes.
- **Rettet (kun dokumentation, ingen kode rørt):**
  1. `RISK_ASSESSMENT_v10.md` R06 — ny afsnit der beskriver gap'et (device slettet fra CMDB midt
     i en ikke-terminal rollout-status tælles ikke længere med i `_resolve_update_targets()`s
     `total`, så rollup'en kan flippe til "deployed" selvom det fjernede device reelt aldrig
     afsluttede), henviser til den eksisterende, committede kontrakttest, og lister de tre
     løsningsmuligheder Peter skal vælge imellem (permanent blokering / nuværende adfærd /
     "delvist bekræftet"-markering) — ingen af de tre implementeret endnu, bevidst, kræver hans
     beslutning først (jf. tidligere runders "Ikke gjort — bevidst"). Residualrisiko-noten
     opdateret til også at nævne dette gap som en betingelse for 🟢.
  2. `GO_LIVE_CHECKLIST_v10.md` §K — "Per-target update status"-rækken udvidet med samme
     information i kort form, med henvisning til R06 for detaljerne.
  3. §12 dokumenthistorik-tabel i RISK_ASSESSMENT_v10.md fik en ny linje for denne runde.
- **Verifikation:** Ren dokumentationsændring — ingen `.py`-filer rørt, så ingen
  `py_compile`/pytest nødvendig denne gang. Kørte `git diff --stat` bagefter: kun de to
  `.md`-filer ændret (21 linjer i RISK_ASSESSMENT, 1 linje i GO_LIVE_CHECKLIST), ingen
  utilsigtede ændringer andre steder. Læste begge ændrede afsnit igennem én gang til efter
  redigering for at bekræfte at de nye tekster ikke modsiger den eksisterende "Åbent"/
  "Residualrisiko"-formulering.
- **Ikke gjort — bevidst:** Ingen kodeændring til selve decommission-adfærden (kræver Peters
  valg mellem de tre muligheder, se ovenfor — antages ikke). Ingen commit/push (samme konvention
  — Peter/Codex committer selv, se nedenfor).
- **Codex/Peter: kør venligst når I har et vindue (ren dokumentation, ufarlig at merge når som
  helst):**
  ```bash
  cd /Users/peter/projects/timelapse-pro
  git diff Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/GO_LIVE_CHECKLIST_v10.md
  git add Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/GO_LIVE_CHECKLIST_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "docs: formalize device-decommission-mid-rollout gap in R06/GO_LIVE §K"
  git push
  # Ingen deploy/genstart nødvendig — ren dokumentation.
  ```
  **Kræver Peters beslutning (ikke hastende, men bør besvares før device-udskiftning bliver
  hyppig i drift):** vælg én af de tre adfærdsmuligheder for device-decommission midt i en
  rollout (se R06 i RISK_ASSESSMENT_v10.md) — så kan Claude/Codex implementere den i en
  efterfølgende runde.
- **Filer rørt:** `Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/GO_LIVE_CHECKLIST_v10.md`.
- **Går videre til:** næste periodiske runde bekræfter om denne docs-commit samt Peters
  decommission-beslutning er kommet igennem; ellers samme liste som hidtil — live
  multi-device-rollout-test, Peters §6-beslutning (CA/mTLS), R17-smoketesten, §K's "OS
  offline-artifact update E2E", eller at bekræfte den faktiske Gemini/Vertex-produktionsregion.

### Handover 2026-07-05 (periodisk tjek #17) — fra Claude: VPEN-2026-008 (NY) — AI Ops' SAST-tal ("73 signaler") var upålideligt, scanner-fejl fundet og rettet

- **Kontekst:** Periodisk 20-minutters-tjek. `git log -3` bekræftede `73c1d692` (docs:
  formalize device-decommission-mid-rollout gap) stadig er seneste commit. `git status --short`
  viste kun den kendte untracked `claude_proxy.py` (uændret, ikke rørt). Ingen ny Codex-entry med
  spørgsmål til Claude siden sidst. Gennemgik §11 P2-listen for et punkt ingen tidligere runde
  havde rørt — valgte "SAST backlog triage (73 signaler)" (VPEN-006), som havde stået uændret
  siden pentesten i maj 2026.
- **Fund:** `_aiops_static_scan()` i `headend/main.py` — funktionen bag AI Ops-cockpittets
  "73 SAST-signaler" — er en simpel regex/substring-scanner over hele repoet. Den sprang kun
  stier over ved et EKSAKT match på en hel path-del (`venv`, `node_modules`, `dist` osv.). Den
  lokale, `.gitignore`'ede mappe `artifacts/edge-qa-training/.venv-edge-qa-train-py312/`
  indeholder et helt vendored virtualenv (sympy, onnxruntime, onnx, fsspec, networkx m.fl.) fra
  en tidligere AI-trænings-kørsel — IKKE committet til Git (`git ls-files` bekræftede 0 rørte
  filer deri), men til stede på disk. En reproduktion af scan-logikken i denne runde viste at
  **72 af 80** (scannerens hårde loft) rapporterede "signaler" reelt kom fra denne
  tredjeparts-kode, ikke fra TimeLapse Pro. Værre: fordi scanneren stopper hårdt ved 80 fund og
  traverserer dybde-først, blev hele loftet brugt op af denne støj FØR resten af repoet —
  inklusive `headend/main.py` selv — nåede at blive scannet. Det betyder cockpittets tal ikke
  bare var upræcist, men reelt kunne skjule ægte fund fra egen kode. Et reelt
  dataintegritetsproblem i en GRC-evidenskilde, ikke bare kosmetik.
- **Rettet (kode + tests):**
  1. Skip-logikken er udtrukket fra `_aiops_static_scan()` til en ren, sideeffektfri
     hjælpefunktion `_aiops_scan_should_skip_path()`, som nu ud over de oprindelige eksakte
     mappenavne også springer `artifacts` (eksakt topniveau-match), enhver sti-del der STARTER
     MED `.venv` (fanger navngivne venvs som `.venv-edge-qa-train-py312`, ikke kun den
     bogstavelige `.venv`), og enhver sti-del der INDEHOLDER `site-packages`/`dist-packages`
     over.
  2. Ny testfil `headend/tests/test_aiops_static_scan.py` — 6 kontrakt-tests: det konkrete
     tilfælde der udløste fixet, `artifacts/`-topniveau uden venv-navn, dotted-venv-varianter,
     regression på de oprindelige eksakte mappenavne (`venv`/`node_modules`/`__pycache__`), at
     rigtig produktkode (`headend/main.py`, `claude_proxy.py`, `e2e_test.sh`,
     `timelapse-ui/src/...`) FORTSAT scannes (fixet må ikke blive for grådigt), og at et
     tilfældigt filnavn der bare indeholder "venv" som substreng (uden at være en dotfile-venv)
     ikke fejlagtigt springes over.
- **Verifikation:** Samme mønster som tidligere runder — frisk venv (`/tmp/hvenv2`, allerede til
  stede i denne sandbox) med `fastapi==0.136.1`, `sqlalchemy==2.0.49`,
  `python-jose[cryptography]==3.5.0`, `bcrypt==5.0.0`, `passlib==1.7.4`, `slowapi==0.1.9`,
  `python-multipart==0.0.27`, `python-dotenv`, `pytest`, `httpx`. `python3 -m py_compile main.py
  database.py tests/test_aiops_static_scan.py` ren. Hele test-suiten i `headend/tests/`:
  **29/29 bestået** (23 eksisterende, uændrede + 6 nye). Kørte desuden selve
  `_aiops_static_scan()` direkte (med sqlite-DB) FØR og EFTER rettelsen for at bekræfte
  effekten i praksis: før fixet var 72/80 fund fra `artifacts/...site-packages/...`; efter
  fixet er samtlige 80 fund fra egen kode (mest `headend/main.py`: `subprocess.run`/`unlink`/
  `rmtree`-kald i backup-, thumbnail- og docker-relateret driftskode — jf. funktionens egen
  docstring er dette "review signals, not proof of vulnerability", ikke i sig selv bekræftede
  sårbarheder). Ingen live-kald foretaget noget sted.
- **Dokumentation opdateret (samme runde):** `RISK_ASSESSMENT_v10.md` — ny §5.2-post
  VPEN-2026-008 med fuld beskrivelse; §2's historiske VPEN-006-linje opdateret med henvisning;
  §11 P2.4 ("SAST backlog triage") opdateret til at forklare at det oprindelige tal "73" var
  upålideligt, og at den reelle triage-mængde formentlig er STØRRE, ikke mindre, end før troet;
  §12 dokumenthistorik fik en ny linje.
- **Ikke gjort — bevidst:** INGEN faktisk triage af de reelle SAST-signaler i egen kode udført
  denne runde (kategorisering i accepted safe pattern / needs guardrail / needs test / needs
  change ticket, jf. VPEN-006's oprindelige anbefaling) — det er et betydeligt, separat stykke
  arbejde der kræver individuel vurdering af hvert fund (nu formentlig 80+, ikke 73), og bør
  ikke forceres overfladisk igennem i én 20-minutters periodisk kørsel. VPEN-006/§11 P2.4 er
  derfor bevidst IKKE markeret løst — kun selve måleinstrumentets pålidelighed er rettet. Ingen
  ændring af det hårde 80-fund-loft eller af hvilke filtyper/mønstre der scannes. Ingen
  commit/push (samme konvention — Peter/Codex committer selv).
- **Codex/Peter: kør venligst når I har et vindue (kodefix + ny test, ufarlig at merge —
  rører kun en read-only AI Ops-diagnostikfunktion, ingen deploy/genstart kræves for selve
  denne ændring, men indgår i næste normale headend-deploy som vanligt):**
  ```bash
  cd /Users/peter/projects/timelapse-pro
  git diff headend/main.py
  git add headend/main.py headend/tests/test_aiops_static_scan.py \
          Dokumentation/RISK_ASSESSMENT_v10.md Dokumentation/HANDOVER_LOG.md
  git commit -m "fix: AI Ops SAST scan no longer counts vendored artifacts/ virtualenv as own-code signals"
  git push
  ```
- **Filer rørt:** `headend/main.py`, `headend/tests/test_aiops_static_scan.py` (ny),
  `Dokumentation/RISK_ASSESSMENT_v10.md`.
- **Går videre til:** næste periodiske runde kan enten (a) begynde selve triagen af de reelle
  SAST-signaler i `headend/main.py` (nu synlige, tidligere druknet i støj) i overskuelige
  batches, eller (b) tage fat på den øvrige, fortsat uændrede liste — live
  multi-device-rollout-test, Peters §6-beslutning (CA/mTLS), R17-smoketesten, §K's "OS
  offline-artifact update E2E", device-decommission-beslutningen, eller at bekræfte den
  faktiske Gemini/Vertex-produktionsregion.

### Handover 2026-07-05 (morgen) - Codex: AI Ops SAST virtualenv-scanfix committet
- **Udført:** Claude's AI Ops/SAST scanner-fix er gennemgået, testet, committet og pushet på
  `claude/capture-camera-location-2026-07-03` som `981c5802`:
  `fix: AI Ops SAST scan no longer counts vendored artifacts/ virtualenv as own-code signals`.
- **Verifikation:** `python3 -m py_compile headend/main.py headend/database.py
  headend/tests/test_aiops_static_scan.py` var ren. Codex kørte:
  `/tmp/tlp-hvenv/bin/python -m pytest tests/test_report_update_rollup.py tests/test_update_lifecycle.py tests/test_gemini_region_guard.py tests/test_change_ticket_sbom.py tests/test_aiops_static_scan.py -v`
  med **29 passed**.
- **Drift:** Ingen live-genstart udført i denne runde; ændringen rører kun read-only AI
  Ops-diagnostik og kan indgå i næste normale headend-deploy.
