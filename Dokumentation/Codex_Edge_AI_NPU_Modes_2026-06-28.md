# TimeLapse Pro - Edge AI/NPU modes

Dato: 2026-06-28

## Formål

Edge AI skal forbedre billedkvalitet lokalt på Orange Pi 4 Pro/A733-lignende hardware:

- lys og eksponeringskompensation
- fokus/uskarphed
- hvidbalance
- dybdeskarphed/fokusplan
- direkte sol/refleks
- sne, skidt, dug eller saltfilm på frontglas/linse

Semantisk tagging af byggepladsindhold bør fortsat ligge i headend/cloud-flow med review. Edge AI er deterministisk QA og kamera-feedback.

## Modes

Konfigureres via `quality.edge_ai.mode` og kan arves fra global, kunde, site eller kamera.

| Mode | Brug | Autonom handling |
| --- | --- | --- |
| `off` | Sluk Edge AI-laget | Ingen |
| `monitor` | Kun analyse/evidence | Ingen EV eller kommandoer |
| `assist` | Standard drift | Sikker EV-justering, anbefalinger |
| `autonomous` | Mere aktiv drift | Sikker EV-justering, schedule-forslag |
| `npu_first` | NPU prioriteres | NPU/runner bruges som højere signal |
| `lab` | Kalibrering og test | Flere forslag/kommandoer tillades |

`quality.adaptive_exposure.enabled` skal stadig være `true`, før Edge faktisk justerer EV mellem captures.

## NPU-kontrakt

Runner konfigureres med:

```yaml
quality:
  edge_ai:
    enabled: true
    mode: assist
    prefer_npu: true
    runner: /opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py
    model_path: /opt/timelapse/models/edge_qa.nb
    vendor_binary: /opt/timelapse/bin/edge_qa_viplite
```

Runneren skal skrive præcis ét JSON-objekt til stdout. Minimum:

```json
{
  "engine": "edge_npu",
  "available": true,
  "is_anomaly": true,
  "probable_cause": "direct_sun_reflection",
  "confidence": 0.88,
  "recommended_action": "Sænk EV eller undgå dette tidspunkt"
}
```

Den nuværende runner er NPU-klar, men falder tilbage til CPU/OpenCV hvis vendor runtime/model mangler. Den returnerer runtime-detektion, så hardwarestatus kan ses i QA-resultatet.

`runner` er den stabile TimeLapse Python-kontrakt. `vendor_binary` er valgfri og peger på den board-lokale VIPLite-wrapper, som senere kører den rigtige `.nb` QA-model og returnerer enten `label + confidence`, `class_id + confidence` eller `scores`.

Status 2026-06-28: `vendor_binary`-wrapperen er implementeret, bygget og installeret på
testboardet som `/opt/timelapse/bin/edge_qa_viplite`. Den bruger Allwinner AWNN/VIPLite og
emitter ren JSON på stdout. VIPLite runtime-log går til stderr, så Python-runneren kan parse
outputtet stabilt.

## QA modelkontrakt

Kontrakten er defineret i `edge/ai/model_contract.py`.

Inputkontrakt til første NPU-model:

- 224 x 224
- RGB
- NHWC
- pixel scale `1/255`

Outputklasser:

| id | label | Dimension |
| --- | --- | --- |
| 0 | `ok` | overall |
| 1 | `blurry` | focus |
| 2 | `depth_of_field_issue` | depth_of_field |
| 3 | `snow_or_dirt_on_lens` | lens_obstruction |
| 4 | `condensation` | lens_obstruction |
| 5 | `direct_sun_reflection` | schedule |
| 6 | `underexposed` | exposure |
| 7 | `overexposed` | exposure |
| 8 | `white_balance_cast` | white_balance |

Wrapper-output kan være en af disse former:

```json
{"label": "direct_sun_reflection", "confidence": 0.92}
```

```json
{"class_id": 5, "confidence": 0.92}
```

```json
{"scores": {"ok": 0.02, "direct_sun_reflection": 0.92}}
```

Runneren normaliserer dette til `timelapse.edge_qa.v1` med `probable_cause`, `quality_dimension`, `recommended_action` og `model_input`.

