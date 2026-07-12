# Admin Guide — Site-Wide Look Matching

**Version:** 1.0
**Last Updated:** 2026-07-12
**Audience:** System Administrators, Technical Staff

---

## Overview

Site-Wide Look Matching is a **production-ready feature** that ensures color consistency across all cameras on a site. This guide covers deployment, configuration, monitoring, and troubleshooting.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Golden Reference** | Site-wide color standard from a high-quality capture |
| **Camera LUT** | Per-camera color transformation to match reference |
| **Quality Threshold** | Minimum score (75%) for reference creation |
| **Match Quality** | Score (0-100%) indicating how well camera matches reference |

---

## Deployment

### Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.8 | 3.10+ |
| OpenCV | 4.0 | 4.5+ |
| NumPy | 1.20 | 1.23+ |
| Disk Space | 100 MB per site | 500 MB buffer |
| CPU | Any | Multi-core preferred |

### Installation

1. **Verify dependencies:**
   ```bash
   # On edge node
   pip list | grep opencv
   pip list | grep numpy
   ```

2. **Create storage directory:**
   ```bash
   sudo mkdir -p /var/lib/timelapse/site_looks
   sudo chown timelapse:timelapse /var/lib/timelapse/site_looks
   sudo chmod 755 /var/lib/timelapse/site_looks
   ```

3. **Configure feature:**
   ```bash
   # Copy example config
   cp edge/config/site_look_config.example.yaml /etc/timelapse/site_look.yaml

   # Edit to your needs
   vi /etc/timelapse/site_look.yaml

   # Reference in main config
   vi /etc/timelapse/config.yaml
   # Add: site_look_config: /etc/timelapse/site_look.yaml
   ```

4. **Restart services:**
   ```bash
   sudo systemctl restart timelapse-edge
   ```

5. **Verify deployment:**
   ```bash
   # Check logs for successful initialization
   sudo journalctl -u timelapse-edge -n 50 | grep -i "site.look"
   ```

---

## Configuration

### Core Settings

```yaml
# /etc/timelapse/config.yaml
site_look_matching:
  # Feature toggle
  enabled: true

  # Storage path
  storage_path: "/var/lib/timelapse/site_looks"

  # Reference creation threshold
  reference_quality_threshold: 75.0  # 0-100

  # Automatic reference management
  auto_create_reference: true   # Auto-create from quality captures
  auto_update_reference: false  # Keep reference stable

  # LUT generation
  lut:
    auto_generate: true
    regeneration_interval_hours: 168  # 7 days
```

### Edge AI Policy

```yaml
edge_ai_policy:
  mode: "assist"  # off | monitor | assist | autonomous

  # Allow camera command hints
  allow_camera_commands: true
  allow_ev_autopilot: true
  allow_schedule_suggestions: true

  # Confidence floor for auto-apply
  confidence_floor: 0.70  # 70%
```

### Adaptive Exposure

```yaml
quality:
  adaptive_exposure:
    target_brightness: 118.0
    brightness_tolerance: 32.0
    step_ev: 0.3
    min_ev: -2.0
    max_ev: 2.0

  blur_threshold: 80.0
  dark_threshold: 25.0
  bright_threshold: 230.0
```

### Device-Level Overrides

```yaml
# device_config.yaml
device:
  device_id: "tlp-001"
  camera:
    # Nikon Z30 example
    model: "Nikon Z30"
    picture_control: "Flat"
    picture_control_parameters:
      sharpening: 3
      contrast: 0
      brightness: 0
      saturation: 0
      hue: 0
```

---

## Monitoring

### Health Checks

```bash
# Check reference exists
ls -la /var/lib/timelapse/site_looks/<site_id>/reference.json

# Check LUTs exist
ls -la /var/lib/timelapse/site_looks/<site_id>/luts/

# Check storage usage
du -sh /var/lib/timelapse/site_looks/
```

### API Endpoints

```bash
# Get site look status
curl http://edge-node:8080/api/quality/<device_id> | jq '.site_look_matching'

# Expected response:
{
  "site_look_matching": {
    "enabled": true,
    "has_site_reference": true,
    "is_site_reference": false,
    "lut_generated": true,
    "reference_info": {
      "site_id": "construction-site-1",
      "quality_score": 92.5
    },
    "lut_info": {
      "match_quality": 0.87
    }
  }
}
```

### Log Monitoring

```bash
# Real-time monitoring
sudo journalctl -u timelapse-edge -f | grep -i "site.look"

# Common log patterns:
# "SiteLookManager: Reference created"  ✅
# "SiteLookManager: LUT generated"      ✅
# "SiteLookManager: Quality below threshold"  ⚠️
# "SiteLookManager: Reference missing"        ❌
```

### Metrics to Monitor

