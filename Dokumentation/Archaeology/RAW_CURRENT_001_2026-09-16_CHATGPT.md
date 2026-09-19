# Raw archaeology extract — current 001

## Dokumentation/00_START_HER.md

1: # 00 — START HER (master-indeks & onboarding)
7: > **Navigationsdiagnostik 2026-09-10:** [aktivering, installation, test og målegrænser](NAVIGATION_DIAGNOSTICS_2026-09.md). Opt-in diagnostik for sporadiske menupauser; se handover for faktisk rollout-status.
17: ## 1. Boot en ny session — kernefakta
29: - **Storage:** Den logiske datarod er `/data-fast`, oprettet af macOS `synthetic.conf` og aktuelt pegende paa den monterede data-disk. Ny drift/backup skal bruge den logiske sti, saa enclosure/NAS kan skiftes uden kodeændringer. Eksisterende Nginx-medier kan fortsat bruge valideret fysisk sti, indtil en separat TCC- og regressionstest er gennemført. Billed-rod styres af `sftp\_base` i DB-settings. Krypteret projektbackup: lokal `/data-fast/backup/project-snapshots/restic-repository`; OneDrive-spejl `/Users/peter/Library/CloudStorage/OneDrive-Personligt/Filer/Projektbackups/restic-repository`. Se `PROJECT_SNAPSHOT_BACKUP.md`.
35: - **Public (planlagt):** `www.timelapse-pro.dk` (statisk info, hostes separat fra staging/prod) + `backend.timelapse-pro.dk:8443` (UI/API, direkte nginx-eksponering — IKKE Cloudflare Tunnel, da CrushFTP allerede ejer 21/22/80/443 på staging/prod-maskinerne; certifikat via DNS-01, se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4). Lab i dag: `timelapse.froekjaer.dk`.
60: ## 2. Autoritative dokumenter (seneste = v10)
66: | `KRAVREGISTER\_og\_STATUS\_v10.md` | Krav-/ønskeregister, status, tidslinje, oprindelige krav, P0/P1/P2 |
67: | `GO\_LIVE\_CHECKLIST\_v10.md` | Krav (A–L) før Internet-eksponering + go/no-go |
78: | `TimeLapse\_Roadmap\_v10.md` | Historisk sprint-roadmap (fremadrettet plan i kravregisteret) |
85: ## 3. Levende arbejdsdokumenter (opdateres løbende — ikke versioneret)
95: | `../PRIORITIZED\_BACKLOG.md` (repo-rod) | Prioriteret backlog — sessions-opstart bruger denne i praksis |
98: | `Codex_Kodereview_2026-08/` | Evidensbaseret review, testbevis, UI-audit og afhjælpningsplan (aabne P0-fund) |
105: ## 4. Aktuelle design-/analysenotater
107: `Claude\_QA\_Review\_2026-07-17.md` (**nyeste QA/retning: SEC-016, GOV-01, gap-analyse for platform/payload**), `Claude\_QA\_Arkitektur\_Review\_2026-07-15.md` + `Codex\_REVIEW\_Claude\_Arkitektur\_Risk\_Test\_2026-07-15.md` (arkitektur/risk/test-reviews bag ADR-001), `TENKNISK\_GÆLD\_ANALYSE\_headend\_main\_py\_2026-07-06.md` + `P2-01\_Refaktoreringsplan\_main\_py.md` (teknisk gæld/refaktorering), `STAGING\_TIL\_PROD\_PROMOTION\_v1.md` + `HEADEND\_GENERATOR\_v1.md` (promotion/provisioning), `Claude\_REVIEW\_Generatorer\_Edge\_Headend\_2026-07-17.md` (generator-review, fund GEN-01..11) + `INSTALLATIONSMANUAL\_HEADEND\_GENERATOR\_v1.md` + `INSTALLATIONSMANUAL\_EDGE\_GENERATOR\_v1.md` (trin-for-trin install: headend på kørende Mac m. CrushFTP-sameksistens; edge som image eller på eksisterende Linux), `Claude\_Observability\_ITIM\_Design\_2026-06-29.md` (ITIM/observability), `Codex\_Thumbnail\_503\_Analyse\_2026-06-30.md`, `Codex\_Edge\_AI\_NPU\_Modes\_2026-06-28.md` (edge NPU), `Claude\_AI\_Tagging\_Redesign\_2026-06-23.md` (tag-generering), `Nikon\_Z30\_LAB\_Profil\_og\_Fokus\_2026-06-22.md`, `Global\_Config\_og\_Kamera\_Binding\_2026-06-22.md`, `README\_CMDB.md`.
109: ## 5. Reference (fortsat gældende)
113: ## 6. Undermapper
119: | `Hardware manualer/` | PDF-manualer: OrangePi 4 Pro (A733), OrangePi PC Plus, OpenClaw-deploy. |
121: | `../docs/` (repo-rod) | ~20 kode-nære udviklernoter fra z.ai-perioden (drift-mode, site-look, LAB-testguide, edge-arkitektur m.m.). **Beslutning om varig placering udestår** (jf. `Claude\_QA\_Review\_2026-07-17.md` §5) — tjek mappen ved arbejde på disse features. |

## Dokumentation/ADMINISTRATORMANUAL_v10.md

