# Reconciliation — 3P Assessment 2026-07

**Dato:** 2026-08-25
**Aktuel baseline:** `main@9925021dc3b19634be55248788d23140d6d6dbd9`
**Historisk kilde:** `origin/assessment/2026-07-3p-review`, `Dokumentation/Assessment_2026-07_3P/`
**Arkiveret kopi:** `Dokumentation/Gamle versioner/Assessment_2026-07_3P/`

## Formål

Denne fil afstemmer Claude's uafhængige 3.-parts assessment fra 2026-07-31 mod den nuværende TimeLapse Pro-tilstand.

Den historiske pakke er værdifuld som audit- og beslutningsevidens, men må ikke læses som aktuel status uden denne reconciliation. Siden 2026-07-31 er store dele af arkitekturen ændret gennem WP-1..WP-4, Trust Service, EdgeServiceGrant, technician platform, artifact signing, update hygiene, retention-fix og live Edge convergence.

## Executive Status

3P-assessmenten var korrekt vigtig på tidspunktet, men er nu delvist overhalet.

Aktuel vurdering:

- **Bevar som historisk evidens:** Ja.
- **Merge råt som aktuel status:** Nej.
- **Brug som aktiv opgaveliste:** Kun punkter markeret `STADIG RELEVANT` nedenfor.
- **Primær nutidig auditpakke:** `Dokumentation/Codex-Audit/`.
- **Primær nutidig convergence-kilde:** `Dokumentation/CONVERGENCE_SOURCE_TO_DECISION_TRACEABILITY_2026-08.md`, WP-dokumenterne og `HANDOVER_LOG.md`.

## Statusmatrix

