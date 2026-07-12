# User Guide — Site-Wide Look Matching

**Version:** 1.0
**Last Updated:** 2026-07-12
**Audience:** Camera Operators, Site Managers

---

## What is Site-Wide Look Matching?

Site-Wide Look Matching ensures that all cameras on your site produce videos with the same colors and brightness. This means you can cut between different camera angles without viewers noticing any difference.

### Why This Matters

**Before Site-Wide Look Matching:**
- Camera A (Nikon Z30) produces warm, vibrant images
- Camera B (Canon EOS 2000D) produces cool, neutral images
- Result: Jarring color jumps when editing together

**After Site-Wide Look Matching:**
- All cameras automatically match to a "golden reference"
- Result: Seamless transitions between camera angles

---

## How It Works

```
1. First camera takes a great shot
   └─> Becomes "Site Reference" (if quality score ≥ 75%)

2. Other cameras analyze their own shots
   └─> System calculates what makes them different
   └─> Creates a "Look-Up Table" (LUT) for each camera

3. Future shots apply the LUT
   └─> All cameras now match the reference look!

4. System suggests camera settings
   └─> "Try White Balance 5600K, EV -0.15"
   └─> Helps future shots match even better
```

---

## Using the Interface

### Finding Site-Wide Look Matching

1. Navigate to **DevicePage**
2. Look for **SiteLookCard** in the right column
3. You'll see one of these states:

#### State 1: No Reference Yet ⚠️

```
⚠️ Mangler Site Reference
Kameraer arbejder uafhængigt - videoer kan have forskellig look

[ Opret Site Reference ]
```

**What to do:** Take a high-quality shot during good lighting conditions. The system will automatically create a reference if quality is high enough.

#### State 2: Reference Active ✅

```
✅ Site Reference Aktiv
Alle kameraer matcher til fælles reference

🎯 Site Reference Info
Site ID: construction-site-1
Oprettet af: Nikon Z30
Kvalitetsscore: 92.5%
Picture Control: Flat

✨ Kamera LUT (Look Matching)
Match kvalitet: 87%
Eksponering offset: -0.15 EV
Saturation multiplier: 1.08x
Picture Control hint: Neutral

👁 Capture Hints (Næste optagelse)
Picture Control: ⚖️ Neutral
White Balance hint: 5600K
Eksponering hint: -0.15 EV

[ Regenerer Kamera LUT ]
```

---

## Understanding the Display

### Reference Info Section

| Field | Meaning |
|-------|---------|
| **Site ID** | Your site identifier |
| **Oprettet af** | Which camera took the reference shot |
| **Kvalitetsscore** | How good the reference is (higher = better) |
| **Picture Control** | Camera picture style used |

### LUT Section

| Field | Meaning |
|-------|---------|
| **Match kvalitet** | How well this camera matches (≥90% excellent) |
| **Eksponering offset** | Brightness difference from reference |
| **Saturation multiplier** | Color intensity adjustment |
| **Picture Control hint** | Recommended camera setting |

### Capture Hints Section

These are **suggestions** for your next shot:

| Hint | What to Do |
|------|------------|
| **Picture Control: Neutral** | Set camera to Neutral/Flat mode |
| **WB hint: 5600K** | Set white balance to 5600 Kelvin |
| **EV hint: -0.15** | Reduce exposure slightly |

---

## Camera-Specific Tips

### Nikon Z30 Users

**Best Picture Control for Timelapse: FLAT 🎬**

The **Flat** picture control gives you:
- Maximum dynamic range (bright and dark details)
- Best material for color matching
- Most flexibility in post-processing

**How to Set:**
1. Press camera's **i** button
2. Select **Picture Control**
3. Choose **Flat**
4. Adjust parameters if needed:
   - Sharpening: 3
   - Contrast: 0
   - Saturation: 0

**Alternative:** Standard mode is fine if Flat isn't available.

### Canon EOS 1300D/2000D Users

**Best Picture Style for Timelapse: NEUTRAL ⚖️**

The **Neutral** picture style gives you:
- Maximum dynamic range
- Best color matching performance
- Minimal in-camera processing

**How to Set:**
1. Press camera's **Q** button
2. Select **Picture Style**
3. Choose **Neutral**
4. Adjust parameters if needed:
   - Sharpness: 2
   - Contrast: 1
   - Saturation: 1

**Alternative:** Faithful mode is second-best.

---

## Best Practices

### For Creating Good References