| Metric | Healthy | Warning | Critical | Action |
|--------|---------|---------|----------|--------|
| Reference Quality | ≥85% | 75-85% | <75% | Consider new reference |
| Match Quality | ≥80% | 60-80% | <60% | Check camera conditions |
| Storage Usage | <1GB | 1-5GB | >5GB | Cleanup old data |
| Processing Time | <200ms | 200-500ms | >500ms | Check CPU load |

---

## Operations

### Manual Reference Creation

When automatic creation isn't suitable:

```bash
# Trigger via API
curl -X POST http://edge-node:8080/api/site-look/create-reference \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "construction-site-1",
    "device_id": "tlp-001",
    "capture_id": "latest"
  }'
```

### Reference Rotation

For seasonal changes or significant condition updates:

```bash
# 1. Backup current reference
cp /var/lib/timelapse/site_looks/<site_id>/reference.json \
   /var/lib/timelapse/site_looks/<site_id>/reference.json.backup

# 2. Take new capture with desired conditions

# 3. Create new reference (will auto-update if quality ≥ threshold)

# 4. LUTs will regenerate automatically
```

### Forced LUT Regeneration

```bash
# Via API
curl -X POST http://edge-node:8080/api/site-look/regenerate-lut \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "construction-site-1",
    "device_id": "tlp-002"
  }'
```

### Disabling the Feature

For troubleshooting or testing:

```bash
# Edit config
vi /etc/timelapse/config.yaml
# Set: site_look_matching.enabled: false

# Restart
sudo systemctl restart timelapse-edge

# Note: References are preserved but unused
```

---

## Backup & Recovery

### Backup Strategy

```bash
# Backup site look data
tar -czf site-look-backup-$(date +%Y%m%d).tar.gz \
    /var/lib/timelapse/site_looks/

# Restore
tar -xzf site-look-backup-20260712.tar.gz -C /
```

### Disaster Recovery

| Scenario | Recovery Time | Procedure |
|----------|---------------|-----------|
| Storage failure | <5 min | Restore from backup |
| Reference corruption | <10 min | Delete reference, auto-recreate |
| LUT corruption | <2 min | Auto-regenerates on next capture |
| Complete loss | <15 min | Restore backup + service restart |

---

## Troubleshooting

### Issue: Reference Not Created

**Symptoms:**
- `has_site_reference: false`
- "Mangler Site Reference" in UI
- No reference.json file

**Diagnosis:**
```bash
# Check capture quality
curl http://edge-node:8080/api/quality/<device_id> | jq '.quality_score'

# Check threshold
grep reference_quality_threshold /etc/timelapse/config.yaml

# Check logs
sudo journalctl -u timelapse-edge -n 100 | grep -i "reference"
```

**Solutions:**
1. Increase quality threshold temporarily: `reference_quality_threshold: 70.0`
2. Ensure camera is using Flat/Neutral picture control
3. Take capture during optimal lighting conditions
4. Verify no clipping in image (check quality metrics)

### Issue: Low Match Quality

**Symptoms:**
- `match_quality < 0.75`
- Visible differences between cameras
- "Low match quality" warning

**Diagnosis:**
```bash
# Check match quality per camera
for device in tlp-001 tlp-002 tlp-003; do
  echo "=== $device ==="
  curl http://edge-node:8080/api/quality/$device | \
    jq '.site_look_matching.lut_info.match_quality'
done

# Check camera conditions (lighting, WB)
```

**Solutions:**
1. Verify all cameras have similar lighting conditions
2. Ensure white balance is consistent (use manual Kelvin)
3. Check camera positioning for similar scene composition
4. Consider creating new reference under better conditions
5. For extreme differences, per-scene references may be needed (future feature)

### Issue: Storage Exhaustion

**Symptoms:**
- Disk space warnings
- Failed LUT writes
- "Storage full" errors

**Diagnosis:**
```bash
# Check usage
du -sh /var/lib/timelapse/site_looks/

# List references per site
find /var/lib/timelapse/site_looks/ -name "reference.json" | wc -l
```

**Solutions:**
1. Clean up old site data: `rm -rf /var/lib/timelapse/site_looks/<old_site>/`
2. Implement retention policy in config
3. Move storage to larger volume: update `storage_path`

### Issue: High CPU Usage

**Symptoms:**
- Slow captures
- High CPU during processing
- Processing timeout warnings

**Diagnosis:**
```bash
# Check CPU
top | grep python

# Check processing time
sudo journalctl -u timelapse-edge -n 100 | grep "processing"
```

**Solutions:**
1. Verify no other processes competing for CPU
2. Reduce capture frequency if needed
3. Consider GPU acceleration path (future)
4. Check for image processing bottlenecks

---

## Performance Tuning

### For High-Volume Sites

