# Raw archaeology extract — current 005

## Dokumentation/Codex-Audit/00_INDEX.md

1: # Codex-Audit — TimeLapse Pro Readiness Review
8: ## Formål
17: ## Audit-filer
28: ## Praktisk compliance-pakke
31: Den pakke er den anbefalede indgang, når auditten skal bruges til kundeonboarding,
35: ## Metode
41: ## Vigtige begrænsninger

## Dokumentation/Codex-Audit/01_EXECUTIVE_READINESS.md

1: # Executive Readiness
3: ## Kort konklusion
19: ## Readiness score
25: | Device trust / provisioning | Gul | WP-4-kontrakter findes. Live edge-konvergens og artifact pipeline mangler stadig fuld driftsevidens. |
30: | Privacy/GDPR/TV-overvågning | Gul/rød | Redaction og RBAC findes, men DPIA, site-skiltning, retention og databehandlerstyring skal formaliseres. |
34: ## P0/P1 fund
36: ### P0 — ingen nye Edge full artifact deployments før F-001/F-005-lignende gates er dokumenteret grønne på current main
38: De konkrete closure-spor ser ud til at være implementeret i `main`, men de er release-kritiske og skal forblive gate for enhver Edge 2 full artifact deployment:
43: - signed artifact skal have version, source commit, SHA-256, signature, manifest, compatibility metadata og rollback target.
45: ### P1 — `edge/technician_auth.py` har sandsynlig runtime regression i confirmation path
49: ### P1 — Edge 2 SSH host-key mismatch er stadig en security event
51: Der må stadig ikke foretages `known_hosts` housekeeping, blind accept eller bypass. Den nye read-only authenticated Edge report-operation er den rigtige vej. Browserterminal skal forblive nægtet for TL-043EB9E72EFD indtil host identity er verificeret og dokumenteret.
53: ### P1 — break-glass og daglig SSH/service-adgang er ikke fuldt konsolideret live
57: ### P1 — restore/rollback er fortsat go-live kritisk
61: ## Samlet vurdering

## Dokumentation/Codex-Audit/02_MISSION_FRAMEWORK_ALIGNMENT.md

1: # Mission Framework Alignment
3: ## Framework-principper brugt som målestok
5: Mission Framework angiver især disse krav som relevante for TimeLapse Pro:
12: - Independent outcome verification: fravær, regression og uventet difference skal opdages som first-class conditions.
15: ## Alignment der er stærkt forbedret
17: | Framework-krav | TimeLapse Pro evidence | Vurdering |
22: | Independent contracts | Route auth coverage, WP-4 provisioning tests, ServicePlatform tests | Stærk forbedring |
23: | Evidence preservation | Handover-entry disciplin og GRC register | God, men GRC-access skal være robust |
26: ## Alignment gaps
28: ### 1. For mange parallelle legacy paths lever stadig side om side
40: Det er ikke nødvendigvis forkert under migration, men det skal være synligt som midlertidigt og må ikke blive ny normaltilstand.
42: ### 2. Handover er stærk, men endnu ikke nok til drift
44: Handover-loggen er meget værdifuld, men flere beslutninger står som "mangler næste skridt". Mission Framework kræver, at en ny deltager kan rekonstruere tilstand uden samtalehistorik. Det kræver at de åbne punkter også findes i GRC/roadmap/CI-gates, ikke kun i prosa.
46: ### 3. Independent outcome verification mangler endnu på live operations
56: ### 4. Compliance intelligence er et godt register, ikke en færdig compliance engine
58: `headend/compliance_intelligence.py` har et sundt princip: ingen full-audit claim uden versioneret, importeret og verificeret katalog. Det er præcis Mission Framework-rigtigt. Men det betyder også, at nuværende compliance-sider skal kaldes readiness/evidence, ikke certificering.
60: ## Min vurdering

## Dokumentation/Codex-Audit/03_ARCHITECTURE_DATAFLOWS.md

1: # Architecture And Dataflows
3: ## Aktuel struktur
42: ## Primære dataflows
44: ### 1. Capture/upload
59: - per-site SFTP credential ownership skal fortsat afgrænses mellem site RBAC og Edge lifecycle;
60: - upload health skal forbindes til credential inventory så manglende known_hosts ikke bliver støj hvert 10. minut uden remediation flow.
62: ### 2. Edge API/sync
76: - handover beskriver historisk dobbelte loops/version-hash mismatch; det skal verificeres at current main ikke stadig har uønsket parallel polling i live runtime;
79: ### 3. Provisioning / WP-4
101: - live migration skal være one-device-at-a-time og non-destructive.
103: ### 4. Technician service
125: - browser shell skal fortsat være explicit break-glass/engineering capability, not normal service.
127: ### 5. Browser SSH terminal
148: - TL-043EB9E72EFD must remain denied until its host key mismatch is resolved.
150: ## Architecture assessment
152: Target-modellen er god. Det vigtigste der mangler, er ikke en ny arkitektur, men:

