# contracts/ — Mission Platform contract set v1 (ADR-002)

The versioned platform/payload seam. **Pure**: imports nothing from headend/ or
edge/. Landed tests-only — no runtime wiring yet; it is the target that P2-01
extraction migrates toward. Timelapse is the first payload.

- `control.py` — PayloadDriver (configure/start/stop/health/handle_command)
- `data.py` — DataSink + blob/timeseries/event channels with classification + retention
- `manifest.py` + `manifest-v1.schema.json` — fail-closed capability manifest (no actuation in v1)

Gates: `tests/test_contracts_architecture.py` (purity, fail-closed, safety),
`tests/test_hardcoded_ratchet.py` (config-rule ratchet). See
`Dokumentation/ADR/ADR-002-contract-set-v1.md`.
