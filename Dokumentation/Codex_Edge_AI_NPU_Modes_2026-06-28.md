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

Status: NPU-hardware, VIPLite runtime og `.nb` modelsti er verificeret. TimeLapse-runneren bruger stadig CPU/OpenCV optimizer som produktions-QA og markerer `vendor_runtime_binding_not_installed`, indtil vi har en egentlig TimeLapse QA `.nb` model og binding/eksekverbar wrapper til VIPLite.

## Næste modelmilepæl

1. Indsaml 200-500 repræsentative billeder pr. klasse fra rigtige installationer og syntetiske testbilleder.
2. Byg `manifest.jsonl` med `build_qa_dataset_manifest.py`.
3. Træn en lille MobileNet/EfficientNet-lignende klassifikationsmodel på PC.
4. Eksporter ONNX og konverter til `.nb` med Allwinner ACUITY.
5. Implementer `/opt/timelapse/bin/edge_qa_viplite`, der læser image/model og skriver scores JSON.
6. Sæt `quality.edge_ai.vendor_binary` i global/kunde/site/kamera-konfigurationen og kør `mode=npu_first` på testkamera.