## Dokumentation/Codex-Audit/04_CODE_REVIEW_FINDINGS.md

1: # Code Review Findings
3: ## P1 — Technician auth confirmation SQL likely fails at runtime
20: ## P1 — Break-glass remains partially operational rather than fully closed
41: ## P1 — GRC DB connectivity for AI/operator workflows is brittle
56: ## P2 — `ServicePlatform.shared_or_lab_session()` calls `current_session()` twice
69: ## P2 — Headend still has a very large monolithic `main.py`
88: ## P2 — Remaining ad hoc authorization paths need closure
109: ## P2 — `edge/technician_ui.py` is retired but still contains legacy HTTP handler code
115: - future maintainers may accidentally revive a retired surface;
123: ## P2 — Edge local PKI still has Headend-generated leaf key path
138: ## P3 — Minor code hygiene
146: These are not blockers, but should be cleaned as part of stabilization.

## Dokumentation/Codex-Audit/05_SECURITY_RISK_SABSA_PENTEST.md

1: # Security Risk, SABSA And Virtual Pentest
3: ## SABSA business attributes
7: | Availability | Unattended capture and upload must continue despite network/service faults | Yellow: store-and-forward exists, but live Edge convergence and rollback must be rehearsed. |
8: | Integrity | Images, sidecars, update artifacts and audit evidence must be tamper-evident | Yellow/green: hashes and signed artifact model exist; production artifact gate must remain strict. |
15: ## Virtual penetration test
19: ### Attack path A — use old/shared credentials to bypass new service model
34: ### Attack path B — malicious or unsigned update artifact
43: - current target path should fail closed for code/OS updates when configured correctly.
49: ### Attack path C — Edge 2 SSH host-key mismatch
66: ### Attack path D — local technician auth regression drives operator to weaker path
80: ### Attack path E — web/API route without authentication
88: - accidental new `/api/*` route without reviewed auth should be caught by CI.
94: ### Attack path F — SFTP host key spoofing
103: - upload may fail noisily, but should not auto-trust attacker-controlled SFTP.
109: ### Attack path G — Headend-generated operational private keys survive WP-4
124: ## Risk register summary
126: | ID | Severity | Risk | Current control | Required next action |
133: | CA-006 | P2 | Legacy TLS/key issuance path | WP-4 CSR tests | Enforce CSR path for new Edges |
137: ## SABSA conclusion
139: The target security architecture is coherent. The remaining risk is mainly convergence risk: old paths, live device state and release process must not outrun the new trust model.

## Dokumentation/Codex-Audit/06_COMPLIANCE_ASSESSMENTS.md

1: # Compliance Assessments
3: ## Scope and caveat
21: ## CRA — Cyber Resilience Act
49: ## GDPR
68: - DPIA must be completed for real site deployments;
69: - controller/processor roles and DPAs must be explicit;
71: - retention/disposition policy must distinguish project evidence, logs, AI metadata and operational telemetry;
73: - signage/legal basis per site must be documented.
75: ## ISO/IEC 27001:2022
104: ## IEC 63442-2-4 / IEC 62443-2-4
133: ## IEC 62443-3-3
155: ## IEC 62443-4-2
176: - no licensed 62443-4-2 requirement mapping.
178: ## AI Act
203: ## CER
224: ## NIS2
252: ## EU Cybersecurity Act
272: ## TV-overvågningsloven
298: ## Overall compliance conclusion

## Dokumentation/Codex-Audit/07_ACCEPTANCE_GATE_AND_ROADMAP.md

1: # Acceptance Gate And Roadmap
3: ## What should not merge/deploy yet
32: ## What should be implemented first
34: ### 1. Fix the technician auth SQL regression
38: ### 2. Finish Edge 2 read-only trust unblocker
42: ### 3. Generate signed deployable Edge application artifact
44: No source/worktree deployment. Artifact must include:
54: ### 4. Prove rollback/recovery before Edge deployment
56: For Edge 2, deployment should remain blocked unless rollback can be performed without physical access and without destructive credential replacement.
58: ### 5. Controlled canary Edge convergence
71: ### 6. Close live technician key / break-glass delta
75: ### 7. Restore rehearsal
79: ### 8. Compliance readiness pack
90: ## RC1 acceptance recommendation

