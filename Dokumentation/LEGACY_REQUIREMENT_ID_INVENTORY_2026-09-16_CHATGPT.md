# TimeLapse Pro — Legacy Requirement ID Inventory

**Dato:** 2026-09-16  
**Formål:** Bevar de 82 ID-bårne krav fra `KRAVREGISTER_og_STATUS_v10.md` som provenance, uden at genbruge det gamle dokuments implementeringsstatus som nutidig sandhed.

> Dette er et inventory, ikke et nyt autoritativt kravregister. Kolonnen “Arkæologi” beskriver kun kendt evolution. Nutidig implementation/runtime-status skal verificeres separat gennem Capability Map/GRC/evidence.

## Capture og billedhåndtering

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| CAP-001 | Edge tager automatiske timelapse-billeder | CURRENT kernecapability |
| CAP-002 | Store-and-forward ved netværksudfald | CURRENT |
| CAP-003 | Thumbnail generering ved upload | CURRENT feature; runtime verify separat |
| CAP-004 | Billedkvalitets-check (blur/QA) | CURRENT, senere udvidet med richer QA/drift |
| CAP-005 | AI-analyse og tagging | CURRENT, taggingfilosofi senere ændret/udvidet |
| CAP-006 | Thumbnail postprocessing | CURRENT feature; status verify |
| CAP-007 | Retention policy pr. kamera | CHANGED materially: tidlig auto-retention vs senere explicit-disposition/no-auto-delete direction |
| CAP-008 | Download/adgangslog pr. billede | CURRENT |
| CAP-009 | Sidecar JSON/XMP metadata | CURRENT provenance intent |
| CAP-010 | Relay-styring kamera-strøm | CURRENT; senere knyttet til HAL/service operations/safe teardown |

## Kundevendt UI

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| UI-001 | Billedgalleri med thumbnails | CURRENT |
| UI-002 | Lightbox med fuldt billede | CURRENT |
| UI-003 | Tag-søgning og filtrering | CURRENT |
| UI-004 | Danske tag-navne | CURRENT usability intent |
| UI-005 | QA badge alarm/afvigelse/OK | CURRENT, men statussemantik skal være ærlig |
| UI-006 | Blur-score visning | CURRENT |
| UI-007 | Tidszone-support | CURRENT; implementation detail may evolve |
| UI-008 | Kundelogin med RBAC | CURRENT |
| UI-009 | MFA/WebAuthn admin-login | CURRENT intent; konkrete authmekanismer evolved |
| UI-010 | Sløring/redaction workflow | CURRENT privacy capability; implementation status verify |
| UI-011 | Downloadbar timelapse-video | CURRENT; senere udvidet med reproducibility/master/evidence profiles |

## Admin UI

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| ADM-001 | CMDB med device-overblik | CURRENT |
| ADM-002 | Update management approve/reject/promote | CURRENT |
| ADM-003 | Key Management UI | CURRENT |
| ADM-004 | GRC/Compliance cockpit | CURRENT, senere væsentligt udvidet med regulatory intelligence/completeness |
| ADM-005 | Global Config med hierarki | CURRENT |
| ADM-006 | LAB mode / kamera-test | CURRENT development/maintenance capability |
| ADM-007 | Post-processing admin-job | CURRENT |
| ADM-008 | Backup UI | CURRENT, men backup-status er ikke restore-proof |
| ADM-009 | Edge image build | CURRENT; #242 gør reproducibility/provenance til vigtig invariant |
| ADM-010 | DPIA-template pr. kunde/site | CURRENT organisational capability; juridisk acceptance separat |
| ADM-011 | Rapporter pr. compliance-standard | CHANGED/expanded: må ikke kaldes fuld audit hvis kun partial mapping |
| ADM-012 | Revision pr. billede/download | CURRENT |
| ADM-013 | Billedhistorik følger logisk kamera-lokation ved Edge-udskiftning | CURRENT vigtig product invariant |

## Edge-management og update

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| UPD-001 | Policy-drevet hierarkisk update | CURRENT |
| UPD-002 | Scope global/kunde/site/kamera/device | CURRENT |
| UPD-003 | Edge opdateres via Headend, ikke direkte internet | CURRENT for production; direct git/apt SUPERSEDED/lab-only |
| UPD-004 | Verificerede update-artifacts | CURRENT; source/artifact/runtime provenance strengthened |
| UPD-005 | Signerede artifacts og change tickets | CURRENT |
| UPD-006 | Maskin- og menneskelæsbare change tickets | CURRENT |
| UPD-007 | UI change-ticket review/godkendelse | CURRENT; high-risk/step-up/customer context later refined |
| UPD-008 | Staged rollout R&D→staging→prod | CURRENT |
| UPD-009 | Automatisk rollback ved fejlet update | CURRENT intent; health/outcome gate now stricter |
| UPD-010 | Maintenance window og reboot policy | CURRENT; capture schedule skal indgå |
| UPD-011 | OS security vs functional separat | CURRENT |
| UPD-012 | Per-target deployment status | CURRENT; historic implementation had real rollup bugs |
| UPD-013 | Komplet update audit trail | CURRENT |
| UPD-014 | SBOM pr. release | CURRENT; broader component/dependency governance later expanded |
| UPD-015 | Edge bevarer drift under update | CURRENT resilience invariant |