## Orange Pi 4 Pro/A733 manualnoter

Manualens afsnit 3.34 beskriver NPU-flowet:

- NPU: 3 TOPS.
- PC-side udviklingsmiljø bruger Allwinner ACUITY Docker image, fx `ubuntu-npu:v2.0.10`.
- `ai-sdk.tar.gz` pakkes ud i Docker workspace for modelkonvertering.
- ONNX-eksempler konverteres/kvantiseres med `pegasus_import.sh`, `pegasus_quantize.sh`, `pegasus_inference.sh` og `pegasus_export_ovx.sh`.
- NPU-modellen eksporteres som `.nb`, fx `network_binary.nb`.
- Board-side installeres `libopencv-dev` og `cmake`, `ai-sdk.tar.gz` pakkes ud, og eksempler kompileres med `cmake .. && make`.
- Runtime-output viser VIPLite, fx `VIPLite driver software version 2.0.3.2-AW-2024-08-30`.
- Manualen viser eksempler for `yolov5`, `resnet50`, `struct2depth`, `transformer_cls`, `yolact`, `deepspeech2` og `chineseocr`.

Runneren søger derfor efter:

- `/opt/timelapse/ai-sdk`
- `/opt/ai-sdk`
- `~/ai-sdk`
- `TIMELAPSE_AI_SDK_ROOT`
- VIPLite biblioteker og device hints som `/dev/galcore`, `/dev/npu`, `/dev/vipcore`

Probe boardet direkte:

```bash
/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/probe_orangepi_npu.py \
  --ai-sdk-root /opt/timelapse/ai-sdk \
  --model /opt/timelapse/models/edge_qa.nb \
  --pretty
```

Vigtige felter:

- `npu_ready=true`: ai-sdk, runtime/device og model er fundet.
- `missing=["ai_sdk"]`: installer/pak `ai-sdk.tar.gz` ud på boardet.
- `missing=["viplite_runtime_or_device"]`: VIPLite runtime/device driver mangler eller er ikke synlig.
- `missing=["model_path"]`: `.nb` modellen mangler på den konfigurerede sti.

Første produktionsmodel bør sandsynligvis være en lille klassifikationsmodel, ikke en stor vision-LLM. Den bør trænes på ovenstående kontrakt og eksporteres via Allwinner ACUITY til `.nb`.

## Testbilleder

Generer testpakke:

```bash
python edge/tools/generate_qa_test_images.py --out /tmp/timelapse-qa-test-images
```

Kør runner:

```bash
/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py \
  --model /opt/timelapse/models/edge_qa.nb \
  --image /tmp/timelapse-qa-test-images/qa_03_direct_sun_reflection.jpg \
  --json
```

Kør batchanalyse på en hel mappe og skriv JSONL:

```bash
/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/analyse_qa_batch.py \
  /tmp/timelapse-qa-test-images \
  --mode npu_first \
  --runner "/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py" \
  --model /opt/timelapse/models/edge_qa.nb \
  --out /tmp/timelapse-qa-test-images/results.jsonl
```

Kør batchanalyse med installeret VIPLite-wrapper:

```bash
/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/analyse_qa_batch.py \
  /tmp/timelapse-qa-test-images \
  --mode npu_first \
  --runner "/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py" \
  --model /opt/timelapse/models/edge_qa.nb \
  --vendor-binary "/opt/timelapse/bin/edge_qa_viplite --input-layout nchw_bgr" \
  --out /tmp/timelapse-qa-test-images/viplite-results.jsonl
```

`--input-layout nchw_bgr` er kun til SDK ResNet-demoen. Den rigtige TimeLapse QA-model bør følge
kontrakten ovenfor (`nhwc_rgb`) eller dokumentere sit layout eksplicit.

Byg datasætmanifest til træning/evaluering:

```bash
/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/build_qa_dataset_manifest.py \
  /tmp/timelapse-qa-test-images \
  --out /tmp/timelapse-qa-test-images/manifest.jsonl
```

Hvis der allerede findes batchanalyse, kan den bruges som pseudo-label-kilde:

```bash
/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/build_qa_dataset_manifest.py \
  /data/captures \
  --from-batch-jsonl /tmp/timelapse-qa-test-images/results.jsonl \
  --out /tmp/timelapse-edge-qa-manifest.jsonl
```

