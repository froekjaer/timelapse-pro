# Golden Edge #257 vs main — evidence-based delta (2026-10-10)

**No feature removal, no blind cherry-pick.** Main and physical devices unchanged.

| Item | Current main | PR #257 | Verdict |
|---|---|---|---|
| Local portal dependencies | `edge/requirements.txt` already contains FastAPI, Uvicorn WebSockets, python-multipart and PyOTP | Includes dependency work | ALREADY_PRESENT_IN_MAIN; preserve newer versions |
| Watchdog service | `edge/scripts/timelapse-watchdog.service` exists and is referenced by `Dockerfile.edge` | Includes watchdog unit | ALREADY_PRESENT_IN_MAIN; compare semantics before any edit |
| System baseline unit | `Dockerfile.edge` references `timelapse-system-baseline.service` | Addresses system baseline | PARTIALLY_PRESENT; physical build gate remains |
| GPIO udev rule | `edge/config/99-timelapse-gpio.rules` absent on main | Adds rule | UNINTEGRATED_CANDIDATE; inspect board mapping and permission model |
| Edge sudoers template | `edge/config/timelapse-edge-sudoers` absent on main | Adds template | UNINTEGRATED_CANDIDATE; security review before adding privilege |
| Golden image validator | `headend/tools/golden_edge_baseline.py` absent on main; image builder does not reference it | Adds validator | UNINTEGRATED_CANDIDATE; separate Headend-side build verification |
| Golden validator tests | `tests/test_golden_edge_baseline.py` absent on main | Adds tests | UNINTEGRATED_CANDIDATE; ensure target matrix coverage |
| Camera compatibility | Current Dockerfile explicitly pins libgphoto2 2.5.34/gphoto2 2.5.32 (2026-10-01) | Earlier PR changes Dockerfile | DO_NOT_REGRESS; retain current Nikon Z30 support |

## Architectural contract
- Headend owns image **building, artifact validation, signing and deployment authorization**.
- Edge owns local **systemd services, GPIO, hardware access, autonomous capture and rollback**.
- Build validation must inspect target-specific output; it must never require Edge to run a Headend service.
- Permission changes (udev/sudoers) require least privilege and hardware-model validation.
- Test gate: static manifest assertions → actual arm64 build → offline first boot → camera/relay/tunnel/recovery physical acceptance.

## Integration decision
**BLOCKED for blanket #257 merge.** Several features already exist in main. Isolate missing validator and permissions and compare exact semantics first; additive implementation on this integration branch only.

## Evidence limits
File existence and text checks were performed on current GitHub main. No local test run, full file diff, physical image build or device verification. The PR's changes cannot be declared redundant as a whole.
