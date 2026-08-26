# 05 — Compliance-vurdering mod "Regler og Standarder"

Grundlag: standardkataloget i `headend/compliance_intelligence.py` (som driver Compliance Cockpit → "Regler og Standarder"). Vurderingen er en **kode-forankret** gap-analyse, ikke en juridisk udtalelse (jf. 06-anbefaling: jurist ved første kommercielle site). Klassifikation: Opfyldt / Delvist / Gap / Ikke relevant nu.

## Kataloget (uddrag af det systemet selv erklærer relevant)

EU: GDPR, AI Act (+ AI Omnibus/Digital Omnibus-ændringer), CRA, NIS2 (+ dansk NIS 2-lov, ENISA NIS2-IR), Cybersecurity Act, Cyber Solidarity Act, Data Act, DORA, Critical Entities Resilience Directive. Standarder: ISO/IEC 27001:2022, ISO/IEC 42001 (AI mgmt), IEC 62443-serien, NIST CSF 2.0, NIST SP 800-82 Rev.3 (OT), NIST AI RMF. Andre jurisdiktioner (markedsdrevet): NERC CIP, FERC 887, GB/T 39204, AU SOCI/Cyber Security Act.

## Vurdering pr. domæne

| Standard/lov | Status | Evidens / gap (denne assessment) |
|---|---|---|
| **GDPR** | **Delvist** | Redaction/GDPR-sløring, retention-politik og DPIA-skabelon findes; **gap**: DPA-skabeloner mangler, controller/processor-rollen uafklaret (RR-09 i REVIEW-001), retention håndhæves af en usuperviseret tråd (TPA-11 — "stille manglende sletning" er en GDPR-risiko). Klassifikation af billeddata findes ikke som håndhævet mekanisme. |
| **CRA** | **Gap (blocker)** | **TPA-00 (default TOTP-secret)** er direkte CRA Annex I-overtrædelse. Secure-by-default brydes også af MD5-fingerprint (TPA-03, kosmetisk men audit-synligt) og manglende per-device-identitet (TPA-02). SBOM pr. release og struktureret vulnerability-håndtering er planlagt men ikke fundet aktivt. |
| **NIS2 / dansk NIS2** | **Delvist / forbered** | Operatøren selv er sandsynligvis under tærskel nu; fremtidige OT-kunder kan være i scope. Adgangsstyring/RBAC, logging/SIEM og incident-registrering findes. **Gap**: formel incident-response-procedure (R20 åben), leverandør-/supply chain-krav. |
| **IEC 62443** | **Delvist** | Zone/conduit-tankegang, JIT-tunnel, RBAC og signeret OTA er på plads. **Gap**: CR 1.5 (TPA-00), SL-T-fastsættelse pr. zone mangler (nævnt i handover 2026-07-18), enheds-CA/mTLS (R05/R08). |
| **ISO/IEC 27001:2022** | **Delvist** | GRC-register i PostgreSQL fungerer som ISMS-kim; risikoregister vedligeholdt. **Gap**: A.8.13 backup — restore-test ikke evidenseret (R09 åben, go-live-blocker). Ingen certificering forfulgt (proportionelt). |
| **ISO/IEC 42001 / NIST AI RMF / AI Act** | **Delvist** | AI-domænesnit (formål/prompt/data/ejerskab pr. domæne) er designet; nuværende AI-brug er lav-risiko under AI Act. **Gap**: AI-register som levende artefakt (ikke fundet som håndhævet), menneskelig-i-loop-dokumentation pr. AI-brug. |
| **NIST SP 800-82 (OT)** | **Ikke relevant endnu** | Først relevant ved første OT-payload; arkitekturvejen (06) holder muligheden åben (monitorering-only, ingen aktuator i kontrakt v1). |
| **NERC CIP / FERC / GB/T / AU** | **Ikke relevant nu** | Markeret markedsdrevet i kataloget; ingen handling før konkret marked/kunde. |

## Samlet compliance-dom

Systemet har en **usædvanligt moden compliance-*bevidsthed*** for sin fase (selve kataloget + GRC-registret er et aktiv, som få projekter på denne størrelse har). Afstanden er **evidens og få konkrete fejl**, ikke manglende forståelse. De to hårde blokkere før prod-eksponering er: **TPA-00 (CRA/62443, default secret)** og **R09 (restore-evidens, ISO 27001 A.8.13)**. GDPR er tættest på, men kræver DPA + rolleafklaring før første kommercielle billede lagres for en kunde.

## Konkret compliance-handlingsliste (mapper til fund)

1. Luk TPA-00 fail-closed (CRA/62443) — **før al eksponering**.
2. Evidensér restore-drill (ISO 27001 A.8.13 / NIS2) — **før prod**.
3. Superviser retention-tråden + audit på sletning (GDPR art. 5/17) — TPA-11.
4. Per-device-identitet (62443 CR 1.2 / CRA) — TPA-02, før ny edge udsendes.
5. Aktivér AI-register + DPA-skabeloner som levende artefakter (AI Act/GDPR) — før første kunde.
6. SBOM pr. release + vulnerability-intake (CRA) — kan følge staging.
