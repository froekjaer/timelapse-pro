# TimeLapse Pro Compliance Readiness Pack

**Dato:** 2026-08-25  
**Status:** Praktisk readiness-pakke, ikke juridisk rådgivning og ikke certificering  
**Bygger på:** `Dokumentation/Codex-Audit/`, `SEC-013`, `SEC-014`, `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`, `LICENS_COMPLIANCE_OG_SBOM_EVIDENS_v1.md`

## Formål

Denne mappe omsætter den tekniske Codex-audit til arbejdspapirer, som kan bruges ved kundeonboarding, intern governance, releasebeslutninger og audit-forberedelse.

Pakken må ikke bruges som en erklæring om juridisk compliance eller certificering. Den er et readiness- og evidenslag: hvad kan TimeLapse Pro dokumentere nu, hvad skal udfyldes pr. kunde/site, og hvad skal lukkes før bredere production/markedskrav.

## Dokumenter

| Fil | Bruges til |
|---|---|
| `01_CUSTOMER_SITE_DPIA_PACK.md` | Site-DPIA, dataminimering, retention og TV-overvågning pr. site |
| `02_DATA_PROCESSING_ROLE_MATRIX.md` | Controller/processor-roller, datakategorier og ansvar |
| `03_VULNERABILITY_UPDATE_SLA.md` | Sikkerhedsopdateringer, vulnerability disclosure, patch-SLA og supportperiode |
| `04_SBOM_RELEASE_EVIDENCE_CHECKLIST.md` | SBOM, licens, release-artifact og change-ticket evidens |
| `05_ISO_NIS2_CER_SUPPLIER_ASSURANCE.md` | Kundevendt assurance summary for ISO 27001, NIS2 og CER |
| `06_AI_SYSTEM_INVENTORY.md` | AI Act-readiness, AI-systemregister og menneskelig kontrol |
| `07_COMPLIANCE_ACCEPTANCE_GATE.md` | Gate for pilot, production og markedskrav |

## Aktuel konklusion

TimeLapse Pro har et stærkt teknisk fundament for pilot- og kontrolleret production-readiness, men skal stadig undgå at formulere sig som certificeret eller fuldt juridisk compliant.

Den rigtige eksterne formulering er:

> TimeLapse Pro har dokumenteret teknisk readiness og kontroller for identitet, adgang, audit, signeret opdatering, retention og incident/vulnerability-processer. Endelig site-, kunde- og lovmæssig compliance kræver udfyldte site-DPIA'er, kontraktgrundlag, kundens rolleafklaring og eventuelt ekstern juridisk/certificeringsreview.

## Autoritative interne kilder

- `Dokumentation/Codex-Audit/00_INDEX.md`
- `Dokumentation/Codex-Audit/06_COMPLIANCE_ASSESSMENTS.md`
- `Dokumentation/Codex-Audit/07_ACCEPTANCE_GATE_AND_ROADMAP.md`
- `Dokumentation/Assessment_2026-07_3P_RECONCILIATION_2026-08-25.md`
- `Dokumentation/SEC-013_Incident_Response_Procedure.md`
- `Dokumentation/SEC-014_Vulnerability_Handling_CVE_Process.md`
- `Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`
- `Dokumentation/LICENS_COMPLIANCE_OG_SBOM_EVIDENS_v1.md`

## Eksterne retskilder og standardkilder

Disse links er medtaget som officielle referencepunkter. ISO/IEC-standarder kræver legitim adgang til selve kontrolkataloget, hvis der senere skal laves clause-complete mapping.

- GDPR: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- Cyber Resilience Act: https://eur-lex.europa.eu/eli/reg/2024/2847/oj
- NIS2: https://eur-lex.europa.eu/eli/dir/2022/2555/oj
- CER: https://eur-lex.europa.eu/eli/dir/2022/2557/oj
- EU AI Act: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- EU Cybersecurity Act: https://eur-lex.europa.eu/eli/reg/2019/881/oj
- TV-overvågningsloven: https://www.retsinformation.dk/eli/lta/2023/182
- ISO/IEC 27001 overview: https://www.iso.org/standard/27001
- IEC 62443 overview: https://www.iec.ch/blog/understanding-iec-62443