1: # TimeLapse Pro — Administratormanual (v10, konsolideret)
5: **Målgruppe:** TimeLapse Pro-administrator (Peter Frøkjær), drift, sikkerhedsansvarlig, teknisk projektleder
14: ## 1. Systemarkitektur
30: ## 1.5 Nye sikkerheds- og compliance-opdateringer (juli 2026)
32: Følgende væsentlige sikkerheds- og compliance-forbedringer er implementeret i juli 2026 og bør være en del af administratorviden:
34: ### 1.5.1 M-05: Agent-role lockdown (PR #2)
46: **Forudsætning:** `TIMELAPSE_ENV` skal være sat korrekt (`rd`/`staging`/`prod`).
50: ### 1.5.2 R17: Debug/lab mode forbedringer
52: **Status:** Kode deployet (commit `44b78fb7`), health 200 OK, manuel smoketest udestår.
63: ### 1.5.3 G-05: Download-/adgangslog pr. billede
76: ### 1.5.4 R09: Backup og resilience forbedringer
86: **VIGTIGT:** Peter/Codex bør manuelt trigge en backup og bekræfte at billed-mirror opfører som forventet på Mac Mini'en.
92: ### 1.5.5 P0-05: Retention Policy (GDPR G-02)
112: 3. **Indstillinger-tab:** Vælg cleanup interval (manuel/dagligt/ugentligt/månedligt).
131: ### 1.5.6 SEC-013: Incident Response Procedure
152: ### 1.5.7 SEC-014: Vulnerability Handling og CVE-proces
176: ### 1.5.8 F-012: Site-Wide Look Matching (2026-07-12)
249: ## 2. Daglig drift
251: ### 2.1 Tjek systemstatus
254: # Headend health
257: # LaunchAgent status
260: # Seneste log (200 linjer)
263: # PostgreSQL
267: ### 2.2 Genstart Headend
270: # Normal genstart (samme plist)
273: # Genindlæs plist (efter konfigurationsændring)
278: ### 2.3 Se captures og uploads
281: # Antal captures i dag
285: # Seneste 10 uploads
289: # Storage-brug
293: ### 2.4 Compliance, backup og resilience-status
304: ## 3. Headend — opsætning og konfiguration
306: ### 3.1 Venv og services
317: ### 3.2 Miljøvariable (i LaunchAgent plist)
321: | `JWT_SECRET` | Signering af JWT-tokens (skal være stabilt på tværs af genstarter) |
328: ### 3.3 Opdater headend-kode (ny version)
334: # Geninstaller Python-dependencies hvis nødvendigt
337: # Byg ny UI
340: # Genstart headend
346: ## 4. Edge-management
348: ### 4.1 SSH adgang til edge
351: # Via reverse tunnel (anbefalet — virker selv uden direkte netværksadgang)
352: # Åbn tunnel fra headend-UI: Admin → CMDB → [device] → SSH Tunnel
355: # Direkte SSH (kræver lokal netværksadgang)
359: ### 4.2 Se edge-logs
362: # Via SSH til edge
367: ### 4.3 Manuelt billede nu
370: # Via SSH til edge
377: ### 4.4 Edge-konfiguration
392: ## 5. Provisioning af ny edge-enhed
394: ### 5.1 Byg disk image
402: ### 5.2 Flash image
405: # Udpak og flash til SD-kort (erstat /dev/diskN med korrekt disk)
409: ### 5.3 Første boot
418: ## 6. Update-flow
420: ### 6.1 App-opdatering til edge
425: 4. Klik **"Godkend"** — edge henter og installerer automatisk ved næste maintenance window
428: ### 6.2 OS-sikkerhedsopdatering
432: 3. Review og godkend som ovenfor
435: ### 6.3 Rollback
441: ## 7. GPG og artifact-signering
444: # Verificer GPG-nøgle er til stede
447: # Test signering
450: # Verificer signeret artifact
453: # Vis trust niveau
455: # > trust (skal være "ultimate" for headend-nøglen)
462: ## 8. Backup
464: ### 8.1 Manuel backup
467: # Backup til /Volumes/Backup (kør fra headend)
468: # Trigger via Admin UI → Backup → Kør backup nu
471: ### 8.2 Verificer backup
476: # Kør fra repo rod
479: # Valg:
480: # --dry-run        Vis hvad der ville blive tjekket uden at udføre handlinger
481: # --test-restore   Udfør faktisk restore til /tmp/timelapse-restore-test og verifikation
482: # --max-age HOURS  Maximal alder af backup i timer (default: 48)
484: # Eksempler:
494: # Bekræft nyeste backup er inden for de seneste 24 timer
500: # Headend skal køre
505: ### 8.3 Restore procedure
510: **⚠️ ADVARSEL:** Restore stopper headend og er midlertidig nedetid. Udfør kun ved nødvendigt driftsstop eller planlagt maintenance.
622: # Brug verify_backup.sh --test-restore flaget
625: # Dette udpakker backup til /tmp/timelapse-restore-test,
626: # verifikere indholdet, og rydder op igen — uden at påvirke kørende system
640: ## 9. nginx og offentlig adgang
642: ### 9.1 Konfigurationsfil
653: # eller
657: ### 9.2 TLS-certifikat fornyelse
660: # Let's Encrypt via certbot
665: ### 9.3 Tjek nginx status
676: ## 10. Databaseadministration
679: # Log ind i PostgreSQL
682: # Se captures pr. kamera
687: # Se aktive brugere
690: # Se pending updates
693: # Opret ny bruger (via API er bedre)
700: ## 11. Brugerstyring
702: ### 11.1 Opret bruger
709: ### 11.2 Roller
718: ### 11.3 Nulstil password
721: # Via API (kræver super_admin-token)
730: ## 12. Troubleshooting
732: ### Headend starter ikke
735: # Se fejl
738: # Check venv
741: # Check PostgreSQL
745: # Check disk mount
749: ### Edge uploader ikke
752: # Via SSH til edge
755: # Test SFTP manuelt fra edge
759: ### CI fejler
762: # Se GitHub Actions log
765: # Lokal test
771: ### GPG-signering fejler
774: # Tjek nøgle
776: # Skal vise F75C248F694C097F
778: # Tjek trust
781: # Skal vise "ultimate"
786: ## 13. Sikkerhedsprocedurer
788: ### 13.1 Kompromitteret edge-enhed
795: ### 13.2 Mistanke om uautoriseret adgang til UI
802: ### 13.3 Rotation af JWT_SECRET
805: # Generer ny secret
808: # Opdater i LaunchAgent plist
810: # Ændr JWT_SECRET-værdien
812: # Genindlæs (invaliderer alle eksisterende sessions)
819: ## 14. Vigtige stier og referencer
841: ## 15. Roller og RBAC (governance)
843: Ud over rollerne i §11.2 opererer governance-dokumentationen med rollen `technician` (mellem operator og admin). Adminopgaver: opret bruger → tildel rolle + evt. kunde-scope → aktivér MFA/WebAuthn for admin/high-risk → gennemgå brugerliste jævnligt → fjern/deaktivér ubrugte konti → gennemgå audit-logs. Før Internet-go-live skal super_admin-password være ændret fra default, og højrisiko-operationer bør kræve MFA.
845: ## 16. Startup-preflight (før production)
847: Headend skal ved opstart verificere: `/Volumes/data-fast` monteret (forventet mount/UUID), skriveadgang til capture-root, nok ledig disk, PostgreSQL kører, Headend health svarer, node-agent kører, nginx på prod-kompliant portmodel.
849: ## 17. Kunde/site/kamera-model og Global Config
853: Global Config arves i fire lag: `global → kunde → site → kamera` (lavere lag vinder). UI skal vise arvet værdi, direkte override, effektiv værdi, vindende lag og farvemarkering for afvigelse fra global. Brug kamera-laget til relay power, ISO, fokusstrategi, storage-overrides og Nikon Z30-profildata.
855: ## 18. CMDB, SBOM og GRC (detaljeret)
857: **CMDB** skal vise: installeret OS/version, systempakker, Python/venv-pakker, TimeLapse Pro-version, hardware model, firmware/kernel, seneste tilgængelige version, risikoklassifikation, update-status, evidence-freshness.
861: **GRC/compliance-dashboard** skal kunne rapportere mod: SABSA business attributes, ISO 27001 control evidence, IEC 62443 zones/conduits + patching, CRA secure update/SBOM/lifecycle, NIS2 risk/continuity/supply-chain, GDPR DPIA/retention/access. Før første kunde-site: DPIA-template klar, retention pr. kamera sætbar, databehandleraftale-template klar, subprocessor-liste dokumenteret (især Gemini/Google Cloud).
863: ## 19. Kendte tekniske gældspunkter (governance-backlog)
865: - ~~`slowapi` importeres i backend men mangler i `headend/requirements.txt`~~ — **Rettet, committet (`b0e224c`) og live-verificeret 2026-07-03** (Claude/Peter): `requirements.txt` er pinnet til konkrete versioner (var 100% upinnet), `slowapi` tilføjet, installeret i prod-venv.
871: - Open WebUI skal besluttes som prod-komponent eller lab-only.
872: - postprocessing af manglende thumbnails skal gøres robust.
873: - per-target update-status skal vises tydeligere i UI.