✅ **DO:**
- Take reference shots during good lighting (not midday harsh sun)
- Use Flat/Neutral picture control
- Ensure scene is representative (not a temporary condition)
- Wait for stable weather (not changing rapidly)

❌ **DON'T:**
- Use shots with harsh shadows or blown-out highlights
- Use shots from temporary conditions (cloud bursts, unusual lighting)
- Use shots with incorrect white balance
- Rush the reference creation

### For Consistent Results

✅ **DO:**
- Keep white balance consistent (use manual Kelvin if possible)
- Use similar Picture Controls on all cameras
- Position cameras to have similar lighting
- Check match quality scores regularly

❌ **DON'T:**
- Mix indoor and outdoor without separate references
- Let cameras use auto white balance differently
- Ignore low match quality warnings
- Assume cameras will match in all conditions

---

## Troubleshooting

### "No Site Reference" Message

**Problem:** System hasn't created a reference yet.

**Solutions:**
1. Take a new shot during good lighting
2. Check quality score in QualityCard (must be ≥75%)
3. Ensure Picture Control is set to Flat/Neutral
4. Try again with better lighting if needed

### Low Match Quality (<75%)

**Problem:** Your camera doesn't match the reference well.

**Solutions:**
1. Check your lighting — is it similar to reference camera?
2. Verify white balance matches (use same Kelvin value)
3. Try the suggested Picture Control
4. Consider repositioning camera for similar lighting
5. In extreme cases, create a new reference

### Camera Hints Not Applied

**Problem:** Suggested settings aren't being used.

**Solutions:**
1. These are **suggestions** — apply them manually to your camera
2. Check if camera supports the suggested Picture Control
3. For Nikon: Flat is fully supported
4. For Canon: Most styles supported, some parameters limited

---

## FAQ

### Q: Will this slow down my camera?

**A:** No. All processing happens after the shot is complete, and takes less than 200ms. Your capture interval is unaffected.

### Q: Can I have different references for indoor vs outdoor?

**A:** Currently, no. You have one reference per site. Future versions may support multiple references.

### Q: What happens if I disable the feature?

**A:** Each camera goes back to independent operation. Existing references are preserved but unused.

### Q: How often should I regenerate LUTs?

**A:** The system does this automatically every 7 days. You can also do it manually via the "Regenerer Kamera LUT" button.

### Q: Can I mix Nikon and Canon cameras?

**A:** Yes! This is exactly what the feature is designed for. Nikon and Canon cameras will produce matching output.

### Q: What if conditions change (season, new lighting)?

**A:** LUTs handle moderate changes. For major changes, consider manually creating a new reference.

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────┐
│          SITE-WIDE LOOK MATCHING                │
├─────────────────────────────────────────────────┤
│                                                  │
│  CREATE REFERENCE:                              │
│  • Good lighting (not harsh midday)             │
│  • Picture Control: Flat/Neutral                │
│  • Quality score ≥ 75%                          │
│                                                  │
│  BEST SETTINGS:                                  │
│  • Nikon Z30: Flat (sharpening=3, contrast=0)    │
│  • Canon EOS: Neutral (sharpness=2, contrast=1) │
│                                                  │
│  MATCH QUALITY:                                  │
│  • ≥90%: Excellent ✅                            │
│  • ≥75%: Good 🔵                                 │
│  • <75%: Needs attention ⚠️                      │
│                                                  │
│  WHITE BALANCE:                                  │
│  • Use manual Kelvin (not auto)                 │
│  • Match across cameras (e.g., 5600K)           │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Getting Help

If you need assistance:

1. **Check the status cards** — They show detailed quality information
2. **Review your settings** — Ensure Picture Control matches recommendations
3. **Consult your admin** — They can adjust configuration if needed
4. **See admin guide** — For advanced configuration options

---

## Tips from the Field

### Construction Sites
> "Take your reference shot during the 'golden hour' (first hour after sunrise or last before sunset). The soft, even lighting gives the best results for all-day matching." — Field Technician

### Indoor Settings
> "For indoor sites, ensure all cameras have similar artificial lighting. Mixing natural and artificial light on different cameras makes matching difficult." — Site Manager

### Seasonal Changes
> "When seasons change significantly (summer to winter), consider creating a new reference. The color temperature of natural light changes throughout the year." — Senior Operator

---

**Remember:** Site-Wide Look Matching is designed to be automatic. Once enabled, it works in the background to ensure consistent quality across all your cameras.
