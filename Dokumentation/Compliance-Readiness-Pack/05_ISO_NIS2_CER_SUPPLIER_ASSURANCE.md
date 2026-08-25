# ISO 27001, NIS2 And CER Supplier Assurance

**Status:** Kundevendt assurance summary  
**Caveat:** Ikke en ISO-certificering, NIS2-konklusion eller CER-juridisk vurdering.

## 1. Assurance statement

TimeLapse Pro kan beskrives som teknisk readiness-orienteret med dokumenterede kontroller for adgangsstyring, audit, signeret update, incident response, vulnerability handling, backup/restore-planer og tenant/site-isolation.

TimeLapse Pro må ikke beskrives som ISO 27001-certificeret eller IEC 62443-certificeret uden formel ekstern audit og legitimt kontrolkatalog.

## 2. Control summary

| Område | Nuværende kontrol | Status |
|---|---|---|
| Access control | RBAC, MFA, capability/PDP for service operations | Delvist/aktivt |
| Device identity | Edge lifecycle/credential inventory, WP-4 target model | Delvist/aktivt |
| Update security | Signed artifacts, fail-closed verifier | Aktivt, med release discipline |
| Audit logging | Headend, service operations, technician actions | Aktivt |
| Incident response | SEC-013 procedure | Skrevet, tabletop mangler |
| Vulnerability handling | SEC-014 procedure | Skrevet, operational SLA skal formalisere |
| Backup/restore | Backup docs/tests findes | Restore rehearsal mangler |
| Supplier management | Subprocessor matrix påbegyndt | Mangler kontrakt/evidence |
| Business continuity | Store-and-forward Edge, rollback model | Delvist |
| Privacy | DPIA/retention template og site controls | Delvist |

## 3. NIS2 supplier evidence

Kunder der selv er omfattet af NIS2 kan få følgende evidence:

- access control model;
- update and vulnerability process;
- incident contact/process;
- backup/restore and continuity plan;
- SBOM/release evidence;
- service operation audit;
- tenant/site isolation model;
- known residual risks and remediation roadmap.

Åbne punkter:

- incident reporting thresholds skal kundetilpasses;
- management accountability er kundens og TLPs kontraktspørgsmål;
- supply-chain evidence skal færdiggøres for subprocessorer og dependencies;
- restore rehearsal skal dokumenteres med faktisk RTO/RPO.

## 4. CER supplier evidence

Hvis kunden er kritisk enhed eller leverer til kritisk infrastruktur, bør TLP levere:

- site/device asset list;
- remote access model og service session audit;
- update/rollback procedure;
- incident escalation path;
- backup/restore evidence;
- operational dependency list;
- physical site assumptions.

Åbne punkter:

- kundens kritikalitetsklassifikation;
- kontraktuel resilience/SLA;
- krav til fysisk adgang og emergency support;
- tabletop/recovery rehearsal.

## 5. ISO 27001 readiness map

| ISO-readiness område | Evidence | Gap |
|---|---|---|
| Asset inventory | CMDB/version inventory | Ownership matrix skal færdiggøres |
| Access management | Users/RBAC/MFA/audit | Periodic access review procedure |
| Supplier relationships | Subprocessor matrix | Formal supplier register/review |
| Change management | PR/CI/artifact/update candidates | Exact release evidence pack |
| Incident management | SEC-013 | Tabletop/rehearsal |
| Vulnerability management | SEC-014 | Operational SLA and recurring evidence |
| Backup/restore | Backup design/tests | Live restore rehearsal |
| Logging/monitoring | SIEM/audit alerts | Alert runbooks and tuning |
| Compliance | Codex-Audit + this pack | Clause-complete mapping requires licensed catalog |