## Dokumentation/ADR/ADR-0007-Evolution-from-Product-to-Platform.md

1: # ADR-0007
2: # Evolution from Product to Platform
7: ## Context
11: The common capabilities belong in a reusable platform. Timelapse should become the first reference implementation rather than define the platform forever.
13: ## Decision
21: ## Vision
36: ## Naming
42: ## Review Trigger

## Dokumentation/ADR/ADR-001-platform-payload-split.md

1: # ADR-001: Platform/Payload-snit for edge-arkitekturen
10: ## Kontekst
15: 2. **Produktambition.** Produktet skal kunne løftes fra et rent timelapse-produkt til en generisk edge-platform, der også kan drive små vandværker, vindmøller, solceller m.m., med sikker remote access via edgen til bagvedliggende (OT-)backendsystemer.
19: Beslutningen skal træffes **før** yderligere kodeflytning (P2-01), så refaktorering sker mod et aftalt mål frem for ad hoc.
23: ## Beslutning
27: ### 1. To lag med klart ejerskab
34: ### 2. Koblingen er én kontrakt: `PayloadDriver` + capability manifest
56: ### 3. Repo-model: monorepo nu, migrerbar til pakke senere
60: ### 4. Kontrakt-versionering = SemVer
64: ### 5. Navngivning: neutral fremad, additiv bagud
68: ### 6. Sikkerhed indbygget, ikke bagpå
72: ### 7. Governance bliver bindende
78: ## Amendments 2026-07-16 (efter Codex-review — accepteret af Claude, indarbejdet i beslutningen)
82: 1. **Isolation er en enforcement-grænse, ikke bare en deklaration.** En in-process Python-`PayloadDriver` + manifest giver IKKE i sig selv CPU/RAM/disk/net/credential-isolation eller fault containment. Når ADR'en lover isolation, skal payloaden køre i en **separat OS-sandboxet proces/service** (eller tilsvarende enforcement boundary). Manifestet er *deklaration*; **platform-policy er autoritativ enforcement**.
85: 4. **Failure contracts skal beskrives:** timeout, backpressure, crash/restart, degraded mode, resource exhaustion, kompatibilitetsmatrix (platform↔payload-versioner) og rollback ved defekt/inkompatibel payload.
86: 5. **Konkrete trust boundaries/zoner/conduits.** Remote support og leverandøradgang kun via JIT/AccessTicket, kortlivede identiteter, destinations-allowlist, session-audit, revocation og kill switch (skærper §6 fra "indbygget" til normativt krav).
93: ## Alternativer overvejet
102: ## Konsekvenser
105: - Refaktoreringen af monoliten (P2-01) får et mål: udtræk sker mod `platform/`-moduler, ikke ad hoc — så gæld-nedbrydning og modularisering er samme arbejde og betaler sig hjem uanset verticals.
120: ## Standardmapping
130: ## Afgrænsning (ikke besluttet her)
137: **Langsigtet vision (kontekst, ikke besluttet her):** Peters mål er at kunne open-source en sikker platform for mindre OT-installationer (vandværk, solceller, vindinstallationer m.m.), der kombinerer beskyttelse og effektiv drift. Visionen udvikles gennem ADR'er og threat modelling — **ikke** gennem for tidlig generalisering af produktkoden. Open source reducerer ikke i sig selv risiko; secure-by-design og et dokumenteret trust-økosystem er forudsætninger.
141: ## Opfølgning ved accept
150: ## Revisionslog
154: | 2026-07-15 | Førsteudkast (Proposed): platform/payload-snit, `PayloadDriver`+manifest, monorepo-model A, SemVer, additiv navngivning, K1–K6. | Claude |
155: | 2026-07-16 | Amendments indarbejdet efter Codex' uafhængige review: (1) proces-isolation som enforcement-grænse, (2) control/data-plane som separate kontrakter, (3) fail-closed capability-validering mod signeret allowlist, (4) failure contracts, (5) normativ JIT/conduit-kontrol, (6) additiv gate-styret migration; + AI-domænesnit; + multi-vendor trust som fremtidig ADR; + open-source OT-vision som kontekst. | Claude (efter Codex-review) |
156: | 2026-07-16 | Codex bekræftede at alle amendments var korrekt indarbejdet og anbefalede accept. **Status → Accepted af Peter.** Binding skrevet ind i `00_START_HER.md`. | Peter (beslutning) |

