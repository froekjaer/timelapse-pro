# Edge1 vs Edge2 vs lab.59 — sammenligning 2026-10-04 (Claude)

Opgave (Peter): "sammenlign lige edge1 og edge2 om der mangler noget på en af dem, så vi kan få det på, og i ISO builderen".
Metode: read-only inventar over tunnelen (sha1 af alle filer under `/opt/timelapse`, systemd-units, `/etc/timelapse`, udev, apt, venv `pip freeze`), sammenholdt med `git ls-tree v2.8.1-lab.59` og lab.59-artifactets manifest (`TL-ART-20261004-cfade21cad4c`, 116 filer).

| | Edge1 `timelapse0101` TL-C87FF9587CA0 (port 2201) | Edge2 `tl-modbaggarddlvc` TL-043EB9E72EFD (port 2204) |
|---|---|---|
| OS | Ubuntu **24.04.4** (Orange Pi desktop-image, håndpatchet) | Ubuntu **22.04.5** (fra image-builderen) |
| App (edge/ i manifest) | = lab.59 | = lab.59 |

## Fund — mangler / afviger

1. **Python-pakker mangler på Edge1:** `qrcode` (står i `edge/requirements.txt`; bruges af `edge/technician_auth.py` til tekniker-QR) og `websockets`/`wsproto` (uvicorn kan ikke opgradere til WebSocket → lokal browser-terminal `/mgmt/cli/bash/ws` virker ikke på Edge1). Edge2 har `websockets`, men heller ikke `wsproto`.
   **Rodårsag (kapabilitetshul):** Python-bundle-sporet (`_reconcile_python_packages_from_pypi`, headend/main.py) opdaterer kun *installerede, forældede* pakker — det installerer aldrig *krævede, manglende* pakker. Og app-opdateringer installerer ikke pip-pakker. Derfor kom `qrcode` aldrig på Edge1.
   Desuden mangler `fastapi`, `uvicorn`, `pyotp` (og `websockets`) i `edge/requirements.txt`, selv om `totp-service.py` importerer dem — rettet på #257-branchen (ikke merged).
2. **`edge/cmdb/executor.py` på Edge1 er den gamle legacy-updater** (juni, med subprocess/git). Edge2 og lab.59 har den udfasede, inerte version. Ingen kode importerer den, men den opdateres aldrig: `_collect_release_outputs` medtager ikke `edge/cmdb/` (heller ikke `collector.py`) eller `edge/training/`.
3. **Edge1 har hele repo-kopien liggende** i `/opt/timelapse`: `headend/`, `timelapse-ui/`, `Dokumentation/`, `tests/`, `ai-sdk/` (1862 filer), `models/` (Edge-QA `.nb`/`.onnx`), samt ~30 `.bak`/`.orig`-filer i `edge/`. Edge2 har kun `edge/` + `prev/`. `ai-sdk` + QA-modeller (NPU-runtime, `edge/ai/npu_runtime.py` søger i `/opt/timelapse/ai-sdk`) findes **kun på Edge1** og er hverken i git eller i image-builderen → NPU-QA kan ikke køre på Edge2/nye images. Kræver beslutning om hvor modeller/SDK distribueres fra.
4. **Filer på begge Edges, men ikke i main:** `edge/scripts/static/xterm/*` (fra #239, åben/konflikt — ingen kode i lab.59 bruger dem), `edge/scripts/timelapse-watchdog.service` (fra #257, åben/konflikt; enheden kører på begge), `edge/scripts/timelapse-breakglass-setup.{service,sh}` (fra lukket #9; erstattet af `inject_edge_image.py` + agent — ikke nødvendig).
5. **Edge2 mangler udev-regler** `99-timelapse-gpio.rules` (og den forældede Canon-H3 `99-timelapse-cameras.rules`). Ingen funktionel effekt nu (agent kører som root), men #257 sender GPIO-reglen med i images.
6. **Kun Edge2:** `timelapse-breakglass-setup.service` enabled (oneshot, allerede provisioneret), `timelapse-bootstrap`/`timelapse-ssh-tunnel` (disabled), `/etc/timelapse/{bootstrap.yaml,node-agent.conf,.enrolled}`, `edge/HEADEND_URL`, `edge/VERSION`, `edge/bootstrap.yaml.template` (image-builder-artefakter). **Kun Edge1:** `/etc/timelapse/tls`, `edge/camera/technician_session.py` (fra lukket #9, ikke importeret), `edge/keys/edge_signing_ed25519*`, tunnel-/sftp-nøgler under `edge/ssh/` (Edge2 har dem andetsteds).
7. **Ens på begge:** watchdog, timesync.timer, chrony, NetworkManager, bt-pan/agent, captive, totp aktive; uvicorn 0.52.4 / fastapi 0.141.1; `emergency`-konto med break-glass-wrapper.

## Åbne spor der dækker dele af dette
- **#257** (Golden Edge builder-huller: network-manager, chrony, timesync, watchdog, fastapi/uvicorn/pyotp i requirements, GPIO-udev, sudoers, gphoto2-pin, build-gate) — CONFLICTING mod main siden 2026-09-24.
- **#239** (xterm.js i direct-Edge-terminal) — CONFLICTING, afventer fysisk test.
