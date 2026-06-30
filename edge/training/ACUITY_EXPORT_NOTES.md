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
