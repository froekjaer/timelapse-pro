# Codex - TimeLapse Pro risk assessment v7 og virtuel penetrationstest

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Status:** Pre-production LAB/R&D  
**Rammer:** SABSA, ISO 27001, IEC 62443, CRA, NIS2, GDPR.

## 1. Scope

Vurderingen daekker:

- Mac Mini Headend: FastAPI/uvicorn, PostgreSQL, nginx, Ollama, node-agent, storage.
- Edge: Orange Pi 4 Pro `TL-C87FF9587CA0` med Nikon Z30.
- Transport: HTTPS/API, SFTP, reverse SSH tunnel, update artifacts.
- UI: React admin/kunde UI, CMDB, GRC, updates, LAB.
- Public/lab: `https://timelapse.froekjaer.dk`.
- Kommende prod: `www.timelapse-pro.dk` og `backend.timelapse-pro.dk`.

Metoden er dokumentreview, kode-/konfigurationsreview og non-destruktiv virtuel penetrationstest. Der er ikke koert aggressiv scanning, brute force eller exploitforsog.

## 2. Status paa tidligere assessments

| Tidligere finding | Codex-status | Kommentar |
|---|---|---|
| R01 SFTP data-adskillelse | Delvist/groen | SFTP chroot og per-site brugere findes; aktuel prod-evidens skal gemmes i GRC |
| R02 UI-adgangskontrol | Delvist | RBAC virker; MFA/WebAuthn enforcement mangler |
| R03 Hardware-historik | Groen | Camera/DeviceAssignment-model loeser fysisk edge-udskiftning |
| R04 Remote adgang | Groen | Reverse SSH tunnel findes; skal forblive debug-only og auditeret |
| R05 Kompromitteret Edge | Aaben | Diskkryptering, intern CA/mTLS og boot-hardening mangler |
| R06 Fejlet update til alle sites | Delvist/groen i lab | App artifact E2E virker; OS E2E paa aktiv Edge mangler |
| R07 Noeglekompromittering | Delvist | Key Management/HMAC findes; stale/legacy credentials skal ryddes |
| R08 MITM/API | Delvist | HTTPS/JWT/HMAC; CA-pinning/mTLS mangler |
| R09 Backup/restore | Aaben | Backup omtales; restore-test/evidence mangler |
| CMDB anonym adgang | Loest | `/api/cmdb/` kraever auth |
| OS bundle cross-release | Loest | Suite udledes fra OS/source metadata |
| Edge stale vist online | Delvist | CMDB list/detail er forbedret; alle UI-flader skal bruge freshness |
| Nikon Z30 config drift | Aaben | Focus, ISO, white balance og accepted-equivalent labels skal faerdiggoeres |
| Open WebUI rolle | Aaben | Beslut lab-only eller prod-komponent med RBAC/health/portmodel |
| Frontend lint | Aaben | Lint baseline er ikke prod-klar |
| Node-agent nede | Aaben | Mac Mini inventory bliver stale uden node-agent |
| GDPR evidence gap | Aaben | DPIA, retention, access logs og DPA mangler |

## 3. SABSA business attributes

| Attribute | Status | Vurdering |
|---|---|---|
| Availability | Gul | Headend og Edge virker i lab; node-agent/storage-preflight mangler |
| Integrity | Gul | Signed app artifact virker; OS update evidence mangler |
| Confidentiality | Gul | RBAC og CMDB-auth virker; secrets og MFA er ikke modne nok |
| Accountability | Gul | Change tickets og auditfelter findes; fuld evidence chain mangler |
| Authenticity | Gul | HMAC findes; mTLS/intern CA og stale cleanup mangler |
| Manageability | Groen | Global Config, CMDB, LAB og update UI giver god driftsevne |
| Continuity | Gul | Edge buffer og rollback findes; restore-test mangler |
| Auditability | Gul | GRC-dashboard findes, men evidence freshness er ujævn |
| Privacy | Gul/roed | GDPR-grundlag mangler foer kundeproduktion |

## 4. Opdateret risikoregister

