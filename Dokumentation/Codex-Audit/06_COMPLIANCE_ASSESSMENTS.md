# Compliance Assessments

## Scope and caveat

This is a technical readiness assessment, not legal advice and not certification. For licensed standards, TimeLapse Pro cannot claim clause-complete compliance until the applicable licensed control catalog is imported, versioned and reviewed.

Official sources checked include:

- GDPR: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- AI Act: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- Cyber Resilience Act: https://eur-lex.europa.eu/eli/reg/2024/2847/oj
- NIS2: https://eur-lex.europa.eu/eli/dir/2022/2555/oj
- CER: https://eur-lex.europa.eu/eli/dir/2022/2557/oj
- EU Cybersecurity Act: https://eur-lex.europa.eu/eli/reg/2019/881/oj
- TV-overvågningsloven: https://www.retsinformation.dk/eli/lta/2023/182
- ISO/IEC 27001 official overview/sample: https://www.iso.org/obp/ui/
- IEC 62443-2-4:2023: https://webstore.iec.ch/en/publication/67631
- IEC 62443-3-3:2013: https://webstore.iec.ch/en/publication/7033
- IEC 62443-4-2:2019: https://webstore.iec.ch/en/publication/34421

## CRA — Cyber Resilience Act

Applicability:

- Likely relevant if TimeLapse Pro is placed on the EU market as a product with digital elements or supplied commercially with software/hardware.

Readiness:

- Partial.

Evidence:

- signed artifact model;
- fail-closed artifact trust;
- SBOM/change ticket references in tests/docs;
- vulnerability handling document exists;
- update/rollback architecture exists;
- credential lifecycle and provisioning model improving.

Gaps:

- formal product role/classification;
- support period policy;
- coordinated vulnerability disclosure operational workflow;
- full SBOM/export evidence for release artifacts;
- security update delivery evidence from current main to Edge;
- CE/conformity file not present as a governed release package.

## GDPR

Applicability:

- Relevant. Captures can include persons, work sites, vehicles, timestamps, user actions, audit logs and AI-derived metadata.

Readiness:

- Partial, not production-complete.

Evidence:

- RBAC/customer/site isolation;
- redaction-related tests and APIs;
- audit and capture access logs;
- retention principle: project evidence is not auto-deleted on uncertain state.

Gaps:

- DPIA must be completed for real site deployments;
- controller/processor roles and DPAs must be explicit;
- data minimization and masking defaults per site;
- retention/disposition policy must distinguish project evidence, logs, AI metadata and operational telemetry;
- subject access/deletion workflows need formalization where applicable;
- signage/legal basis per site must be documented.

## ISO/IEC 27001:2022

Applicability:

- Relevant as ISMS and customer assurance framework.

Readiness:

- Good engineering evidence, incomplete ISMS.

Evidence:

- risk register/GRC;
- access control/RBAC/MFA;
- change/update governance;
- incident/vulnerability documents;
- audit trails;
- backup/restore tests exist in code/docs.

Gaps:

- no formal SoA;
- no internal audit program evidence;
- no management review evidence;
- no complete asset inventory ownership matrix;
- restore rehearsal incomplete;
- supplier/processor management incomplete;
- no clause-complete licensed catalog in repo.

## IEC 63442-2-4 / IEC 62443-2-4

Finding:

- `IEC 63442-2-4` could not be verified as an official IEC standard identifier. The official, relevant service-provider standard appears to be `IEC 62443-2-4:2023`.

Applicability:

- Relevant if TimeLapse Pro acts as an IACS/OT service provider for industrial sites.

Readiness:

- Partial.

Evidence:

- service lifecycle, technician platform, remote support conduit and audit are emerging;
- patch/update model exists;
- backup/recovery docs exist;
- role/capability model exists.

Gaps:

- service provider security program not fully formalized;
- field service procedures not fully evidence-backed;
- break-glass not complete;
- remote access operational controls still converging;
- no licensed 62443-2-4 profile imported.

## IEC 62443-3-3

