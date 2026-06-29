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
