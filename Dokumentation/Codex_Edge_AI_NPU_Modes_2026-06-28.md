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

Første produktionsmodel bør sandsynligvis være en lille klassifikationsmodel, ikke en stor vision-LLM:

- input: nedskaleret JPEG/preview
- outputklasser: `ok`, `blurry`, `snow_or_dirt_on_lens`, `condensation`, `direct_sun_reflection`, `underexposed`, `overexposed`, `white_balance_cast`
- output: confidence + class, som runneren mapper til TimeLapse JSON-kontrakten

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

## Morgenens hardware-test

1. Verificer at `opencv-python-headless` virker i edge venv.
2. Kør `edge_qa_npu_runner.py` på Orange Pi og gem JSON-output.
3. Tjek runtime hints: `/dev/galcore`, `/dev/npu`, VIPLite/libNPU vendor libs.
4. Installer vendor SDK/model når tilgængelig.
5. Sæt `quality.edge_ai.mode=npu_first` på testkamera.
6. Tag LAB-preview og fuldt capture; kontroller `.qa.json` og `capture.ai_result`.