Applicability:

- Relevant for system-level security requirements if TimeLapse Pro is deployed into OT/IACS-like environments.

Readiness:

- Partial, closer to SL1/SL2-aligned controls than certified SL claims.

Evidence:

- identification/authentication, use control, system integrity, data confidentiality, restricted data flow, timely response to events and resource availability all have partial implementations.

Gaps:

- no zone/conduit enforcement beyond logical architecture;
- mTLS/PKI still converging;
- device hardening/disk encryption incomplete;
- physical compromise controls incomplete;
- no formal security level target/profile.

## IEC 62443-4-2

Applicability:

- Relevant if Edge/Headend components are assessed as IACS components.

Readiness:

- Partial.

Evidence:

- component identity, auth, audit, update verification and fail-closed behavior are improving;
- HAL and service operations reduce direct hardware access.

Gaps:

- component hardening profile incomplete;
- secure boot/disk encryption not implemented;
- no component certification package;
- legacy service surfaces and private key paths still require closure;
- no licensed 62443-4-2 requirement mapping.

## AI Act

Applicability:

- Conditional. Current AI features appear to support image quality, tagging, diagnostics and recommendations. High-risk classification depends on final use, autonomy, employment/workplace impact, safety role and customer context.

Readiness:

- Early partial.

Evidence:

- AI role is documented as observe/classify/recommend, not autonomous irreversible action;
- AI runtime is treated as platform capability;
- model/result repositories and prompts exist.

Gaps:

- role classification provider/deployer/importer/distributor;
- AI system inventory and risk classification;
- human oversight policy;
- data governance and bias/quality documentation;
- post-market monitoring;
- transparency notices where AI outputs affect users/customers.

## CER

Applicability:

- Customer-driven. TimeLapse Pro itself is unlikely to be a critical entity, but may serve sites owned by critical entities.

Readiness:

- Partial as supplier evidence.

Evidence:

- continuity model, backup/restore docs, remote diagnostics, update governance and audit.

Gaps:

- customer criticality classification;
- resilience obligations in contracts;
- business continuity and supplier assurance evidence;
- physical/logical zone model not fully implemented.

## NIS2

Applicability:

- Conditional/customer-driven unless TimeLapse Pro/Froekjaer itself falls into an essential/important entity category. Strongly relevant as supplier/security evidence.

Readiness:

- Partial.

Evidence:

- risk register/GRC;
- access/MFA/RBAC;
- vulnerability handling;
- update governance;
- logging/SIEM;
- backup planning.

Gaps:

- incident reporting procedure and thresholds;
- supply-chain risk management evidence;
- management accountability;
- continuity testing;
- vulnerability disclosure and patch SLA;
- formal policy set.

## EU Cybersecurity Act

Applicability:

- Market/customer-driven. Relevant if TimeLapse Pro later targets EU cybersecurity certification schemes.

Readiness:

- Early.

Evidence:

- security architecture and evidence discipline align with certification direction.

Gaps:

- no selected EU certification scheme;
- no assurance level target;
- no conformity evidence package.

## TV-overvågningsloven

Applicability:

- Site-conditional but likely relevant for repeated camera capture where persons/public areas/workplaces may be recorded.

Readiness:

- Partial, requires deployment-by-deployment legal controls.

Evidence:

- redaction features;
- access control;
- retention/disposition model;
- site/customer structure.

Gaps:

- site-specific lawful basis and signage;
- POLCAM registration assessment where applicable;
- camera angle/privacy masking review;
- workplace/employee notice process;
- policy for disclosure to police/customers/third parties;
- alignment with GDPR/DPA controls.

## Overall compliance conclusion

TimeLapse Pro has unusually strong engineering evidence for a project at this stage, but compliance maturity is not yet "complete". The right claim is:

> TimeLapse Pro is building toward regulatory and assurance readiness, with several strong technical controls already implemented, but it needs formal governance, live evidence, DPIA/site controls, restore testing and licensed-standard mappings before production/certification claims.