```yaml
# Reduce regeneration frequency
site_look_matching:
  lut:
    regeneration_interval_hours: 336  # 14 days

# Reduce quality threshold for faster reference creation
site_look_matching:
  reference_quality_threshold: 70.0  # Lower if acceptable

# Disable auto-update for stability
site_look_matching:
  auto_update_reference: false
```

### For Maximum Quality

```yaml
# Increase quality threshold
site_look_matching:
  reference_quality_threshold: 85.0  # Stricter

# Enable all hints
edge_ai_policy:
  allow_camera_commands: true
  allow_ev_autopilot: true

# Increase regeneration frequency
site_look_matching:
  lut:
    regeneration_interval_hours: 168  # Weekly
```

---

## Security Considerations

### File Permissions

```bash
# Recommended permissions
sudo chmod 755 /var/lib/timelapse/site_looks/
sudo chmod 644 /var/lib/timelapse/site_looks/*/reference.json
sudo chmod 644 /var/lib/timelapse/site_looks/*/luts/*.json
```

### API Access Control

Site look endpoints inherit authentication from technician UI:

- Admin: Full access (create, delete, modify)
- Technician: Read-only access
- Viewer: Read-only access

### Audit Logging

All site look operations are logged:

```bash
# View audit trail
sudo journalctl -u timelapse-edge --since "today" | grep -E "(reference|lut).*(created|deleted|modified)"
```

---

## Upgrading

### Version Compatibility

| Feature Version | Minimum Edge Version | Breaking Changes? |
|-----------------|----------------------|-------------------|
| 1.0 | 2.5.0 | No |

### Upgrade Procedure

```bash
# 1. Backup current state
tar -czf site-look-pre-upgrade.tar.gz /var/lib/timelapse/site_looks/

# 2. Stop service
sudo systemctl stop timelapse-edge

# 3. Update code
git pull origin main
pip install -r edge/requirements.txt

# 4. Start service
sudo systemctl start timelapse-edge

# 5. Verify
curl http://edge-node:8080/api/health | jq '.site_look_matching'
```

---

## Integration Examples

### Monitoring with Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'timelapse-edge'
    static_configs:
      - targets: ['edge-node:8080']
    metrics_path: '/api/metrics'
```

### Alerts with Alertmanager

```yaml
# alertmanager.yml
groups:
  - name: site_look
    rules:
      - alert: LowMatchQuality
        expr: site_look_match_quality < 0.75
        for: 10m
        annotations:
          summary: "Camera {{ $labels.device_id }} has low match quality"

      - alert: MissingReference
        expr: site_look_has_reference == 0
        for: 1h
        annotations:
          summary: "Site {{ $labels.site_id }} missing reference"
```

---

## Reference

### File Structure

```
/var/lib/timelapse/site_looks/
├── <site_id>/
│   ├── reference.json          # Golden reference frame
│   ├── luts/
│   │   ├── <camera_id>.json   # Per-camera LUT
│   │   └── ...
│   └── metadata.json           # Site metadata
```

### Reference JSON Schema

```json
{
  "site_id": "construction-site-1",
  "created_at": "2026-07-11T12:34:56Z",
  "created_by_camera": "Nikon Z30",
  "quality_score": 92.5,
  "scene_type": "day",
  "lab_mean": [45.2, 12.3, -8.5],
  "lab_std": [8.2, 5.1, 6.3],
  "hsv_stats": {...},
  "wb_kelvin": 5600,
  "picture_control": "Flat"
}
```

### LUT JSON Schema

```json
{
  "camera_id": "tlp-002",
  "camera_model": "Canon EOS 2000D",
  "generated_at": "2026-07-11T12:35:00Z",
  "reference_camera_id": "tlp-001",
  "match_quality": 0.87,
  "color_matrix": [[1.02, -0.01, 0.03], ...],
  "exposure_offset_ev": -0.15,
  "saturation_multiplier": 1.08,
  "wb_kelvin_offset": 50
}
```

---

## Appendix

### Command-Line Reference

```bash
# Service management
systemctl {start|stop|restart|status} timelapse-edge

# Log viewing
journalctl -u timelapse-edge -f
journalctl -u timelapse-edge --since "1 hour ago"

# File operations
ls -la /var/lib/timelapse/site_looks/
du -sh /var/lib/timelapse/site_looks/
find /var/lib/timelapse/site_looks/ -name "*.json"

# API testing
curl http://edge-node:8080/api/health
curl http://edge-node:8080/api/quality/<device_id> | jq '.'

# Backup/restore
tar -czf backup.tar.gz /var/lib/timelapse/site_looks/
tar -xzf backup.tar.gz -C /
```

### Support Contacts

| Issue Type | Contact |
|------------|---------|
| Bug Reports | tech-support@timelapse-pro.example |
| Configuration Issues | admin@timelapse-pro.example |
| Feature Requests | product@timelapse-pro.example |

---

**Document Version:** 1.0
**Last Updated:** 2026-07-12
**Next Review:** 2026-10-12
