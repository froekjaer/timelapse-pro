# Edge QA model export to Orange Pi VIPLite

The training script exports:

- `edge_qa_model.onnx`
- `edge_qa_model_metadata.json`
- class contract from `edge/ai/model_contract.py`

Target input for the production model:

- RGB
- 224 x 224
- NCHW in ONNX (`1,3,224,224`)
- pixel values scaled to `0..1`

The current VIPLite wrapper can preprocess `nhwc_rgb`, `nchw_rgb` or `nchw_bgr`.
For the production QA model, prefer `nchw_rgb` unless ACUITY export proves another
layout is required.

Manual Orange Pi/ACUITY flow from the vendor SDK:

1. Train and export `edge_qa_model.onnx`.
2. Copy ONNX and calibration images to the ACUITY Docker workspace.
3. Run the vendor `pegasus_import.sh`, `pegasus_quantize.sh`,
   `pegasus_inference.sh` and `pegasus_export_ovx.sh` flow.
4. Install the resulting `.nb` as `/opt/timelapse/models/edge_qa.nb`.
5. Configure:

```yaml
quality:
  edge_ai:
    mode: npu_first
    model_path: /opt/timelapse/models/edge_qa.nb
    vendor_binary: /opt/timelapse/bin/edge_qa_viplite --input-layout nchw_rgb
```

Important: keep the CPU/OpenCV QA optimizer enabled as the safety fallback until
the NPU model has been validated on real camera data.

## Prepared MobileNet smoke workspace

Use `edge/tools/prepare_acuity_workspace.py` to build the exact folder layout
expected by the Allwinner `pegasus_*` scripts:

```bash
python edge/tools/prepare_acuity_workspace.py \
  --model /path/to/model-mobilenet-v1-preload-smoke/edge_qa_model.onnx \
  --metadata /path/to/model-mobilenet-v1-preload-smoke/edge_qa_model_metadata.json \
  --manifest /path/to/curated-broad-v1-smoke.jsonl \
  --out-dir /tmp/timelapse-acuity \
  --name edge_qa_model \
  --per-label 24
```

The tool writes:

- `edge_qa_model/edge_qa_model.onnx`
- `edge_qa_model/edge_qa_model.onnx.data` if PyTorch exported external data
- `edge_qa_model/inputs_outputs.txt`
- `edge_qa_model/channel_mean_value.txt`
- `edge_qa_model/dataset.txt`
- resized calibration JPEGs

For the MobileNet smoke model, `channel_mean_value.txt` is `0 0 0 0.00392157`
because ImageNet mean/std normalization is already inside the ONNX graph.

On Orange Pi 4 Pro A733 the SDK reports `NPU_VERSION = v3`, so use:

```bash
source ../scripts/pegasus_setup.sh v3
../scripts/pegasus_import.sh edge_qa_model
../scripts/pegasus_quantize.sh edge_qa_model uint8
../scripts/pegasus_inference.sh edge_qa_model uint8
../scripts/pegasus_export_ovx_nbg.sh edge_qa_model uint8 "$VSIMULATOR_CONFIG" "$VIV_SDK"
```

The board-side `/opt/timelapse/ai-sdk` currently contains runtime libraries,
examples and the `pegasus_*` wrapper scripts, but not the ACUITY compiler binary
itself. If `pegasus_import.sh` says `Need to set environment variable
ACUITY_PATH`, install/load the Allwinner ACUITY toolkit or Docker image first.

## ACUITY/VIPLite status 2026-07-02

The Allwinner ACUITY Docker image is loaded locally as `ubuntu-npu:v2.0.10.2`.
The MobileNet smoke model had to be re-exported with the legacy TorchScript ONNX
exporter (`dynamo=False`, opset 13); the PyTorch 2.9 dynamo exporter produced an
opset-18 graph that ACUITY 6.30.22 failed to import.

Working conversion path:

```bash
source /opt/ai-sdk/scripts/pegasus_setup.sh v3
/opt/ai-sdk/scripts/pegasus_import.sh edge_qa_model
/opt/ai-sdk/scripts/pegasus_quantize.sh edge_qa_model uint8
/opt/ai-sdk/scripts/pegasus_export_ovx_nbg.sh edge_qa_model uint8 "$VSIMULATOR_CONFIG" "$VIV_SDK"
```

For host-side NBG generation, use:

```bash
export VIVANTE_SDK_DIR=/root/Vivante_IDE/VivanteIDE5.11.0/cmdtools/vsimulator
export VIV_VX_ENABLE_SAVE_NETWORK_BINARY=1
```

The generated file is installed on `timelapse0101` as:

```text
/opt/timelapse/models/edge_qa.nb
sha256: 773c9986d8997ce01977e865ab2a4e64b777813d025ecfc090b7af9e582d963d
```

Runtime status:

- `/opt/timelapse/bin/edge_qa_viplite` now runs the `.nb` on `/dev/vipcore`.
- The wrapper feeds FP16 input (`224x224x3`, default scale `1/255`).
- `edge/tools/edge_qa_npu_runner.py` returns a valid `timelapse.edge_qa.v1`
  contract with `available=true`.

Important remaining work: NPU inference is stable, but the quantized `.nb`
output is not yet numerically close enough to the ONNX CPU baseline. Keep
`quality.edge_ai.mode=assist` and CPU/OpenCV fallback enabled until a v2
calibration/export is validated across a broader image set.

## ONNX vs NPU parity analysis 2026-07-02

Tool:

