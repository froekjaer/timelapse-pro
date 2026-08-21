# Executive Readiness

## Kort konklusion

TimeLapse Pro nærmer sig en acceptabel platform-tilstand for **kontrolleret pilot / R&D / begrænset kundeafprøvning**, men er efter min vurdering **ikke endnu klar som bred production/scale release** uden eksplicit risk acceptance.

Den vigtigste positive ændring siden de ældre juli-assessments er, at projektet nu har en tydeligere locked architecture og flere reelle kontrakttests omkring:

- Edge lifecycle og credential inventory;
- EdgeServiceGrant og central PDP;
- ServicePlatform / Service Operations;
- WP-4 provisioning model;
- SFTP host trust fail-closed;
- artifact signing fail-closed;
- route authentication coverage.

Det er ikke længere en samling tilfældige features. Det begynder at ligne en platform.

## Readiness score

| Område | Vurdering | Begrundelse |
|---|---:|---|
| Arkitekturretning | Grøn/gul | Locked target model er stærk og implementeret i flere lag. |
| Engineering continuity | Gul | OP-001, handover, GRC og tests hjælper, men mange åbne PRs og legacy paths kræver disciplin. |
| Device trust / provisioning | Gul | WP-4-kontrakter findes. Live edge-konvergens og artifact pipeline mangler stadig fuld driftsevidens. |
| Technician platform | Gul | ServicePlatform findes, men der er fundet runtime bug i technician auth confirmation path. |
| Auth/RBAC/PDP | Gul | Central PDP er indført, men ad hoc authorization findes fortsat i flere API-moduler. |
| Secrets/private keys | Gul/rød | Meget forbedret, men live legacy og break-glass overlap er stadig risikoområde. |
| Update / OTA | Gul | Bedre fail-closed trust, men signed deployable Edge artifact og rollback evidence er fortsat release-gate. |
| Privacy/GDPR/TV-overvågning | Gul/rød | Redaction og RBAC findes, men DPIA, site-skiltning, retention og databehandlerstyring skal formaliseres. |
| Operations/backup/restore | Gul/rød | Backup findes, men dokumenteret restore rehearsal er stadig en væsentlig go-live-gate. |
| Testdisciplin | Grøn/gul | Mange kontrakttests; dog kendt test isolation-gæld og manglende live integration evidence. |

## P0/P1 fund

### P0 — ingen nye Edge full artifact deployments før F-001/F-005-lignende gates er dokumenteret grønne på current main

De konkrete closure-spor ser ud til at være implementeret i `main`, men de er release-kritiske og skal forblive gate for enhver Edge 2 full artifact deployment:

- ingen shared factory TOTP fallback i Headend config merge;
- artifact signing fail-closed uden for explicit LAB/test;
- `system-hash` må ikke være production-deployable artifact;
- signed artifact skal have version, source commit, SHA-256, signature, manifest, compatibility metadata og rollback target.

### P1 — `edge/technician_auth.py` har sandsynlig runtime regression i confirmation path

`confirm_session()` indeholder en SQL `UPDATE` med dobbelt `WHERE session_id = ?`. Det er ikke en Python syntax-fejl, men SQLite vil afvise queryen ved runtime. Det kan blokere normal central technician-auth confirmation og dermed svække WP-3/WP-2 sammenhængen.

### P1 — Edge 2 SSH host-key mismatch er stadig en security event

Der må stadig ikke foretages `known_hosts` housekeeping, blind accept eller bypass. Den nye read-only authenticated Edge report-operation er den rigtige vej. Browserterminal skal forblive nægtet for TL-043EB9E72EFD indtil host identity er verificeret og dokumenteret.

### P1 — break-glass og daglig SSH/service-adgang er ikke fuldt konsolideret live

Kodebasen er bevæget mod RBAC-scopede tekniker-nøgler og EdgeServiceGrant, men handover viser, at live devices endnu ikke nødvendigvis er provisioneret fuldt, og password-baseret break-glass ikke er ende-til-ende lukket.

### P1 — restore/rollback er fortsat go-live kritisk

Mission Framework kræver kontinuitet. TimeLapse Pro har update/rollback-mekanismer, men bred production readiness kræver dokumenteret Headend DB/capture-store restore og Edge rollback rehearsal.

## Samlet vurdering

Jeg ville ikke stoppe projektet. Tværtimod: det er nu tættere på sin endelige arkitektur end tidligere. Men jeg ville stoppe brede featureudvidelser og gøre resten af arbejdet gate-drevet:

1. fix technician auth confirmation bug;
2. luk Edge 2 host-key evidence og signed artifact gate;
3. bevis non-destructive Edge convergence på en canary;
4. luk live break-glass/technician-key operationalisering;
5. gennemfør restore rehearsal;
6. formaliser DPIA/site privacy controls før egentlig kundeproduktion.