## Morgenens hardware-test

1. Verificer at `opencv-python-headless` virker i edge venv.
2. Kør `probe_orangepi_npu.py --pretty` og gem JSON-output.
3. Installer/ret `ai-sdk`, VIPLite eller `.nb` model indtil `missing` er tom eller kendt accepteret.
4. Generer testbilleder og kør `analyse_qa_batch.py` i `monitor`, `assist` og `npu_first`.
5. Sæt `quality.edge_ai.mode=npu_first` på testkamera.
6. Kør `edge_qa_npu_runner.py` på mindst normal, sol/refleks og snavs/sne testbillede.
7. Tag LAB-preview og fuldt capture; kontroller `.qa.json` og `capture.ai_result`.

## Orange Pi 4 Pro teststatus 2026-06-28

Testet på `timelapse0101` (`192.168.86.134`):

- Board viser `/dev/vipcore=true`, `machine=aarch64`, `proc_device_tree_model=sun60iw2`.
- Installeret afhængigheder: `libopencv-dev`, `cmake`, `make`, `g++`, `pkg-config`, `tree`.
- Installeret officielt Orange Pi `ai-sdk` fra `NPU Sample Program/ai-sdk.tar` i `/opt/timelapse/ai-sdk`.
- Bygget og kørt `/opt/timelapse/ai-sdk/examples/resnet50/build/resnet50`.
- NPU-run output viste `VIPLite driver software version 2.0.3.2-AW-2024-08-30` og `awnn_run success`.
- Foreløbig modelsti `/opt/timelapse/models/edge_qa.nb` peger på SDK'ets ResNet50 demo-model for at bevise `.nb`/runtime-kæden.
- `probe_orangepi_npu.py --model /opt/timelapse/models/edge_qa.nb --pretty` returnerer `npu_ready=true` og `missing=[]`.
- Bygget og installeret TimeLapse wrapper:
  - kilde: `/opt/timelapse/edge/npu_viplite`
  - binær: `/opt/timelapse/bin/edge_qa_viplite`
  - build helper: `/opt/timelapse/edge/tools/build_edge_qa_viplite.sh`
- Verificeret fuld kæde:
  - `edge_qa_viplite` kører ResNet-demo `.nb` via VIPLite og emitter JSON.
  - `edge_qa_npu_runner.py --vendor-binary "/opt/timelapse/bin/edge_qa_viplite --input-layout nchw_bgr"` normaliserer wrapperens `scores` til `timelapse.edge_qa.v1`.
  - `analyse_qa_batch.py --vendor-binary ...` skriver batchresultater med `npu.available=true`.

Status: NPU-hardware, VIPLite runtime, `.nb` modelsti og TimeLapse wrapper er verificeret. Den
nuværende `.nb` er stadig kun ResNet50-demoen, så dens QA-scores er ikke semantisk gyldige. CPU/OpenCV
optimizer er fortsat produktions-QA, indtil vi har en egentlig TimeLapse QA `.nb` model.

## Næste modelmilepæl

Status 2026-06-29:

- Mining-værktøjet er gjort mere driftsegnet med `--sample-mode stratified`, `--max-per-bucket`,
  `--progress-every` og dæmpet QualityChecker-logning.
- Label-mining prioriterer nu primære QA-flags (`blurry`, `underexposed`, `overexposed`) før
  optimizer-anbefalinger, så nat/mørke billeder ikke fejllabels som dybdeskarphed.
- Optimizer-prioritet til træningslabels er justeret, så eksponering vinder over dybdeskarphed,
  mens vedligeholdelse og direkte sol/schedule stadig prioriteres højt.
- En konservativ normal-kandidatregel er tilføjet, men den seneste historiske sampling gav stadig
  ingen sikre `ok`-billeder. Næste datasætrunde skal derfor mine `ok` målrettet i dagslys.
