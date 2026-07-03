# Codex - TimeLapse Pro kravregister, status og tidslinje

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Status:** Pre-production samlet kravoverblik.

## 1. Produktvision

TimeLapse Pro skal dokumentere byggepladser over tid med:

- robuste Edge-kameraer
- lokal buffer og autonom capture
- Headend-styret konfiguration og update-flow
- kundevendt galleri, tags, search og timelapse-output
- admin UI til CMDB, GRC, backup, update og LAB
- dokumenteret security/compliance efter SABSA, ISO 27001, IEC 62443, CRA, NIS2 og GDPR.

## 2. Kravregister

| ID | Krav | Status | Mangler |
|---|---|---|---|
| CAP-001 | Automatisk capture paa Edge | Implementeret | Nikon Z30 tuning |
| CAP-002 | Store-and-forward ved netvaerksudfald | Implementeret | Driftstest over laengere periode |
| CAP-003 | Thumbnail ved upload | Delvist | Robust postprocessing af manglende thumbnails |
| CAP-004 | Billedkvalitet: blur/lys/eksponering | Delvist | Edge CV-quality pipeline modnes |
| CAP-005 | AI-tags og soegning | Delvist | Cloud/Gemini ontologi, confidence, review |
| CAP-006 | Timelapse-video eksport | Mangler/delvist | UI/FFmpeg workflow og quality filters |
| CAP-007 | Retention pr. kamera | Mangler | GDPR-kritisk |
| UI-001 | Kundegalleri og lightbox | Implementeret | Performance/backfill QA |
| UI-002 | Dansk visning af engelske canonical tags | Implementeret | Kunde-redigerbar oversaettelsestabel |
| UI-003 | Kundelogin og RBAC | Delvist | MFA/WebAuthn og token posture |
| UI-004 | Compliance-rapporter pr. standard | Delvist | Evidence links og rapportgenerator |
| ADM-001 | CMDB device/software inventory | Delvist | Node-agent friskhed, installed/latest version komplet |
| ADM-002 | GRC dashboard | Delvist | Click-through, quantitative risk, evidence freshness |
| ADM-003 | Backup UI | Delvist | Edge backup og restore-test evidence |
| ADM-004 | Edge image build/download | Implementeret | UI QA og image signing/evidence |
| ADM-005 | Global Config 4 lag | Implementeret | Flere parametre og inherited/current UX polish |
| CFG-001 | Kamera-lokation adskilt fra fysisk Edge | Implementeret | Binding flow skal QA-testes ved ny edge |
| CFG-002 | Nikon Z30 profil | Delvist | Remote focus, focus slice, video stream, accepted labels |
| UPD-001 | Edge maa ikke bruge direkte Internet/GitHub/apt | Implementeret som princip | Legacy paths skal lab-only og kontrolleres |
| UPD-002 | App artifacts signeres og deployes fra Headend | Delvist/implementeret i lab | Production signing og per-target evidence |
| UPD-003 | OS security/functional offline bundles | Delvist | OS E2E paa aktiv Edge |
| UPD-004 | Lab -> staging -> prod promotion | Delvist | Gates og customer/site/camera scopes |
| UPD-005 | Change tickets | Delvist | Signeret approval, MFA-context, kundeaccept |
| UPD-006 | SBOM | Delvist | Auto-generering og binding til artifacts |
| SEC-001 | RBAC | Implementeret | MFA enforcement |
| SEC-002 | HMAC device auth | Delvist | Global rollout og stale cleanup |
| SEC-003 | Intern CA/mTLS | Mangler | IEC 62443/CRA-hardening |
| SEC-004 | Backup/restore | Mangler/delvist | Restore-test, RTO/RPO, offsite |
| SEC-005 | GDPR DPIA/retention/DPA | Mangler | Blocker for kundeproduktion |
| SEC-006 | Incident response | Mangler | GDPR 72t procedure |
| NET-001 | Ikke bruge 80/443/21/22/8080 paa Mac Headend-origin | Mangler i lab | Cloudflare Tunnel og origin port 18443 |
| WEB-001 | Public website `www.timelapse-pro.dk` | Implementeret statisk draft | Hosting og endelig tekst/brand QA |
| WEB-002 | Login redirect til backend | Implementeret i draft | Backend domain go-live |

## 3. Hvad er bygget

- FastAPI Headend og React UI.
- PostgreSQL-baseret datamodel.
- Capture/upload fra aktiv Edge.
- CMDB, Key Management, updates, GRC og LAB-sider.
- App artifact E2E-test paa `TL-C87FF9587CA0`.
- Global Config med arv: global -> kunde -> site -> kamera.
- Kamera-lokation og DeviceAssignment-model.
- Nikon Z30 profil som ny retning.
- Edge image build og statisk website-map.
- Dokumenteret go-live gate og portplan i Codex-dokumenter.

## 4. Hvad mangler foer production

P0:

1. Port-/proxy-migration til Cloudflare Tunnel og non-standard Headend-origin.
2. Backup + restore-test med evidence.
3. GDPR DPIA, retention og databehandlergrundlag.
4. Node-agent og frisk Headend CMDB inventory.
5. Stale credential cleanup og HMAC globalt.

P1:

1. MFA/WebAuthn for admin/high-risk.
2. OS offline update E2E paa aktiv Edge.
3. Nikon Z30 focus/video/LAB faerdiggoerelse.
4. Per-target update status i UI.
5. Frontend lint/test gate.

P2:

1. Cloud AI/tag ontologi og dansk oversaettelsestabel.
2. GRC rapportgenerator pr. standard.
3. Incident response og vulnerability handling.
4. Edge disk encryption.
5. Multi-headend/customer-owned headend governance.

## 5. Tidslinje

| Periode | Leverance/status |
|---|---|
| Apr 2026 | Grund-MVP: capture, SFTP, UI, database, edge |
| Maj 2026 | SABSA/RBAC/reverse SSH/CMDB/update governance paabegyndt |
| Start juni 2026 | Mac Headend, update-flow, portkonflikt, OpenWebUI/Ollama, thumbnails |
| Midt juni 2026 | Offline artifact model, OS bundle, HMAC, GRC, backup/image build |
| 21 juni 2026 | App update E2E paa aktiv Edge dokumenteret |
| 22 juni 2026 | Global Config, kamera-binding, Nikon Z30 LAB profil |
| 23 juni 2026 | Codex risk/krav/go-live/port/manual dokumentsaet og website draft |

## 6. Anbefalet roadmap

| Fase | Indhold | Estimat |
|---|---|---|
| Pre-Internet gate | Ports, Cloudflare Tunnel, backup/restore, node-agent, GDPR minimum | 2-4 uger |
| Site readiness | Nikon Z30, LAB video/fokus, update E2E, CMDB freshness | 2-3 uger |
| Customer readiness | MFA, DPA, retention, reporting, support/runbooks | 3-5 uger |
| Scale readiness | Multi-headend, CRA package, GRC automation, AI governance | 2-3 maaneder |

