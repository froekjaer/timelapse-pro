# WebRTC Live View — Test Guide

**Feature:** F-013 WebRTC Live View for LAB mode
**Version:** 1.0.0 | 13. juli 2026

---

## ✅ Implementation Status

| Component | Status | Note |
|-----------|--------|------|
| `edge/webrtc_server.py` | ✅ Complete | Fixed `VideoFrame.from_bytes()` bug |
| `edge/agent.py` | ✅ Complete | Start/stop + signaling |
| `headend/main.py` | ✅ Complete | REST signaling endpoints |
| `timelapse-ui/src/hooks/useWebRTC.ts` | ✅ Complete | Native RTCPeerConnection |
| `timelapse-ui/src/pages/LabPage.tsx` | ✅ Complete | Video element + toggle |

---

## 📦 Installation af Dependencies

### Edge (på device):
```bash
cd /path/to/edge
pip install aiortc av
```

### UI (ingen nye dependencies!)
WebRTC bruger native browser API - ingen npm pakker nødvendige.

---

## 🧪 Test Steps

### 1. Start LAB Mode
1. Åbn TimeLapse Pro UI
2. Gå til "LAB" mode
3. Klik "Start LAB mode" på en device
4. Vent på "LAB mode active" status

### 2. Aktivér WebRTC Live
1. Klik "WebRTC Live" knappen i preview panelet
2. UI viser "WebRTC forbindes..." indikator
3. Efter 2-5 sekunder vises live video

### 3. Test Real-time Fokus
1. Juster kamera fokus manuelt
2. **Verifikation:** Ændringer skal ses inden for 200ms (<1 sekund)
3. Sammenlign med "Preview loop" (3-4 sekunders forsinkelse)

### 4. Test Fallback
1. Stop WebRTC server på edge (kill process)
2. UI skal vise fejlbesked
3. Klik "WebRTC Live" igen → skal prøve at reconnect
4. Eller brug "Preview loop" som fallback

### 5. Test LAB Mode Stop
1. Stop LAB mode
2. WebRTC skal automatisk stoppe
3. Video element fjernes fra UI

---

## 🔍 Debugging

### WebRTC Server ikke startet?
Check edge logs:
```
grep -i webrtc /var/log/timelapse/agent.log
```

Forventet output:
```
WebRTC: Server started on port 8100
WebRTC: gphoto2 frame capture started
```

### Video viser ikke frames?
1. Check WebRTC health endpoint:
```bash
curl http://edge-device:8100/health
```

2. Check browser console for WebRTC errors:
```
[WebRTC] Connection state: ...
[WebRTC] Received track: video
```

### ICE connection failed?
1. Check STUN server er tilgængelig:
```bash
ping stun.l.google.com
```

2. I browser console, se efter:
```
[WebRTC] Connection state: failed
```

### gphoto2 capture fejler?
Check kamera forbindelse:
```bash
gphoto2 --capture-preview --filename /tmp/test.jpg
```

---

## 📊 Performance Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Latency** | <200ms | Juster fokus → tæl til visualisering |
| **Frame Rate** | 0.8-1.5 FPS | Tæl frames i 10 sekunder / 10 |
| **Connection Time** | <5 sek | Fra "WebRTC Live" klik til video |
| **Memory Leak** | 0 efter 10 min | Check edge RAM før/efter |

---

## 🐛 Kendte Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| ICE candidates not sent | ℹ️ Low | ICE included in SDP (works for LAN) |
| Requires aiortc on edge | ℹ️ By design | Fallback to polling if missing |
| gphoto2 frame rate limit | ℹ️ Hardware limit | 0.8-1.5 FPS is normal |

---

## ✅ Verification Checklist

- [ ] WebRTC server starter når LAB mode aktiveres
- [ ] UI viser `<video>` element med live stream
- [ ] Fokus ændringer ses med det samme (<200ms)
- [ ] "WebRTC Live" knap skifter til aktiv state
- [ ] Video stopper når LAB mode stoppes
- [ ] Fallback til "Preview loop" virker
- [ ] Ingen memory leaks efter 10+ minutter streaming
- [ ] Browser console ingen errors (kun warnings ok)

---

## 🚀 Go-Live Decision

**Ready for production when:**
- ✅ All verification checks pass
- ✅ Dependencies (aiortc, av) dokumenteret i requirements
- ✅ Fallback til polling testet og virker

**Risk Level:** 🟢 Low
- WebRTC er optional feature
- Fallback til eksisterende polling mechanism
- Kun aktiv i LAB mode (kortvarige sessions)

---

## 📝 Notes til udvikling

**Fixet i denne version:**
- `VideoFrame.from_bytes()` → korrekt PyAV API med `av.CodecContext.create('mjpeg', 'r')`

**Fremtidige forbedringer:**
- [ ] Send ICE candidates separately (not just in SDP)
- [ ] Add TURN server for WAN scenarios
- [ ] Optimize frame rate with gphoto2 --capture-tethered
