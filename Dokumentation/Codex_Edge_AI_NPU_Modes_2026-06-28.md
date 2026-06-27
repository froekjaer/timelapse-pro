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
    runner: /opt/timelapse/edge/tools/edge_qa_npu_runner.py
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

## Testbilleder

Generer testpakke:

```bash
python edge/tools/generate_qa_test_images.py --out /tmp/timelapse-qa-test-images
```

Kør runner:

```bash
python edge/tools/edge_qa_npu_runner.py \
  --model /opt/timelapse/models/edge_qa.nb \
  --image /tmp/timelapse-qa-test-images/qa_03_direct_sun_reflection.jpg \
  --json
```

## Morgenens hardware-test

1. Verificer at `opencv-python-headless` virker i edge venv.
2. Kør `edge_qa_npu_runner.py` på Orange Pi og gem JSON-output.
3. Tjek runtime hints: `/dev/galcore`, `/dev/npu`, VIPLite/libNPU vendor libs.
4. Installer vendor SDK/model når tilgængelig.
5. Sæt `quality.edge_ai.mode=npu_first` på testkamera.
6. Tag LAB-preview og fuldt capture; kontroller `.qa.json` og `capture.ai_result`.

