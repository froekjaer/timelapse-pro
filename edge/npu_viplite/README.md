# TimeLapse Edge QA VIPLite wrapper

Board-side wrapper for Allwinner/Orange Pi A733 VIPLite `.nb` models.

It is intentionally tiny: read an image, preprocess to the agreed Edge QA input
shape, run the `.nb` model through AWNN/VIPLite, and emit one JSON object with
`scores`. The Python runner normalises those scores into the stable
`timelapse.edge_qa.v1` contract.

Build on Orange Pi:

```bash
cd /opt/timelapse/edge/npu_viplite
cmake -S . -B build -DAI_SDK_ROOT=/opt/timelapse/ai-sdk
cmake --build build -j"$(nproc)"
sudo install -m 0755 build/edge_qa_viplite /opt/timelapse/bin/edge_qa_viplite
```

Smoke-test with the SDK ResNet model:

```bash
/opt/timelapse/bin/edge_qa_viplite \
  --model /opt/timelapse/models/edge_qa.nb \
  --image /tmp/timelapse-qa-board-contract/qa_03_direct_sun_reflection.jpg \
  --input-layout nchw_bgr \
  --json
```

The ResNet model is only a runtime proof. A real TimeLapse QA model must be
trained/exported for the labels in `edge/ai/model_contract.py`.
