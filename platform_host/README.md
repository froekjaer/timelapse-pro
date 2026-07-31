# platform_host/ & payloads/timelapse/ — ADR-002 vertical slice (tests-only)

Proves the contract set fits the REAL edge capture flow.

- `payloads/timelapse/driver.py` — `TimelapsePayloadDriver` wraps the existing
  `edge/camera/base.py::CameraBase` (inject `GPhoto2Driver` in production; a fake
  in tests) behind `PayloadDriver`. Publishes captures as classified `images`
  blobs (retention_class `project-evidence-explicit-disposition`, tying into the
  proposed Evidence Retention policy) and capture metrics as timeseries.
- `platform_host/` — reference host: `SpoolDataSink` (declared-channel + quota +
  backpressure enforcement), `Supervisor` (fail-closed manifest/policy admission,
  lifecycle, health restart/quarantine), `policy` (signed node policy).

Invariants (tested in `tests/test_vertical_slice.py`): platform_host imports no
payloads; payloads/timelapse imports contracts (not platform_host); end-to-end
capture lands classified evidence; absent camera, capture failure, backpressure
and unknown commands all handled fail-safe.

**Not wired into edge/agent runtime yet.** Eventual home: `platform_core/` +
`payloads/timelapse/` when P2-01 extraction begins. Run:
`PYTHONPATH=.:edge pytest tests/test_vertical_slice.py -q`
