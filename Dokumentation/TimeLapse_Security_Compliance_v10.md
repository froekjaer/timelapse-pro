# TimeLapse Pro — Security & Compliance Framework (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Konsoliderer:** `TimeLapse_Security_Compliance_v2.docx`, `timelapse_full_security.docx` (identiske), `timelapse_security.docx` (arkiveret i `Gamle versioner/`).

> **Note:** Dette er den dybdegående security-/compliance-analyse (STRIDE, DFD, SABSA 6-lag, IEC 62443, CRA). Skrevet i Canon/RPi5-æraen; det operationelle risikobillede er ført videre i `RISK_ASSESSMENT_v10.md`. Dette dokument bevarer den strukturerede trussel- og compliance-analyse.

## 1. Executive summary

Distribueret industrielt IoT-system til kontinuerlig fotografisk dokumentation: feltinstallerede edge-noder (Orange Pi 4 Pro + DSLR) + central headend, forbundet via LAN/WiFi og SFTP/SSH. Behandler potentielt personhenførbare data + forretningskritiske billeder for eksterne kunder.

Dækker: SABSA-risikoanalyse (alle 6 lag), STRIDE-trusselmodellering, dybdegående cybersecurity code review, data flow-dokumentation (DFD-0 til DFD-2), compliance mod IEC 62443-2-4 ML2 / 62443-3-3 SL2 / 62443-4-2 SL2, ISO 27001:2022, GDPR, NIS2, CER og CRA.

**Mest kritisk — CRA:** TimeLapse Pro klassificerer sandsynligvis som **Class I Important Product** under Annex III (netværkstilsluttet IoT med fjernfejlsøgning), hvilket kræver tredjeparts-konformitetsvurdering af et notificeret organ inden CE-mærkning og markedsføring i EU. Frist: september 2026.

## 2. Systembeskrivelse

Multi-tenant distribueret system i tre lag: edge (feltinstallation), headend (central server), præsentation (web-UI). Designet til bygge-/anlægsmiljøer med begrænset IT-infrastruktur og upålideligt netværk. Inkl. hardwarekomponenter + tillidsniveauer + kommunikationsgrænseflader.

## 3. Data flow-dokumentation

DFD-0 (kontekst), DFD-1 (primære flows: capture-pipeline hvert 10. min, auth-flow, reverse SSH-flow), DFD-2 (sikkerhedskritiske subflows). STRIDE-koder pr. trin: S=Spoofing, T=Tampering, R=Repudiation, I=Information Disclosure, D=Denial of Service, E=Elevation of Privilege. Inkl. dataklassifikation + GDPR-mapping.

## 4. SABSA-risikoanalyse (6 lag)

Contextual (forretning) → Conceptual (kernesikkerhedsprincipper) → Logical (STRIDE-trusselmodel, sandsynlighed×konsekvens: ≥15 KRITISK, 8–14 HØJ, 4–7 MEDIUM) → Physical → Component → Operational. Integrerer STRIDE + DREAD.

## 5. Cybersecurity code review

Design-niveau review af samtlige filer/funktioner (agent.py edge, main.py headend, database.py, gphoto2_driver.py + Sprint C-filer), baseret på OWASP Top 10, CWE/SANS Top 25, IEC 62443, GDPR Art. 25 (privacy by design). Automatiseret SAST (Bandit, Semgrep, pip-audit) anbefales som supplement. **Opdateret 2026-07-05:** den oprindelige SAST-backlog på "73 signals" var baseret på en upålidelig scanner-optælling (to selvreferencer i AI Ops' egen statiske scanner er siden rettet); triagen af alle 80 aktuelle signaler (`hardcoded_secret_terms`, `shell_execution`, `legacy_update_paths`, `dangerous_file_ops`) er nu afsluttet uden bekræftede reelle sårbarheder — ét opmærksomhedspunkt til Peter resterer (lokalt dev-værktøj `claude_proxy.py`s `shell=True`). Se `RISK_ASSESSMENT_v10.md` VPEN-006/VPEN-2026-008/VPEN-2026-009 for detaljer.

## 6. IEC 62443 compliance

- **62443-2-4 ML2** (serviceudbyderkrav): definerede, dokumenterede, konsistent implementerede processer på tværs af projekter.
- **62443-3-3 SL2** (systemkrav): 7 Foundational Requirements — FR1 Identification & Authentication Control, FR2 Use Control, FR3 System Integrity, FR4 Data Confidentiality, FR5 Restricted Data Flow/segmentering, FR6 Timely Response to Events, FR7 Resource Availability. SL2 = beskyttelse mod bevidst overtrædelse med simple midler/lav motivation.
- **62443-4-2 SL2** (komponentkrav).

## 7. Øvrige standarder

ISO 27001:2022 (ISMS, controls), GDPR (DPIA, retention, DPA, subprocessorer, access logs), NIS2 (continuity, incident handling, supply chain), CER, CRA (secure update, SBOM, lifecycle, vulnerability process). Operationel status pr. standard føres i `RISK_ASSESSMENT_v10.md` §6–§9 og `KRAVREGISTER_og_STATUS_v10.md`.