| 3P fund / tema | Historisk vurdering 2026-07-31 | Status 2026-08-25 | Aktuel handling |
|---|---|---|---|
| TPA-00 / SEC-016 factory BT-TOTP fallback | Kritisk, fail-open known default credential | **LUKKET som delt fallback.** `SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md` dokumenterer closure; tests forbyder `JBSWY3DPEHPK3PXP` i kørende kode. Per-device/auto-sync/bootstrap-sporet er efterfølgende bygget og dokumenteret. | Ingen ny P0 fra 3P. Hold regressionstests og lifecycle-inventory for offline recovery. |
| TPA-01 route-auth canary | Først høj, derefter nedgraderet til lav efter Codex CI-evidens | **ERSTATTET/LUKKET SOM BLOCKER.** Branch protection og route-auth/gov-gates har siden været del af normal CI/PR-flow. | Bevar route-auth ratchet. Ingen selvstændig 3P-action. |
| TPA-02 Edge-signering med Bearer-token/HMAC, mTLS/enheds-CA mangler | Mellem, før ny Edge | **ERSTATTET AF WP-1/WP-4.** Edge credential inventory, bootstrap lifecycle, Edge-owned SSH/TLS key generation, signed provisioning envelope og CSR path er nu implementeret som target-model. Legacy adapters findes stadig for eksisterende Edges. | Følg WP-4 remaining legacy path-dokumentation; ingen tilbage til 2026-07 design. |
| TPA-03 MD5 config fingerprint | Mellem, audit-støj og duplikation | **STADIG RELEVANT.** `hashlib.md5`/`_hl.md5` findes stadig flere steder i `headend/main.py` og `headend/api/service_access_api.py` som config version/fingerprint. Ikke en aktiv kryptografisk sårbarhed, men stadig audit- og duplikationsgæld. | Lav fokuseret P2 hygiene-PR: én `config_fingerprint()` med SHA-256 og tests. |
| TPA-04 dynamisk SQL identifier interpolation | Mellem, primært intern-constant risiko | **STADIG DELVIST RELEVANT.** Nogle paths er legitime migrations/whitelist-lignende helpers; flere settings-table lookups og tool queries bruger stadig interpolerede tabelnavne. | Lav P2 hardening-PR: identifier allowlists for settings-table helpers og upload columns; dokumentér migration-only undtagelser. |
| TPA-05 cookie/JWT skærpelser | Lav | **STADIG RELEVANT SOM HYGIENE.** Ingen evidence for akut regression; bør ligge som normal security hardening. | P3/P2 afhængigt af Internet exposure: SameSite/CSRF review for muterende endpoints. |
| TPA-06 replay-vindue for signed Edge requests | Lav/usikkerhed | **DELVIST ERSTATTET.** Trust Service/EdgeServiceGrant har replay/challenge-tests; Edge API request replay bør fortsat have eksplicit test hvis ikke allerede dækket. | P2/P3 test gap: dokumentér/tilføj nonce/skew test for Edge request signing. |
| TPA-07 SIEM naive string matching | Lav | **STADIG RELEVANT SOM LABELING.** Heuristikker kan være nyttige, men må ikke fremstilles som verificerede exploits. | UI/event-type labeling når SIEM-polering genoptages. |
| TPA-10 monolit `headend/main.py` | Høj teknisk gæld | **STADIG RELEVANT, men styret.** Arkitektur-ratchet og router-udtræk er aktiv praksis; Codex-Audit gentager monolitten som P2, ikke release-blocker. | Fortsæt ratchet og små router/service udtræk. Ingen big-bang. |
| TPA-11 background jobs uden fælles supervision | Mellem | **DELVIST RELEVANT.** Backup/update/retention har fået mere evidence og konkrete fixes; samlet job registry er stadig nyttigt men ikke Gate 0. | P2 operational observability: background job registry/health when touching startup/jobs. |
| TPA-12 tråd-pr.-hændelse uden begrænsning | Mellem | **UKLAR / KRÆVER NY MÅLING.** Ikke valideret i denne reconciliation; nyere architecture work kan have ændret hot paths. | Re-test under load/soak før production scale claim. |
| TPA-13 module-level caches | Lav | **STADIG HYGIENE.** Ikke en blocker. | Tag opportunistisk sammen med settings/cache work. |
| TPA-14 FastAPI `on_event`/lifespan | Lav | **STADIG HYGIENE.** | Tag opportunistisk med startup/job registry. |
| TPA-15 duplikation/settings adapter | Mellem | **STADIG DELVIST RELEVANT.** Flere settings helpers og config fingerprint-duplicates findes endnu, selv om convergence har reduceret parallelle authority paths på Edge. | Kombiner med TPA-03/04 som lille hygiene sequence. |
| H-01..H-07 hardcoded paths/ports/env defaults | Mellem | **DELVIST LUKKET / DELVIST RELEVANT.** CMDB/version inventory og update hygiene forbedret; flere hardcoded local fallbacks findes stadig. | Ikke Gate 0. Lav sweep når settings registry arbejdet genoptages. |
| TPA-20..24 UI/UX navigation/sprog/persona | Mellem/lav | **DELVIST LUKKET/OVERHALET.** Hjælpemenu, CMDB-version UI, update-indikatorer og technician UI er ændret siden. | Kræver ny UI-review mod current UI; ikke brug 31. juli-listen direkte. |
| GDPR compliance gaps | Delvist, DPA/roles/retention supervision mangler | **STADIG RELEVANT, men status ændret.** Edge-local retention og Headend retention/audit er stærkere; DPIA/DPA/controller-processor/site signage og TV-overvågning er stadig business/legal readiness. | Brug `Codex-Audit/06_COMPLIANCE_ASSESSMENTS.md` som aktuel kilde; lav kunde/site compliance pack før kommerciel produktion. |
| CRA readiness | Blocker pga. TPA-00, SBOM/update gaps | **STADIG RELEVANT, MEN IKKE SAMME BLOCKER.** Factory TOTP er lukket; artifact signing, SBOM/update governance og WP-4 er stærkere. Formal product classification/support period/VEX/CE file mangler stadig. | Brug Codex-Audit CRA-afsnit og release evidence pack. |
| IEC 62443 | Delvist, TPA-00 + mTLS/enheds-CA gaps | **DELVIST ERSTATTET.** Trust Service, PDP, EdgeServiceGrant, WP-4 provisioning og technician platform har ændret risikobilledet. | Ny 62443 mapping skal baseres på current architecture, ikke 31. juli. |
| ISO 27001 / R09 restore evidence | Restore-test go-live blocker | **STADIG RELEVANT.** Backup er forbedret og restore-verifiable mekanik findes, men egentlig restore rehearsal/evidence er stadig et stærkt acceptance gate før brede compliance claims. | Planlæg og dokumentér Headend DB + capture-store restore rehearsal. |
| AI Act / AI register | Delvist | **STADIG RELEVANT.** AI-funktioner er fortsat støtte/diagnostik, men register/rolleklassifikation/human oversight bør være levende dokumentation. | Indgår i compliance pack. |
| GEN-01 SFTP ingress i generator | Høj før staging | **DELVIST ERSTATTET AF SENERE SITE-SFTP/RBAC-ARBEJDE.** Site SFTP er nu behandlet som site/RBAC-owned credential/profile, og Edge-consumed SFTP er inventory-aware. Generatorens fulde fresh install path bør dog vurderes mod current architecture. | Re-test headend/site provisioning from blank install; ikke merge gammel generator-plan blindt. |
| GEN-02 SFTP port setting | Lukket efter Codex-evidens | **LUKKET.** | Ingen action. |
| GEN-03/04/11 tunnel-port/prod image build beslutninger | Peter-beslutninger | **ERSTATTET AF LOCKED ARCHITECTURE + WP-4.** Generic signed image + provisioning envelope er target; reverse tunnel work er efterfølgende behandlet i Trust/SSH tunnel UX. | Brug locked decisions og WP-4 docs. |
| E-01/E-02 per-device identity/fail-closed enrollment | Kritisk | **LUKKET/ERSTATTET AF WP-4 BASELINE.** Signed provisioning envelope, one-time bootstrap consume, hardware binding, Edge-owned keys og lifecycle inventory er implementeret/testet. | Følg WP-4 exit/remaining legacy paths. |
| Framework v1 contracts path | Additivt næste skridt | **STADIG STRATEGISK RELEVANT, MEN IKKE RELEASE-BLOCKER.** Mission Framework alignment er nu behandlet i Codex-Audit og OP-001 loader. | Hold som later architecture governance track. |

