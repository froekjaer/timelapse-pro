# TimeLapse Pro — System Architecture & Configuration Guide (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Konsoliderer:** `TimeLapse Pro Configuration Guide.docx`, `TimeLapse_Pro_Configuration_Guide_v3.docx`, `TimeLapse_Configuration_Guide_v4.docx` (arkiveret i `Gamle versioner/`). v4 er backbone.

> **Udviklingsnote:** Guiden er fra Canon/RPi5-æraen (headend på Raspberry Pi 5, SQLite). Aktuel production-headend er Mac Mini + PostgreSQL + nginx — se `ADMINISTRATORMANUAL_v10.md` og `Headend_Installationsguide_Mac_Mini.md` for gældende opsætning. Nedenstående bevarer arkitektur- og edge-konfigurationsessensen.

## 1. Systemoverblik

Arkitektur i SABSA-lag (se `SABSA_Architecture_v10.md`). Netværk og tillidsgrænser: Edge→Headend API (nu HTTPS/JWT), Edge→Headend SFTP m. SHA-256, Browser→Headend HTTPS, Edge→SSH-tunnel (ED25519, customer approval), Kamera→Edge USB/PTP.

## 2. Headend-konfiguration

Historiske lab-kommandoer (RPi5/systemd/SQLite):

```bash
sudo systemctl status timelapse-headend
sudo journalctl -u timelapse-headend -f
sudo systemctl restart timelapse-headend
python3 -c "import ast; ast.parse(open('/home/peter/headend/main.py').read()); print('OK')"
```

Aktuel Mac Mini-drift (launchd, PostgreSQL) er dokumenteret i `ADMINISTRATORMANUAL_v10.md` §2–§3.

## 3. Konfigurationshierarki

5 lag: **Global → Kunde → Site → Kamera → Runtime (LAB)**. Lavere lag vinder. UI viser arvet/direkte/effektiv værdi + vindende lag + farvemarkering (se `ADMINISTRATORMANUAL_v10.md` §17).

## 4. Edge-node-konfiguration (Orange Pi 4 Pro)

GPIO: 356/Pin 7 = kamera 0-relæ (`/dev/cam0`), 357/Pin 16 = kamera 1-relæ (`/dev/cam1`), 361/Pin 11 = modem-relæ (aktiv-lav). USB-symlinks via udev:

```bash
ls -la /dev/cam*
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 5. Timelapse Video-generator

`POST /api/timelapse/create` (FFmpeg: FPS, opløsning, codec, crop, fade, Ken Burns) og `GET /api/timelapse/frames?device_id=...&start=...&day_night=day`.

## 6. Autentificering og RBAC

Fuld auth med JWT, RBAC (roller), MFA — alle API-endpoints beskyttet. Aktuel implementering beskrevet i `RISK_ASSESSMENT_v10.md` (R02) og `ADMINISTRATORMANUAL_v10.md` (§11, §15).