| ID | Risiko | Score | Status | Primær behandling |
|---|---|---:|---|---|
| R01 | SFTP data laek/lateral movement | 4 | Lav | Gem aktuel chroot-evidens |
| R02 | Uautoriseret admin UI | 8 | Medium | MFA/WebAuthn for admin/high-risk |
| R03 | Hardwaretab bryder historik | 3 | Lav | Bevar Camera/DeviceAssignment model |
| R04 | Manglende remote adgang | 4 | Lav | Tunnel debug-only, audit og deny-policy |
| R05 | Kompromitteret fysisk Edge | 12 | Hoj | mTLS/intern CA, disk encryption, credential rotation |
| R06 | Fejlet update i stor skala | 8 | Medium | Per-target status, staged rollout, OS E2E |
| R07 | Noeglekompromittering | 8 | Medium | Stale cleanup, GPG/key lifecycle, revocation |
| R08 | MITM/API manipulation | 8 | Medium | CA-pinning/mTLS, HMAC globalt |
| R09 | Backup/restore fejler | 12 | Hoj | Restore-test, RTO/RPO, offsite backup |
| R10 | SSH tunnel misbrug | 4 | Lav | Audit, restricted access, no always-on tunnel |
| R11 | AI hallucinerer tags | 9 | Medium | Cloud/Gemini ontologi, confidence, review |
| R12 | GDPR non-compliance | 16 | Kritisk | DPIA, retention, DPA, access logging |
| R13 | Headend paa public 80/443 | 12 | Hoj | Cloudflare Tunnel og loopback origin |
| R14 | CMDB inventory stale | 9 | Medium | Node-agent genstart og freshness-gating |
| R15 | Nikon Z30 fokus/config drift | 9 | Medium | Profilmapping, LAB-tests, accepted equivalents |

## 5. Virtuel penetrationstest

### Testede flader

| Flade | Status |
|---|---|
| `/api/health` | 200 uden auth, acceptabelt |
| `/api/cmdb/` | Skal give 401 uden login |
| `/api/admin/*` | Skal give 401 uden login |
| nginx 80/443 | Aktiv i lab, ikke prod-kompliant |
| FastAPI 127.0.0.1:8000 | Intern, acceptabel |
| Ollama 127.0.0.1:11434 | Intern, acceptabel |
| OpenWebUI 8080 | Skal ikke public; rolle uafklaret |
| SFTP | Skal ikke bruge 21/22; non-standard port med chroot |
| Reverse SSH | Debug-only, audited |

### Hovedfund

| ID | Prioritet | Finding | Handling |
|---|---|---|---|
| VPEN-CX-001 | P0 | Mac Headend lab-nginx ejer 80/443 | Flyt backend-origin til loopback/non-standard bag Cloudflare |
| VPEN-CX-002 | P0 | Backup/restore ikke bevist | Udfør restore-test og gem evidence |
| VPEN-CX-003 | P0 | GDPR-grundlag mangler | DPIA, retention, DPA, subprocessor-liste |
| VPEN-CX-004 | P1 | MFA/WebAuthn ikke enforced | Indfør for admin/high-risk |
| VPEN-CX-005 | P1 | Stale credentials | Migrer/revoker gamle edge credentials |
| VPEN-CX-006 | P1 | OS update E2E mangler paa aktiv Edge | Byg/sign/test OS artifact paa `TL-C87FF9587CA0` |
| VPEN-CX-007 | P2 | OpenWebUI rolle uklar | Lab-only eller prod-service med RBAC/health |
| VPEN-CX-008 | P2 | LocalStorage/token posture | Ryd/risikovurder foer prod |
| VPEN-CX-009 | P2 | Frontend lint-gaeld | Indfoer lint gate og triage |

## 6. Standardmapping

| Standard | Codex-vurdering |
|---|---|
| SABSA | God arkitekturretning; business attributes skal bindes til frisk evidence og risikoejere |
| ISO 27001 | Asset, access, logging og change controls findes delvist; formelt ISMS/risk treatment mangler |
| IEC 62443 | Edge/Headend kan modelleres som zones/conduits; secure update og identity skal styrkes |
| CRA | Secure update er paa vej; SBOM, lifecycle support og vulnerability process mangler |
| NIS2 | Relevans som leverandoer til kunder; continuity, incident handling og supply chain skal dokumenteres |
| GDPR | Ikke klar foer DPIA, retention, DPA, subprocessor-liste og access logs er paa plads |

## 7. Go/no-go

| Miljoe | Vurdering |
|---|---|
| LAB/R&D | Go |
| Foerste kontrollerede testsite | Naesten go, hvis backup/restore, Nikon LAB og node-agent lukkes |
| Internet-facing production | No-go pr. 2026-06-23 |
| `timelapse-pro.dk` backend | No-go indtil port/proxy, backup, GDPR og MFA/credentials er lukket |

