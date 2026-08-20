# TimeLapse Pro — Edge Node Runbook (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Konsoliderer:** `TimeLapse_Edge_Runbook_v2.docx`…`_v7.docx` (arkiveret i `Gamle versioner/`). v7 er backbone.

> **Note:** Kommandoer nedenfor stammer fra Canon/lab-æraen (edge SQLite `/data/timelapse_edge.db`, headend på 192.168.86.132). Aktivt kamera er nu Nikon Z30; se `ADMINISTRATORMANUAL_v10.md` for headend-siden.

## 1. Daglig drift

```bash
# Service status + live log
sudo systemctl status timelapse-edge
journalctl -u timelapse-edge -f

# Unsynced captures / seneste capture / diskforbrug / shutter-tæller
sqlite3 /data/timelapse_edge.db "SELECT COUNT(*) FROM captures WHERE synced_to_headend=0;"
sqlite3 /data/timelapse_edge.db "SELECT MAX(captured_at) FROM captures;"
df -h /data && du -sh /data/captures/
sqlite3 /data/timelapse_edge.db "SELECT cam_shutter_cnt, cam_shutter_pct FROM diagnostics ORDER BY recorded_at DESC LIMIT 1;"
```

## 2. Deploy og opdatering

Deploy sker automatisk: Push → GitHub Actions → poller → edge self-update inden for 5 min. Nød-deploy:

```bash
cd /opt/timelapse && git pull origin main
find edge -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
sudo systemctl restart timelapse-edge
```

> Production-regel (aktuel): Edge må IKKE bruge direkte GitHub/Internet/apt — updates skal gå via Headend-medieret offline artifact (se `ADMINISTRATORMANUAL_v10.md` §7). Ovenstående git-pull er lab-only/nød.

## 3. USB-symlinks

```bash
ls -la /dev/cam*
sudo udevadm control --reload-rules && sudo udevadm trigger
gphoto2 --auto-detect
gphoto2 --port usb: --summary 2>&1 | head -5
```

## 4. Backup og restore

Backup via Web UI anbefales (pull-arkitektur — ingen inbound SSH til edge). Manuel:

```bash
BACKUP_FILE="/tmp/edge_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf $BACKUP_FILE /data/timelapse_edge.db /opt/timelapse/edge/ /etc/systemd/system/timelapse-edge.service
sftp sftp_test@<headend>:/incoming/_backups/TL-XXX/ <<< "put $BACKUP_FILE"
```

Restore: SSH til edge → `sudo systemctl stop timelapse-edge` → hent backup (scp) → `tar -xzf ... -C /` → `sudo systemctl start timelapse-edge` → verificér i journalctl.

## 5. Fejlfinding

Kamera: verificér relæ tændt + `gphoto2 --auto-detect`. Netværk:

```bash
nmcli device status
ping -c 3 <headend>
sftp <sftp-bruger>@<headend> <<< 'ls /incoming/' 2>&1 | head -5
curl -s http://<headend>:8000/api/config/TL-XXX | python3 -m json.tool | head -10
```

## 6. Reverse SSH-provisioning

Reverse SSH (ED25519, autossh -R) med customer approval — teknikerens flow beskrevet i `ADMINISTRATORMANUAL_v10.md` (Edge-management) og `RISK_ASSESSMENT_v10.md` (R10/§14 Key Management).

**Opdatering 2026-08-20 (PR #73, SEC-ZAI-05/15):** Edge-enheden ejer selv sin operationelle SSH-identitet. Headend genererer, gemmer eller injicerer **ikke** længere Edge private keys — key-management er public-key-only for `entity_type=edge`, og legacy `Camera.ssh_private_key`-data er pensioneret fra alle aktive flows (410 Gone). Første legacy-konvergens skal sikre at enheden har/genererer sin egen nøgle **før** gamle escrow-data fjernes destruktivt. Browserterminal i UI'en (`/ssh-tunnel`) kræver at enhedens host identity er trusted/verified — ellers er den deaktiveret med begrundelse.