## Dokumentation/ADR/ADR-003-pakke-hygiejne-mod-legacy-branches.md

1: # ADR-003: Pakke-hygiejne — forebyggelse af overhalet/glemt arbejde på tværs af AI-sessioner
4: - **Accept:** Peter, 2026-09-13, efter Claude/Kimi-genreviews og instruktion om at afslutte det reviewede arbejde. Omfatter ADR-003 og §14; ikke implementering af de åbne opfølgningsspor.
7: - **Historisk review af #230, selvrapporteret identitet; ikke accept af senere syntese:** Kimi 2026-09-13 — **tiltræder ADR'en uden ændringskrav**. Verificerede kontekst-påstandene mod repoet (127 branches, #163/#159-conflicts) og bidrog med den målte branch-klassificering i `PAKKE_SPOR_REGISTER.md` §Backlog. Én metode-præcisering: sweeps skal bruge patch-ækvivalens (`git cherry`), da `git log main..<branch>` fejlagtigt viser squash-mergede branches som ikke-mergede.
10: ## Kontekst
12: Peter rejste en konkret bekymring 2026-09-13: da PR #214 viste sig at være `BEHIND` main, opstod spørgsmålet om hvorvidt en opdatering til branchen risikerer at overskrive eller kritikløst "overhale" arbejde, der reelt stadig mangler at blive integreret. En efterfølgende gennemgang bekræftede at bekymringen er velbegrundet i praksis, ikke kun i teori:
14: - Ved den oprindelige forespørgsel blev der uformelt talt **ca. 127 remote branches** (`git branch -r`, ikke frosset/verificeret) — historisk kontekst-estimat, ikke et verificeret grundlag. Kun en håndfuld havde en åben PR. Det senere bevarede, reproducerbare grundlag er **122–123 branches** ekskl. main (to uafhængigt frosne populationer, forskel forklaret); se `PAKKE_SPOR_REGISTER.md` §Backlog for metode og data.
16: - Claudes foreløbige strengsøgning gav indikation af, at de to PR'er ikke var fuldt overhalet — den funktionalitet de tilføjer (post-restart health-stabilitetsvindue + Headend-sweeper i #163; eksplicitte lokal/UTC-tidsfelter fra capture-API'et i #159) blev ikke fundet ved den beskrevne søgning. Det er screening fra samme forfatter, ikke en fuld uafhængig semantisk gennemgang; genverifikation udestår før integration.
20: ## Beslutning — hvad og hvorfor
22: Beslutningen fastlægger bevaring af relevant restindhold, synlig koordinering før ændringer og dokumenteret disposition før oprydning. Det skal forebygge tab af kode, tests, idéer og beslutningshistorik på tværs af parallelle sessioner. Registret giver overblik; handover bevarer hændelser; faktiske Git/GRC/CMDB-kilder forbliver autoritative for deres respektive tilstande.
26: ## Alternativer overvejet
33: ## Konsekvenser
45: - Løser ikke i sig selv de branches der endnu ikke er trieret (127/124 var ubekræftede tidlige estimater, ikke et verificeret tal; det bevarede, reproducerbare grundlag er 122–123 branches ekskl. main — se `PAKKE_SPOR_REGISTER.md` §Backlog). Denne ADR fastlægger *processen fremadrettet*; den fulde historiske oprydning er et separat, afgrænset arbejde.
47: ## Standardmapping
53: ## Afgrænsning
57: ## Samlet præcisering — Claude, Kimi og Codex, 2026-09-13
63: `git cherry` sammenligner individuelle patch-ID'er og er et screeningsværktøj. Flere commits squash-merget til én kan stadig fremstå unikke. Hverken 0 unikke commits, patch-ækvivalens, alder eller en lukket PR er alene slettebevis. Restindhold, worktrees, uncommitted/untracked materiale, aktive sessioner, release-/rollbackreferencer og holdbar recovery skal være afklaret. Delvist overhalede spor gennemgås pr. krav/idé; beslutningshistorik bevares.
65: Registerets ældre tal er historiske observationer og ikke autoriseret slettekø. Se korrektion og metodebegrænsning dér. Framework/Platform-input i samarbejdsmodellens §15 er foreslået videre arbejde, ikke en vedtaget udvidelse af nogen af de to repositories.