- Seneste baseline:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-normal-baseline-20260629-164818`
  - inspiceret: 1500 billeder
  - valgt: 935 kandidater
  - errors: 0
  - labels selected: `direct_sun_reflection=250`, `depth_of_field_issue=250`, `overexposed=239`,
    `underexposed=141`, `blurry=54`, `white_balance_cast=1`
  - review-ark: `review/*.jpg`
  - review-CSV: `review/review.csv`

Beslutning: træn ikke første model blindt på denne baseline. Brug den som review/evidence, men lav
en separat OK-mining og kurater mindst et lille godkendt manifest, før ONNX-træning.

1. Mine kandidater fra historiske billeder:
   ```bash
   python edge/tools/mine_qa_training_candidates.py \
     /Volumes/data-fast/timelapse-incoming/canonical-images \
     --limit 5000 \
     --sample-mode stratified \
     --max-per-bucket 3 \
     --per-label 500 \
     --include-review \
     --out /tmp/edge-qa-dataset/candidates.jsonl \
     --summary-out /tmp/edge-qa-dataset/summary.json
   ```
2. Render review-ark og CSV til human review:
   ```bash
   python edge/tools/render_qa_review_sheet.py \
     --manifest /tmp/edge-qa-dataset/candidates.jsonl \
     --out-dir /tmp/edge-qa-dataset/review
   ```
3. Ret `review.csv` hvor CPU-heuristikken tager fejl, og byg et godkendt manifest til træning.
4. Træn en lille CNN/MobileNet-lignende klassifikationsmodel i separat training-venv:
   ```bash
   python -m venv .venv-edge-qa-train
   .venv-edge-qa-train/bin/pip install -r edge/training/requirements-edge-qa.txt
   .venv-edge-qa-train/bin/python edge/training/train_edge_qa_model.py \
     --manifest /tmp/edge-qa-dataset/candidates.jsonl \
     --out-dir /tmp/edge-qa-model-v1
   ```
5. Eksporter ONNX og konverter til `.nb` med Allwinner ACUITY. Se `edge/training/ACUITY_EXPORT_NOTES.md`.
6. Læg QA-modellen som `/opt/timelapse/models/edge_qa.nb`.
7. Sæt `quality.edge_ai.vendor_binary=/opt/timelapse/bin/edge_qa_viplite` i global/kunde/site/kamera-konfigurationen og kør `mode=npu_first` på testkamera.

Praktisk krav før produktionsdrift: valider modellen på mindst `test`-split og en frisk dag fra
hver kameratype. CPU/OpenCV optimizer skal forblive fallback, indtil NPU-modellen er bedre end
heuristikken på reelle edge-problemer.

## Edge QA model-v1 status 2026-06-30

Der er gennemført et end-to-end smoke-forløb fra historiske billeder til ONNX:

- Kandidat-mining:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321`
  - inspiceret: 12000 billeder
  - valgt: 6381 kandidater
  - labels selected: `ok=1200`, `direct_sun_reflection=1200`, `depth_of_field_issue=1200`,
    `overexposed=1200`, `underexposed=1162`, `blurry=408`, `white_balance_cast=11`
  - review-ark: `review/*.jpg`
  - review-CSV: `review/review.csv`
- Curated safe-core manifest: `curated-train.jsonl`
  - 2483 rækker med auto/review-recommended rækker.
- Curated broad manifest: `curated-broad-train.jsonl`
  - 5419 rækker over syv klasser; inkluderer review-rækker og er derfor heuristik-distillation.
- Smoke/deploy manifest: `curated-broad-v1-smoke.jsonl`
  - 611 rækker, maks 100 pr. klasse, brugt til første ONNX-kædetest.
- Første ONNX-model: `model-broad-v1-smoke/edge_qa_model.onnx`
  - input: NCHW/RGB 224x224, scale 1/255
  - output: 9 logits i `timelapse.edge_qa.v1` klasseorden
  - ONNX Runtime test: OK
  - runner-test: `edge_qa_npu_runner.py` kan køre `.onnx` lokalt med `engine=edge_onnxruntime_local`
  - kvalitet: smoke-only, `best_val_accuracy=0.36`, `test_accuracy≈0.31`
- Orange Pi prep:
  - ONNX kopieret til `/opt/timelapse/models/edge_qa_model_v1_smoke.onnx` på `timelapse0101`
  - metadata kopieret til `/opt/timelapse/models/edge_qa_model_v1_smoke_metadata.json`
  - eksisterende `/opt/timelapse/models/edge_qa.nb` er stadig ResNet-demoen og er ikke overskrevet.
- ACUITY bundle:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321/acuity-bundle-v1-smoke.tar.gz`
  - indeholder ONNX, metadata, ACUITY-noter og 83 kalibreringsbilleder.
  - Docker CLI findes på Mac, men Docker daemon kørte ikke under testen, så lokal ACUITY-konvertering
    er ikke udført endnu.
- Fuldt historik-run til v2 er startet som baggrundsjob:
  `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-full-20260630-112714`
  - script: `run-full-mining.sh`
  - log: `full-mining.log`
  - pid-fil: `full-mining.pid`

Beslutning: v1-smoke-modellen beviser pipeline og kan bruges til ACUITY/VIPLite-konverteringstest,
men den er ikke produktionsklar til autonom drift. Drift skal fortsat bruge CPU/OpenCV optimizer som
autoritativ fallback. Næste kvalitetsløft er at lade fuld historik-mining færdiggøre, reviewe især
`depth_of_field_issue`, `direct_sun_reflection` og `ok`, og træne v2 på safe-core + human-approved
review-rækker før `.nb` erstatter demo-modellen.

## Edge QA MobileNet smoke 2026-06-30

Der er nu trænet en bedre smoke-kandidat med transfer learning:

- Model: `model-mobilenet-v1-preload-smoke/edge_qa_model.onnx`
  - arkitektur: `mobilenet_v2`, ImageNet-pretrained, frosset feature-backbone
  - input: NCHW/RGB 224x224, scale 1/255 med ImageNet-normalisering inde i ONNX-grafen
  - output: 9 logits i `timelapse.edge_qa.v1` klasseorden
  - artifacts:
    `/Volumes/data-fast/peter-home/projects/timelapse-pro/artifacts/edge-qa-training/edge-qa-v1-20260630-095321/model-mobilenet-v1-preload-smoke`
- Træningsscriptet har fået `--preload`, `--skip-unreadable` og `--num-workers`, så historiske
  JPEG-fejl isoleres i preload/skipped-fasen i stedet for at gøre træningen langsom og uigennemsigtig.
- Smoke-metrics:
  - `best_val_accuracy=0.88`
  - `test_accuracy=0.8028169014084507`
  - stærke klasser i test: `blurry=1.0`, `underexposed=1.0`, `direct_sun_reflection=0.875`
  - svagere klasser: `overexposed=0.429`, `depth_of_field_issue=0.625`, `ok=0.733`
- Orange Pi `timelapse0101`:
  - `onnxruntime` installeret i `/opt/timelapse/venv`
  - model kopieret til `/opt/timelapse/models/edge_qa_model_v1_mobilenet_smoke.onnx`
  - ekstern vægtfil kopieret til `/opt/timelapse/models/edge_qa_model.onnx.data` og
    `/opt/timelapse/models/edge_qa_model_v1_mobilenet_smoke.onnx.data`
  - metadata kopieret til `/opt/timelapse/models/edge_qa_model_v1_mobilenet_smoke_metadata.json`
  - opdateret runner/kontraktkode kopieret til `/opt/timelapse/edge/...`
  - board-test OK: runner returnerer `engine=edge_onnxruntime_local`, `available=true` og gyldig
    `timelapse.edge_qa.v1` kontrakt på et rigtigt historisk billede.

Vigtig begrænsning: dette er stadig ONNX Runtime på CPU på Orange Pi, ikke NPU. NPU-kæden er klar
til `.nb`, men denne MobileNet-ONNX skal stadig igennem Allwinner ACUITY-konvertering. Docker daemon
kørte ikke på Mac under seneste forsøg, så ACUITY-konvertering er fortsat næste tekniske milepæl.

Driftsbeslutning: MobileNet-smoke er brugbar til integrationstest og som assist-signal. Den bør ikke
køre autonomt uden confidence-gating og CPU/OpenCV fallback. Produktsikkert første mode er
`quality.edge_ai.mode=assist`, hvor CPU/OpenCV optimizer forbliver autoritativ og ONNX/NPU kun får
lov til at styrke høj-konfidens fund.