## Fund der stadig bør oprettes eller bevares som aktive work items

1. **P2 — Config fingerprint consolidation:** erstat MD5-duplikation med én SHA-256 helper.
2. **P2 — Dynamic SQL identifier allowlists:** tillad kun eksplicit kendte tabel-/kolonnenavne; marker migrationsundtagelser.
3. **P2 — Restore rehearsal evidence:** kør og dokumentér restore af Headend DB + capture-store.
4. **P2 — Compliance readiness pack:** DPIA, DPA/controller-processor, site signage/TV-overvågning, AI register, support/vulnerability/update SLA.
5. **P3/P2 — Edge request replay tests:** bekræft nonce/skew for Edge API signing, separat fra EdgeServiceGrant.
6. **P3 — UI language/navigation refresh:** ny review mod current UI frem for 31. juli snapshot.

## Fund der ikke bør genåbnes fra 3P-pakken

- Factory shared TOTP fallback som P0: lukket og testet.
- Route-auth canary som høj blocker: nedgraderet og overhalet af CI-evidens.
- 31. juli Edge generator model: erstattet af WP-4 target model.
- Gammel retention supervision som “stille manglende sletning”: Edge-local uploaded FIFO retention er implementeret og verificeret live; eventuel opfølgning skal handle om current retention telemetry, ikke den gamle no-op tilstand.
- PR/branch-anbefalinger fra 31. juli uden current rebase: brug `gh pr list` og current open PR-status i stedet.

## Beslutning

Den historiske 3P-pakke bevares i `Dokumentation/Gamle versioner/Assessment_2026-07_3P/`.

Denne reconciliation er den autoritative læsevej for pakken efter 2026-08-25. Nye GRC-items må oprettes fra statusmatrixens `STADIG RELEVANT` punkter, ikke direkte fra de arkiverede filer.
