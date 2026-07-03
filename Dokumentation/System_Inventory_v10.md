# TimeLapse Pro — System Inventar (v10, konsolideret)

**Version:** 10 (konsolideret; oprindeligt v1.0, 14. april 2026)
**Dato:** 2026-07-02
**Konverteret fra:** `TimeLapse_System_Inventory_v1.docx` (arkiveret i `Gamle versioner/`).
**Kilde:** Direkte SSH-output fra begge enheder (find, pip, systemctl, dpkg, df).

> **Historisk snapshot:** Dette inventar er fra Canon/Raspberry-Pi-5-æraen (edge = Canon EOS 1300D/1000D, headend = Raspberry Pi 5, SQLite). Aktuelt kamera er Nikon Z30 og production-headend er Mac Mini + PostgreSQL. Det **levende** inventar føres nu i CMDB (`README_CMDB.md`, `ADMINISTRATORMANUAL_v10.md` §18). Bevaret som empiri/reference for edge-hardware, mappestruktur og pakkelister.

## 1. Orange Pi 4 Pro — Edge node (timelapse0101)

| Parameter | Værdi |
|---|---|
| Hostname / IP | timelapse0101 / 192.168.86.134 |
| Hardware | Orange Pi 4 Pro, RK3588S octa-core, 128 GB NVMe M.2 |
| OS / Python | Armbian/Ubuntu 24.04 (arm64) / system 3.12.3, venv `/opt/timelapse/venv` (3.12) |
| Kamera 0 | Canon EOS 1300D — `/dev/cam0` — GPIO 356 (pin 7) |
| Kamera 1 | Canon EOS 1000D — `/dev/cam1` — GPIO 357 (pin 16) |
| Modem relay | GPIO 361 (pin 11) — 4G USB-modem |
| Disk | NVMe 128 GB — 19 GB brugt / 93 GB ledig (17%) |

**Mappestruktur (udvalgt):** `/opt/timelapse/` = git-repo root (edge/, headend/, src/, timelapse-ui/, deploy/, tests/, venv/). `/opt/timelapse/edge/` = agent.py, config.yaml, bootstrap.yaml; undermapper camera/ (+drivers/), capture/ (buffer.py, quality.py), config/, diagnostics/, upload/ (sftp.py, headend_client.py), utils/ (database.py SQLite), ssh/, scripts/, update/. `/data/` = captures + SQLite (`/data/timelapse_edge.db`). Capture-navngivning: TL-prefix (2026-03-29→31) → `Kunde_Site_Kamera_YYYYMMDD_HHMMSS.jpg` (fra 03-31) + sidecar JSON (fra 04-13, Sprint B).

**Edge venv-pakker (nøgle):** cryptography 46.0.6 (Fernet/RSA/ED25519), opencv-python-headless 4.13 (blur/brightness), numpy 2.4.4, OPi.GPIO 0.5.2, paramiko 4.0 (SFTP), PyYAML 6.0.3, requests 2.33, bcrypt 5.0, PyNaCl 1.6.2. Mangler til Sprint C: pyotp, python-jose (JWT), qrcode, autossh (apt).

**Edge services:** timelapse-edge.service (✅ agent), timelapse-watchdog.service (✅ genstart ved crash), cron (nightly reboot 03:00), ssh.socket (LAN-only). **System-pakker (nøgle):** gphoto2 2.5.28, libgphoto2 2.5.31, libimage-exiftool-perl 12.76, openssh 9.6p1.

## 2. Raspberry Pi 5 — Headend (raspberrypi) [historisk; nu Mac Mini]

| Parameter | Værdi |
|---|---|
| Hostname / IP | raspberrypi / 192.168.86.132 |
| Hardware | Raspberry Pi 5, 8 GB RAM, SD-kort 57 GB |
| OS / Python | Raspberry Pi OS (Debian 13) / system 3.13.5, venv `/home/peter/venv` (3.13) |
| API / UI | FastAPI port 8000 (bag nginx) / nginx port 80 → `timelapse-ui/dist/` |
| Disk | SD 57 GB — 27 GB brugt / 28 GB ledig (49%) ⚠️ |

**Mappestruktur (udvalgt):** `/home/peter/headend/` (main.py v2.7.0, database.py v2.1.0), `/home/peter/timelapse-ui/dist/`, `/home/peter/venv/`, `/home/peter/backup/` (headend ×6 + edge ×11 tarballs), `/data/sftp/incoming/` (Kunde/Site/YYYY/MM/DD/*.jpg), `/data/sftp/incoming/_backups/TL-C87FF9587CA0/`, `/etc/nginx/`.

**Headend venv-pakker (nøgle):** fastapi 0.135.2, uvicorn 0.42, starlette 1.0, pydantic 2.12.5, SQLAlchemy 2.0.48, python-jose 3.5 (JWT RS256/HS256), bcrypt 5.0, passlib 1.7.4, cryptography 46.0.6, pillow 12.1.1. **Services:** timelapse-headend.service (✅), timelapse-deploy.timer (poller GitHub/min), nginx (✅), ssh (✅). **System-pakker (nøgle):** ffmpeg 7.1.3 (timelapse MP4), nginx 1.26.3, openssh 10.0p1, libgphoto2 2.5.31, exiftool 13.25.

## 3. Backup-status (14. apr 2026)

Headend: 6 backups (seneste 2026-04-12) i `/home/peter/backup/`. Edge: 11 (manuelt) + 5 (SFTP incoming). ⚠️ RPi5 SD-kort halvt fyldt — NVMe HAT anbefalet før production (Sprint D).

## 4. Sprint C readiness (pakke-gap, historisk)

| Pakke/feature | Edge | Headend | Handling |
|---|---|---|---|
| bcrypt, cryptography | ✅ | ✅ | Klar |
| python-jose (JWT) | ❌ | ✅ | pip på edge |
| pyotp (TOTP/MFA) | ❌ | ❌ | pip begge |
| qrcode (MFA QR) | n/a | ❌ | pip headend |
| autossh (reverse SSH) | ❌ | n/a | apt install på edge |

## 5. Netværks-/portoversigt (historisk lab)

22 (edge/headend SSH, LAN-only), 22 SFTP (edge→headend), 80 (nginx UI+proxy), 8000 (FastAPI), 2220X (fremtidig reverse SSH-tunnel edge→VPS). Aktuel portmodel: se `PORT_AUDIT_og_WEBSITE_v10.md`.