## Dokumentation/ADR/ADR-004-development-and-recovery-shell-access.md

1: # ADR-004: Development and Recovery Shell Access
8: ## Kontekst
10: TimeLapse Pro er tidligt i sin udviklings- og stabiliseringsfase. `agent/core-design-principles`-dokumentet (2026-07-31, Proposed) foreslår "No General-purpose Shell" som et målprincip for lokal service-adgang — ingen vilkårlig kommandokørsel i normal service-mode. En efterfølgende R04-branchtriage (2026-09-13) fandt at main allerede har et sådant general-purpose shell-endpoint (`/mgmt/cli/bash/ws` i `edge/scripts/totp-service.py`, en root-PTY-bash bag Bluetooth-TOTP-portalen), og at en aldrig-merget branch (`codex/edge-terminal-renderer`) indeholder ureviewede forbedringer til netop dette endpoint.
14: Peter har efterfølgende truffet en eksplicit lifecycle-beslutning: i den nuværende udviklings-/stabiliseringsfase vejer **recoverability og diagnosability højere end at eliminere general-purpose shell-adgang**. Peter skal uden større problemer kunne få fuld adgang til en edge til fejlsøgning og recovery, også når agent, Headend eller andre højere lag fejler. At fjerne, begrænse eller erstatte shell'en med typed operations på nuværende tidspunkt ville aktivt modarbejde dette behov, før der er evidens for at systemet er stabilt nok til at undvære det.
16: ## Beslutning
18: **General-purpose/root shell-adgang via `/mgmt/cli/bash/*` er en bevidst accepteret development/stabilization-capability i denne fase af projektet.** Den fjernes ikke, begrænses ikke på en måde der gør recovery vanskeligt, og erstattes ikke af typed/capability-baserede operationer, før et fremtidigt review (se §Review-kriterier) beslutter andet.
23: 2. **Transskript-logging vurderes, men loves ikke ubetinget.** Break-glass-forsøget på fuld transskript-optagelse (`script -f -q -c ...`) blev forladt pga. reelle PTY-relæ-kompatibilitetsproblemer (dobbelt-PTY ødelagde terminal-echo på visse klienter). `/mgmt/cli/bash/ws` har en gunstigere arkitektur til dette (Python-koden ejer selv PTY'en direkte via `pty.fork()`, uden et ekstra sshd-PTY-relæ imellem) — transskript-optagelse er derfor sandsynligvis lettere at få til at virke pålideligt her end det var for break-glass, men skal verificeres konkret, ikke antages.
24: 3. **Fail-closed er allerede på plads og skal forblive uændret:** `management.enable_interactive_shell` er `False` som standard (verificeret i `_default_config()`), synkroniseret fra Headend's centrale `service_access.interactive_shell_enabled`-politik, og WebSocket-handleren lukker forbindelsen (kode 1008) hvis flaget ikke er sat. Denne fail-closed-adfærd bevares som den primære centrale kontrol.
26: 5. **Ingen ny ekstern afhængighed må kunne blokere lokal recovery.** Enhver kontrol indført under dette punkt skal fungere fuldt ud lokalt uden Headend/netværk til stede — dette er en hård grænse, ikke en anbefaling.
28: ## Alternativer overvejet
31: - **Begræns shell'en til kun break-glass-lignende, meget restriktiv brug allerede nu:** afvist for nu — det er præcis den beslutning der er udskudt til det fremtidige review, ikke noget der skal forhåndsbesluttes.
34: ## Konsekvenser
46: - Denne ADR ændrer ikke `agent/core-design-principles`s status — dokumentet forbliver Proposed, bevaret som muligt fremtidigt målprincip, ikke kasseret.
48: ## Standardmapping
54: ## Review-kriterier (ikke en dato)
61: - Antallet af hændelser hvor shell reelt var nødvendigt (ikke bare tilgængeligt) er lavt og faldende, målt via den nye audit-log.
63: ## Afgrænsning
68: - Erstatter ikke `agent/core-design-principles`s "No General-purpose Shell"-forslag — den forbliver et gyldigt fremtidigt målprincip, som denne ADR midlertidigt fraviger, ikke forkaster.

## Dokumentation/ADR/README.md

1: # Architecture Decision Records (ADR)
7: ## Regler
12: - **Reference i PR.** Arkitekturændringer bør referere den ADR de udmønter.
14: ## Status-værdier
18: ## Skabelon
21: # ADR-XXX: <kort titel>
28: ## Kontekst
31: ## Beslutning
34: ## Alternativer overvejet
37: ## Konsekvenser
40: ## Standardmapping
43: ## Afgrænsning
47: ## Register
51: | [ADR-001](ADR-001-platform-payload-split.md) | Platform/Payload-snit for edge-arkitekturen | **Accepted 2026-07-16** |
52: | [ADR-003](ADR-003-pakke-hygiejne-mod-legacy-branches.md) | Pakke-hygiejne — forebyggelse af overhalet/glemt arbejde på tværs af AI-sessioner | Accepted 2026-09-13 |
53: | [ADR-004](ADR-004-development-and-recovery-shell-access.md) | Development and Recovery Shell Access — lifecycle-afhængig accept af general-purpose edge-shell | Proposed 2026-09-13 |

## Dokumentation/AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md

1: # TimeLapse Pro - aggregeret kravregister for update, change, provisioning og drift
5: **Formål:** Samle krav fra alle dokumenter i `Dokumentation/`, inklusive ældre versioner og chat-/arbejdsdokumenter, uden at reducere detaljegrad.  
8: ## Læseprincipper
10: - Nyeste/gældende dokumenter vægtes højest, men ældre dokumenter må ikke ignoreres. Ældre krav markeres som historiske, konflikter eller kandidater, hvis de ikke findes i nyeste materiale.
11: - Krav med sikkerheds-, compliance- eller driftskonsekvens bevares, selv hvis de kun findes i chat-dumps eller tidlige roadmap-versioner.
15: ## Kildegrundlag
37: ## Overordnet målmodel
39: TimeLapse Pro skal understøtte en livscyklus fra R&D/LAB til produktion:
49: ## Kravregister
51: ### UPD-001 - Update-systemet skal være policy-drevet og hierarkisk
53: **Krav:** Systemet skal kunne afgøre auto/manual update-policy ud fra et hierarki: global default -> kunde -> site -> kamera/device -> runtime override.
57: - Policy skal kunne sættes forskelligt for `app_security`, `app_updates`, `os_security` og `os_updates`.
58: - Mere restriktiv policy skal kunne vinde over en mere åben nedarvet policy.
59: - Manual approval skal kunne kræves for udvalgte kunder, sites, kameraer eller devices.
60: - Auto-deploy skal kunne tillades, hvis kunden/site/kameraet er konfigureret til det.
67: ### UPD-002 - Update-scope skal understøtte global, kunde, site, kamera og device
69: **Krav:** En opdatering skal kunne målrettes globalt, til en kunde, et site, et kamera eller en konkret fysisk edge/device.
73: - Eksisterende `scope` dækker `global|customer|site|device`, men kamera/logisk camera bør også kunne være scope.
74: - Kamera-scope skal respektere Camera/DeviceAssignment-modellen, så et fysisk device kan udskiftes uden at miste policyhistorik.
75: - UI skal vise effektivt scope og hvilke devices/kameraer der rammes.
79: **Implementeringsstatus:** Delvist. `PendingUpdate.scope` findes, men UI er reduceret til global/device i approval modal, og kamera-scope mangler.
81: ### UPD-003 - App updates må ikke forudsætte direkte GitHub-adgang fra Edge
83: **Krav:** Edge-enheder skal kunne opdateres uden direkte internetadgang eller direkte GitHub-adgang. Headend skal være update authority/proxy.
88: - Headend skal hente, verificere og pakke app-release/artifact.
89: - Edge skal hente artifact fra Headend, ikke `git fetch origin main` direkte.
96: ### UPD-004 - Headend skal producere verificerede update artifacts
98: **Krav:** Headend skal producere eller cache et verificeret artifact pr. app-release, egnet til offline/Headend-mediated Edge-update.
103: - Artifact skal have manifest med mindst: release id, target commit, source branch/tag, build timestamp, hash, signer, test-resultat, SBOM-reference og rollback target.
104: - Artifact skal være immutable efter godkendelse.
105: - Artifact skal kunne distribueres til edge via API eller SFTP uden at edge kender GitHub.
109: **Implementeringsstatus:** Mangler.
111: ### UPD-005 - Update artifacts og change tickets skal være signerede
113: **Krav:** Alle app-release artifacts og tilhørende change tickets skal signeres kryptografisk.
117: - Commit/tag-signatur alene er ikke nok; change ticket og artifact-manifest skal også signeres.
118: - Signatur skal kunne verificeres maskinelt på Headend og, hvor muligt, på Edge.
119: - Signeret ticket skal kunne eksporteres til kunde eller kundens ticketing-system.
120: - Signering af brugeraccept skal knyttes til logged-in user, rolle, tidspunkt, IP/user-agent og eventuel MFA/WebAuthn kontekst.
124: **Implementeringsstatus:** Delvist på Git-commit niveau. Mangler ticket-/manifest-signering og user approval signature.
126: ### UPD-006 - Change ticket skal være både menneske- og maskinlæsbart
128: **Krav:** For hver update skal der genereres et change ticket i et format der både kan læses af mennesker og parse's af systemet.
133: - Ticket skal mindst indeholde:
144:   - reboot requirement
153: **Implementeringsstatus:** Mangler.
155: ### UPD-007 - UI skal understøtte review og godkendelse af change ticket
157: **Krav:** UI skal vise alle relevante change-ticket felter før godkendelse, og godkendelseshandlingen skal være eksplicit og auditérbar.
161: - UI må ikke nøjes med en "Godkend" knap uden detaljer.
162: - Bruger skal kunne se scope, severity, update-type, release notes, teststatus, rollback-plan, reboot/downtime og signaturstatus.
163: - UI skal kunne kræve MFA/WebAuthn ved højrisikoændringer.
164: - UI skal kunne eksportere eller downloade ticket til kundeaccept.
165: - UI skal kunne registrere ekstern kundeticket-reference.
169: **Implementeringsstatus:** Delvist. `UpdatesPage.tsx` viser basale oplysninger og approve/reject, men mangler ticketvisning, signatur, kundeaccept og MFA-gating.
171: ### UPD-008 - Rollout skal være staged og kontrolleret
173: **Krav:** Update rollout skal kunne ske i faser: R&D/LAB -> staging/test -> pilot -> production.
177: - En update skal kunne godkendes til test først og derefter promoveres til production.
179: - Scope skal kunne begrænses i hver fase.
180: - Systemet skal vise deployed/failed counts og status pr. device.
185: **Implementeringsstatus:** Delvist. `promote_update` findes, men mangler robust status pr. target og gating.
187: ### UPD-009 - Rollback skal være automatisk ved fejlet update
189: **Krav:** Edge og Headend skal automatisk rollbacke ved fejlet update efter definerede health criteria.
193: - App update rollback skal bruge kendt tidligere version/artifact.
194: - Healthcheck skal mindst kontrollere service-active, heartbeat, API-kommunikation og eventuelt capture-loop.
195: - Rollback-resultat skal rapporteres til Headend.
196: - Hvis rollback fejler, skal der oprettes kritisk alarm og manuel intervention.
197: - Rollback skal være testet som en del af release acceptance.
203: ### UPD-010 - Maintenance window og reboot-policy skal være konfigurerbar
205: **Krav:** Update execution skal respektere maintenance window og reboot-policy på relevant scope.
209: - Policy skal kunne definere tilladt tidsvindue.
211: - OS-kernel/security updates skal kunne markeres som reboot-required.
212: - Capture schedule skal indgå i beslutningen, så opdatering ikke afbryder vigtige optagelser.
216: **Implementeringsstatus:** Delvist/mangler. Default `maintenance_window` findes i policy response, men enforcement er ikke tydelig.
218: ### UPD-011 - OS security og OS functional updates skal håndteres særskilt
220: **Krav:** OS security updates og funktionelle OS updates skal klassificeres, godkendes og deployes separat.
224: - `os_security` skal kunne have højere default prioritet end `os_updates`.
226: - Funktionelle OS updates bør typisk være manual eller staged.
227: - apt/package-list og reboot-required skal indgå i ticket.
228: - OS update resultater skal rapporteres og auditeres.
232: **Implementeringsstatus:** Delvist. Edge indsamler apt info og backend opretter `PendingUpdate`, men ticket, package details og robust result audit mangler.
234: ### UPD-012 - Tredjepartsapplikationer og dependencies skal indgå i update governance
236: **Krav:** Update-systemet skal håndtere ikke kun Timelapse-app og OS, men også afhængigheder og nødvendige tredjepartsapplikationer.
240: - Python dependencies, Node/npm dependencies, gphoto2, nginx, PostgreSQL, Ollama/Gemini-integration, certbot, fail2ban og systemd units bør kunne spores.
241: - SBOM skal genereres og opdateres ved release.
242: - Vulnerability status bør kunne knyttes til change ticket.
246: **Implementeringsstatus:** Mangler samlet model. Inventory findes delvist.
248: ### UPD-013 - Change og update audit trail skal være komplet
250: **Krav:** Alle update-relaterede handlinger skal logges med tilstrækkelig evidens.
254: - Oprettelse, ticket generation, artifact creation, approval, rejection, promotion, deployment start, deployment success/failure, rollback request/result og export til kunde skal auditeres.
255: - Audit skal inkludere actor, rolle, tenant/customer context, timestamp, IP/user-agent, MFA/WebAuthn status og signature/hash.
256: - Audit skal være tenant-isoleret og egnet til kundedokumentation.
262: ### UPD-014 - Update-status skal spores pr. target
264: **Krav:** En update med flere targets skal have status pr. device/kamera, ikke kun global status på `PendingUpdate`.
268: - Per-target status skal kunne være pending, approved, downloading, deploying, healthcheck, deployed, failed, rolled_back, skipped.
269: - `deployed_count` og `failed_count` skal udledes fra per-target records.
270: - UI skal kunne vise hvilke devices der mangler, fejlede eller rullede tilbage.
274: **Implementeringsstatus:** Mangler per-target tabel/model.
276: ### UPD-015 - Edge skal bevare autonom drift under update og netværksudfald
278: **Krav:** Edge må fortsætte capture/store-and-forward under Headend- eller netværksudfald og må ikke efterlades i halvopdateret tilstand.
282: - Edge skal have lokal config cache og lokal DB/circular buffer.
283: - Update skal være atomisk eller have tydelig staging/activation.
284: - Hvis update artifact ikke kan downloades/verificeres, skal Edge fortsætte på eksisterende version.
291: ### PROV-001 - Ny Edge provisioning skal være zero-touch eller near-zero-touch
293: **Krav:** En ny edge skal kunne startes på rå OS med minimal manuel handling og registrere sig mod Headend.
297: - Headend skal generere bootstrap package med `bootstrap.yaml`, device id, headend URL, bootstrap token, CA cert og eventuelle initiale nøgler.
298: - Edge skal kunne hente effektiv konfiguration fra Headend efter bootstrap.
299: - Bootstrap token skal være engangsbrug eller tidsbegrænset.
306: ### PROV-002 - Headend skal kunne generere OS-tilretning og app-installation for Edge
308: **Krav:** Provisioning skal kunne installere/konfigurere nødvendige OS-pakker, services og Timelapse-komponenter på edge.
312: - OS hardening, package install, Python venv, systemd service, watchdog, gphoto2, GPIO, modem/network tools og logging skal kunne beskrives som provisioneringsprofil.
313: - Provisioning skal være idempotent.
314: - Resultat skal rapporteres til Headend som provisioning status.
315: - Production provisioning bør ikke kræve rå databasekald eller manuel filkopiering.
319: **Implementeringsstatus:** Mangler samlet orchestreret provisioning. Runbooks findes.
321: ### PROV-003 - Provisioning skal generere og rotere device-nøgler
323: **Krav:** Headend skal håndtere device-nøgler, client certs og SSH tunnel-nøgler med lifecycle og revokering.
328: - Device client certs bør have udløb og rotation.
329: - SSH keys skal kunne genereres, installeres, begrænses og revokeres.
330: - Kompromitteret edge skal kunne isoleres ved at tilbagekalde cert/nøgle.
334: **Implementeringsstatus:** Delvist/planlagt.
336: ### PROV-004 - Kold og varm backup Headend skal indgå i provisioningmodellen
338: **Krav:** Systemet skal kunne etablere og genskabe Headend fra backup, inklusive varm/kold standby-scenarier.
342: - Backup Headend skal kunne få nødvendige certs, DB backup, artifact store, configuration, keys og UI/backend services.
343: - Failover/restore skal have dokumenteret RTO/RPO.
344: - Edge skal kunne kende primær og eventuel fallback Headend, uden at bryde trust/pinning.
345: - Kold backup skal kunne provisioneres fra rå OS.
349: **Implementeringsstatus:** Delvist. Backup findes i UI/runbooks, men standby/failover architecture mangler.
351: ### PROV-005 - Backup og restore skal testes og dokumenteres
353: **Krav:** Backup må ikke kun eksistere; restore skal testes og kunne dokumenteres.
358: - Backup-testprocedure mangler og skal etableres.
359: - Restore-test skal kunne generere audit/resultat.
360: - Kunde-/tenantdata skal bevares adskilt og krypteres.
366: ### SEC-001 - Compliance-targets skal være eksplicitte i design og tickets
368: **Krav:** Update/provisioning-systemet skal understøtte krav fra ISO 27001:2022, NIS2, CRA og IEC 62443.
381: ### SEC-002 - Secrets og runtime caches må ikke committes
383: **Krav:** Secrets, runtime caches, exports og backup artifacts må ikke indgå i Git.
387: - `secrets/`, service accounts, exported DB data, `.bak` og generated snapshots skal håndteres uden for Git.
388: - Edge runtime cache som `edge/sftp_cache.yaml` skal ignoreres og have stramme permissions.
393: **Implementeringsstatus:** Delvist. Der er signeret commit for `edge/sftp_cache.yaml` ignore og future `chmod(0600)`.
395: ### SEC-003 - Tests skal være gate før deploy
397: **Krav:** Der skal være et test/staging-gate før deployment til Edge og production Headend.
405: - Testresultater skal indgå i change ticket.
411: ### CFG-001 - Alle konfigurationsparametre skal kunne administreres fra UI
413: **Krav:** Det skal "aldrig" være nødvendigt at ændre rå database eller kode for timing/operationelle parametre.
417: - Central admin UI skal vise og ændre alle config-parametre.
418: - Effective/merged config pr. kamera skal kunne vises.
419: - LAB mode ændringer skal kunne gemmes for aktuelt kamera og uploades til Headend.
420: - Nedarvning skal følge Default -> Kunde -> Site -> Kamera.
426: ## Konflikter og beslutninger
428: ### CON-001 - Edge direct GitHub pull vs. Headend-mediated update
430: **Observation:** Ældre roadmap/runbooks beskriver `git pull` på Edge, Git deploy keys og Edge self-update direkte fra origin. Nyere brugerkrav og production constraints siger, at Edge ikke nødvendigvis har Internet og skal opdateres via Headend.
432: **Foreløbig beslutning:** Production design skal være Headend-mediated. Direkte GitHub kan kun være R&D/LAB nødfunktion, tydeligt markeret og disabled by policy i prod.
436: ### CON-002 - SQLite vs. PostgreSQL Headend
440: **Foreløbig beslutning:** R&D/LAB kan have historiske SQLite/Pi spor, men production Headend bør være Mac Mini/PostgreSQL som aktuel installationsguide. Backup/failover skal tage højde for PostgreSQL.
444: ### CON-003 - MAC-baseret identity vs. cert/key-baseret identity
448: **Foreløbig beslutning:** MAC-afledt ID kan være bootstrap convenience, ikke production trust anchor. Production identity skal være cert/key-baseret.
452: ### CON-004 - Single PendingUpdate status vs. per-target deployment state
460: ### CON-005 - Change ticket format
466: ## Foreslået datamodel - arbejdsskitse
468: ### `change_tickets`
500: ### `change_approvals`
516: ### `update_targets`
535: ### `update_artifacts`
550: ## Foreslået change ticket JSON - første udkast
593:     "required": true,
601: ## Næste analyseopgaver
603: 1. Udtræk alle unikke krav fra chat-dumps uden at blande fejlrettelseslogs og midlertidige kommandoer ind som permanente krav.
604: 2. Markér krav som `current`, `historical`, `conflict`, `implemented`, `partial`, `missing`.
613: 4. Beslut ticket-format og signeringsmekanisme.