```bash
python edge/tools/evaluate_edge_qa_npu_parity.py \
  --image-root /Volumes/data-fast/timelapse-incoming/canonical-images \
  --onnx-model artifacts/edge-qa-training/edge-qa-v1-20260630-095321/acuity-edge-qa-mobilenet-smoke/edge_qa_model/edge_qa_model_legacy_opset13.onnx \
  --remote orangepi@192.168.86.134 \
  --remote-model /opt/timelapse/models/edge_qa.nb \
  --vendor-binary /opt/timelapse/bin/edge_qa_viplite \
  --input-layout nchw_rgb
```

Main 50-image result:

- JSONL: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-090636.jsonl`
- Summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-090636_summary.json`
- `top1_match_rate`: `0.36`
- mean MAE: `0.1142`
- mean cosine: `0.5870`
- mean KL CPU->NPU: `0.8567`

20-image input sweep:

| Layout/scale | Top-1 match | Mean MAE | Mean cosine | Mean KL |
| --- | ---: | ---: | ---: | ---: |
| `nchw_rgb`, default `1/255` | 0.40 | 0.1160 | 0.5991 | 0.8849 |
| `nchw_bgr`, default `1/255` | 0.30 | 0.1139 | 0.5993 | 0.9230 |
| `nhwc_rgb`, default `1/255` | 0.25 | 0.1240 | 0.5332 | 1.1525 |
| `nchw_rgb`, scale `1.0` | 0.25 | 0.1395 | 0.4841 | 1.3103 |
| `nhwc_rgb`, scale `1.0` | 0.25 | 0.1394 | 0.4836 | 1.2971 |

Conclusion: keep `nchw_rgb` with default `1/255` as the runtime contract for now. The mismatch is
not solved by channel/layout/scale changes alone. The quantized NPU model has a strong `blurry`
bias and misses most `underexposed`, `depth_of_field_issue`, `ok`, and many `overexposed` cases.
Next export should focus on calibration and possibly removing/fusing the ONNX normalization path in
a way ACUITY quantizes more faithfully.

## v2 MobileNetV2 vs NPU-friendly CNN 2026-07-02

MobileNetV2 v2 reached strong ONNX accuracy (`0.9655` test accuracy), but the
ACUITY/VIPLite `.nb` export remained unusable in parity tests. Both the original
candidate and an RGB inputmeta re-export showed a hard bias toward `blurry`.

The VIPLite wrapper itself is not the root cause. It now supports both input
contracts:

```bash
/opt/timelapse/bin/edge_qa_viplite \
  --model /opt/timelapse/models/edge_qa.nb \
  --image /tmp/edge-qa-smoke.jpg \
  --json --input-layout nchw_rgb --input-dtype fp16

/opt/timelapse/bin/edge_qa_viplite \
  --model /opt/timelapse/models/edge_qa_simple_mini.nb \
  --image /tmp/edge-qa-smoke.jpg \
  --json --input-layout nchw_rgb --input-dtype uint8
```

Installed candidate models on `timelapse0101`:

- `/opt/timelapse/models/edge_qa.nb`: legacy fp16 model.
- `/opt/timelapse/models/edge_qa_v2.nb`: MobileNetV2 v2 candidate, not for
  autonomous use.
- `/opt/timelapse/models/edge_qa_v2_rgb.nb`: MobileNetV2 RGB re-export
  candidate, not for autonomous use.
- `/opt/timelapse/models/edge_qa_simple_mini.nb`: simple Conv/ReLU/Pool mini
  model for NPU parity regression.

The simple CNN mini model is not accurate enough as a QA product model, but it
does prove the NPU path is numerically healthy:

- ONNX: `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/model-simple-cnn-mini-npu-rgb/edge_qa_model.onnx`
- NBG: `/opt/timelapse/models/edge_qa_simple_mini.nb`
- sha256: `3af381b14bfb8de8431441f85448b26fa8f541996162447298a04d219102a0eb`
- parity summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-114804_summary.json`
- top-1 match: `0.9167`
- mean MAE: `0.0032`
- mean cosine: `0.9994`

Conclusion: for production NPU QA, prefer an ACUITY-friendly standard-conv
architecture over MobileNetV2/depthwise-heavy models unless ACUITY calibration
can be made demonstrably faithful.

## Edge CNN baseline 2026-07-02

`edge_cnn` is the current preferred Orange Pi 4 Pro NPU architecture family. It
uses only standard ACUITY-friendly operators:

- `Conv`
- `Relu`
- `MaxPool`
- `GlobalAveragePool`
- `Flatten`
- `Gemm`

Mini baseline:

- ONNX: `artifacts/edge-qa-training/edge-qa-v2-npu-20260702-095056/model-edge-cnn-mini-npu-rgb/edge_qa_model.onnx`
- NBG: `/opt/timelapse/models/edge_qa_edge_cnn_mini.nb`
- sha256: `d98274bdf7bf36745300cbf8da4ebc2e07a1c95f62b6c0e21b86f247ca8eda24`
- input: `nchw_rgb`, `uint8`, 224x224
- mini test accuracy: `0.8370`
- parity summary: `artifacts/edge-qa-npu-parity/edge_qa_npu_parity_20260702-121903_summary.json`
- 20-image top-1 match: `1.0000`
- mean MAE: `0.0053`
- mean cosine: `0.9985`

Runtime command:

```bash
/opt/timelapse/bin/edge_qa_viplite \
  --model /opt/timelapse/models/edge_qa_edge_cnn_mini.nb \
  --image /tmp/edge-qa-smoke.jpg \
  --json --input-layout nchw_rgb --input-dtype uint8 --classes 9
```

This model is the first useful NPU-compatible baseline. Keep it in assist/test
mode until a full-manifest `edge_cnn` model has been trained, exported, installed
and validated with broader parity.
