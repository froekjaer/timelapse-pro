# Site-Wide Look Matching System

## Overblik

Site-Wide Look Matching sikrer at alle kameraer på et site kan producere timelapse videoer med konsistent look (farver, eksponering, etc.) der kan klippes sammen uden synlige forskelle.

## Arkitektur

```
┌─────────────────────────────────────────────────────────────────┐
│                     Site Reference Frame                        │
│  - "Golden reference" look for hele site                       │
│  - Oprettet fra første høj-kvalitet capture (score >= 75%)     │
│  - Gemmer LAB mean/std, HSV stats, WB, Picture Control        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Per-Kamera LUTs                               │
│  - Analyserer kamera vs reference                               │
│  - Genererer color matrix, EV offset, sat multiplier            │
│  - Picture Control hints (Nikon Flat/Standard, Canon Neutral)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Video Rendering Pipeline                        │
│  - Render alle videoer med fælles look                          │
│  - LUT anvendt til color matching                               │
│  - Resultat: Konsistente videoer på tværs af kameraer            │
└─────────────────────────────────────────────────────────────────┘
```

## Komponenter

### 1. SiteLookManager (`edge/ai/site_look_manager.py`)

Core motor for site-wide look matching:

- `SiteReferenceFrame`: Golden reference datastruktur
- `CameraLUT`: Per-kamera look-up table
- `create_reference_from_capture()`: Opret reference fra høj-kvalitet capture
- `generate_camera_lut()`: Generer LUT for kamera matching
- `get_capture_hints()`: Få kamera kommando hints

### 2. AutonomousImageOptimizer Integration

`edge/ai/autonomous_optimizer.py` er automatisk integreret med SiteLookManager:

- Kører automatisk efter hver capture
- Opretter reference hvis kvaliteten er høj nok
- Genererer/updaterer LUT for kameraet
- Returnerer capture hints til UI

### 3. UI Komponenter

- `SiteLookCard.tsx`: Viser site look matching status
  - Reference status (aktiv/mangler)
  - LUT info (match quality, EV offset, saturation)
  - Capture hints (WB, Picture Control)
  - Kamera-specifikke anbefalinger

## Kamera-Specificke Features

### Nikon Z30

**Picture Controls:**
- **Flat** (Anbefalet til timelapse): Maksimalt dynamisk område, minimal processing
- **Standard**: God out-of-camera kvalitet, passende til de fleste scener
- **Neutral**: Fladere profil med lavere kontrast/saturation
- **Vivid**: Øget saturation og kontrast
- **Landscape**: Optimeret til himmel og vegetation
- **Portrait**: Optimeret til hudtoner

**Parametre (sharpening, contrast, brightness, saturation, hue):**
- Flat: `sharpening=3, contrast=0, brightness=0, saturation=0, hue=0`
- Standard: `sharpening=4, contrast=1, brightness=0, saturation=0, hue=0`

### Canon EOS 1300D/2000D

**Picture Styles:**
- **Neutral** (Anbefalet til timelapse): Maksimalt dynamisk område
- **Standard**: God out-of-camera kvalitet
- **Faithful**: Nøjagtig farvegengivelse
- **Landscape**: Dybere blå/grønne toner
- **Portrait**: Blødere toner til hud

**Parametre (sharpness, contrast, saturation, color tone):**
- Neutral: `sharpness=2, contrast=1, saturation=1, color_tone=0`
- Standard: `sharpness=3, contrast=2, saturation=2, color_tone=0`

## Konfiguration

Aktiver site-wide look matching i `config.yaml`:

```yaml
# Site-wide look matching (enabled by default)
site_look_matching:
  enabled: true

# Storage path for reference frames and LUTs
site_look_storage_path: "/data/timelapse/site_looks"
```

## API Output

`autonomous_optimizer` analyse inkluderer nu `site_look_matching` data:

```json
{
  "site_look_matching": {
    "enabled": true,
    "has_site_reference": true,
    "is_site_reference": false,
    "lut_generated": true,
    "reference_info": {
      "site_id": "construction-site-1",
      "created_at": "2026-07-11T12:34:56Z",
      "created_by_camera": "Nikon Z30",
      "quality_score": 92.5,
      "scene_type": "day",
      "picture_control": "Flat"
    },
    "lut_info": {
      "camera_model": "Canon EOS 2000D",
      "match_quality": 0.87,
      "exposure_offset_ev": -0.15,
      "saturation_multiplier": 1.08,
      "picture_control_hint": "Neutral"
    },
    "capture_hints": {
      "has_reference": true,
      "picture_control": "Neutral",
      "wb_kelvin_hint": 5600,
      "ev_hint": -0.15,
      "match_quality": 0.87
    }
  }
}
```

## Kvalitetskrav for Reference

Et billede kan kun blive site reference hvis:

- Quality score >= 75%
- Ingen signifikant clipping (highlights < 3%, shadows < 5%)
- God sharpness (blur score >= threshold)

## Match Quality

Match quality score (0-1) indikerer hvor tæt kameraet er på reference:

- **>= 0.90**: Fremragende match (næsten usynlig forskel)
- **>= 0.75**: God match (minimal forskel)
- **>= 0.60**: Brugbar match (let korrigering i post)
- **< 0.60**: Lav match (kræver manuel justering)

## Video Rendering Pipeline

TODO: Implementer rendering med LUT anvendt:

```python
from edge.ai.site_look_manager import SiteLookManager

manager = SiteLookManager(config)
lut = manager.get_camera_lut(site_id, camera_id)

if lut:
    # Apply LUT to each frame during video rendering
    lut.apply_to_image(input_frame, output_frame)
```

## Fremtidige Forbedringer

- [ ] GPU-accelerated LUT application (CUDA/OpenCL)
- [ ] 3D LUT interpolation for bedre accuracy
- [ ] Time-of-day based references (golden hour, overcast, night)
- [ ] Per-scene LUTs (indendørs vs udendørs)
- [ ] CIEDE2000 color difference for bedre match evaluation
- [ ] Automated reference rotation (daglige ugentlige opdateringer)

## Troubleshooting

**Ingen site reference oprettet:**
- Tjek at quality score er >= 75%
- Tjek at der ikke er clipping i billedet
- Se edge logs for fejlmeddelelser

**Lut match quality er lav:**
- Tjek at kameraet har samme lysforhold som reference
- Verificer at white balance er korrekt indstillet
- Overvej at oprette ny reference under bedre forhold

**Capture hints virker ikke:**
- Tjek at Picture Control er supporteret af kameraet
- Verificer at kamera kommandoer er tilladt (allow_camera_commands)
- Se edge logs for gphoto2 fejl