## Provisioning og onboarding

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| PROV-001 | Zero/near-zero-touch Edge provisioning | CURRENT |
| PROV-002 | OS hardening/app-installation via Headend | CURRENT |
| PROV-003 | Device keys: generation/rotation/revocation | CURRENT; key ownership model later changed |
| PROV-004 | Kold/varm backup Headend | CURRENT/TARGET |
| PROV-005 | Backup + restore testet/dokumenteret | CURRENT; “backup without restore is assumption” strengthened |
| PROV-006 | WiFi-konfiguration i disk image | CURRENT feature, target-specific verify |
| PROV-007 | SSH-nøgler i disk image | CHANGED: later design says operational Edge private key owned/generated on Edge; do not blindly reapply old injection model |
| PROV-008 | Bootstrap token one-time/time-limited | CURRENT |
| PROV-009 | Multi-target build OP4Pro/OP-PC+/RPi4/RPi5/Jetson | CURRENT aspiration; actual support/reproducibility verify per target |

## Sikkerhed og compliance

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| SEC-001 | ISO 27001/NIS2/CRA/IEC 62443 targets | CURRENT; now also explicit applicability/completeness semantics |
| SEC-002 | Secrets ikke i Git | CURRENT |
| SEC-003 | Test gate før deploy | CURRENT; tests must distinguish unit/integration/runtime evidence |
| SEC-004 | RBAC | CURRENT; role model/details evolved |
| SEC-005 | JWT med kort levetid | CURRENT security intent, concrete TTL/algorithm/storage evolved |
| SEC-006 | HMAC request-signatur for device tokens | CURRENT unless later formally superseded; HMAC historically intended to remain alongside mTLS |
| SEC-007 | SFTP chroot isolation | CURRENT |
| SEC-008 | MFA/WebAuthn | CURRENT intent; actual mechanism/policy evolved |
| SEC-009 | Intern CA + client certs | OPEN/TARGET; verify current implementation before claiming control |
| SEC-010 | Disk encryption on Edge | OPEN/TARGET; evaluate against recovery constraints |
| SEC-011 | fail2ban | CURRENT hardening candidate/requirement; runtime verify |
| SEC-012 | DPIA and GDPR evidence | CURRENT |
| SEC-013 | Incident response procedure | CURRENT; procedure must be exercised, not just written |
| SEC-014 | Vulnerability/CVE process | CURRENT; operational evidence needed |

## Konfiguration og arkitektur

| Legacy ID | Krav/ønske | Arkæologi |
|---|---|---|
| CFG-001 | Hierarkisk config global→kunde→site→kamera | CURRENT; Runtime/LAB is temporary fifth layer |
| CFG-002 | Effective config med provenance pr. felt | CURRENT |
| CFG-003 | Config UI med farvemarkering | CURRENT usability aid |
| CFG-004 | Kamera-lokation adskilt fra fysisk Edge | CURRENT |
| CFG-005 | Reverse SSH tunnel | CURRENT remote-management mechanism, not sole recovery path |
| CFG-006 | Bluetooth PAN management | CURRENT as one transport, not exclusive reachability model |
| CFG-007 | GPS tidssynkronisering | CURRENT capability component; newer physical evidence says GPS/chrony works on current Edges |
| CFG-008 | Web terminal | CURRENT capability, implementation evolved into multiple paths; #239 physical acceptance pending |
| CFG-009 | Lokal management UI på Edge | CURRENT and strengthened to local-first recovery across permitted transports |
| CFG-010 | Storage single source of truth | CURRENT architecture hygiene intent |

## Summary

The historical register contains **82 stable legacy IDs** across seven categories. They remain valuable references, but several status/solution statements are now stale.

Most important known material evolutions:

1. `CAP-007` retention: automatic cleanup → explicit disposition / no ordinary automatic project-data deletion.
2. `UPD-003`: direct Git/Internet update paths → Headend-mediated signed artifacts for production.
3. `PROV-003/007`: Headend-held/injected Edge key concepts → Edge ownership of operational private identity.
4. `CFG-006/009`: Bluetooth management → broader path-independent local management/recovery; BT-PAN is one transport.
5. `CFG-008`: “web terminal missing” → multiple terminal/recovery paths, with usability and physical acceptance as capability criteria.
6. `SEC-005/008`: original JWT/MFA/WebAuthn detail → policy-driven/evolving auth while preserving stronger admin/high-risk authentication intent.
7. `ADM-011/SEC-001`: compliance reports → explicit distinction between partial mapping, tested, assessed and certified; complete applicable-control accounting desired.
8. `ADM-009/PROV-009`: image builder exists → artifact/source provenance and reproducibility now explicit requirements after physical audit evidence.

Use the legacy IDs for provenance, not as proof of current status.