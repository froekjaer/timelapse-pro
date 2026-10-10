# Raw archaeology extract — current 008

## Dokumentation/Compliance-Readiness-Pack/05_ISO_NIS2_CER_SUPPLIER_ASSURANCE.md

1: # ISO 27001, NIS2 And CER Supplier Assurance
6: ## 1. Assurance statement
12: ## 2. Control summary
17: | Device identity | Edge lifecycle/credential inventory, WP-4 target model | Delvist/aktivt |
20: | Incident response | SEC-013 procedure | Skrevet, tabletop mangler |
21: | Vulnerability handling | SEC-014 procedure | Skrevet, operational SLA skal formalisere |
22: | Backup/restore | Backup docs/tests findes | Restore rehearsal mangler |
23: | Supplier management | Subprocessor matrix påbegyndt | Mangler kontrakt/evidence |
27: ## 3. NIS2 supplier evidence
38: - known residual risks and remediation roadmap.
42: - incident reporting thresholds skal kundetilpasses;
44: - supply-chain evidence skal færdiggøres for subprocessorer og dependencies;
45: - restore rehearsal skal dokumenteres med faktisk RTO/RPO.
47: ## 4. CER supplier evidence
49: Hvis kunden er kritisk enhed eller leverer til kritisk infrastruktur, bør TLP levere:
63: - krav til fysisk adgang og emergency support;
66: ## 5. ISO 27001 readiness map
68: | ISO-readiness område | Evidence | Gap |
70: | Asset inventory | CMDB/version inventory | Ownership matrix skal færdiggøres |
74: | Incident management | SEC-013 | Tabletop/rehearsal |
75: | Vulnerability management | SEC-014 | Operational SLA and recurring evidence |

## Dokumentation/Compliance-Readiness-Pack/06_AI_SYSTEM_INVENTORY.md

1: # AI System Inventory And AI Act Readiness
6: ## 1. AI principle
22: ## 2. AI system register
29: | Future AI Service Assistant | Teknisk hjælp | Logs/status/config | Forslag/diagnose | TBD | Må ikke udføre hardware uden Service Operations/capabilities | Ikke aktiv |
31: ## 3. Human oversight
35: - AI-output skal markeres som anbefaling/diagnostik hvor det kan påvirke teknikerbeslutning;
36: - tekniker/admin skal kunne se underliggende evidence;
41: ## 4. Data governance
47: | Provider/region documented | Mangler pr. deployment | Særligt cloud-AI |
48: | Retention documented | Delvist | Skal følge billede/metadata policy |
49: | Prompt/model versioning | Delvist | Skal bindes til release evidence hvor relevant |
50: | Bias/quality monitoring | Mangler | Relevant ved person-/arbejdspladskontekst |
52: ## 5. Classification gate
61: - dokumenter om kunden skal informere brugere/registrerede.

## Dokumentation/Compliance-Readiness-Pack/07_COMPLIANCE_ACCEPTANCE_GATE.md

1: # Compliance Acceptance Gate
5: ## 1. Pilot gate
18: ## 2. Controlled production gate
31: ## 3. Market/commercial compliance gate
43: ## 4. Red lines
53: ## 5. Recommended next work order

## Dokumentation/DOKUMENTPAKKE_OVERSIGT_v10.md

1: # TimeLapse Pro — Dokumentpakke (v10, konsolideret)
10: ## Autoritative dokumenter (v10)
15: | `KRAVREGISTER_og_STATUS_v10.md` | Samlet krav-/ønskeregister, bygget status, mangler og tidslinje |
16: | `GO_LIVE_CHECKLIST_v10.md` | Konkrete krav før Headend sættes på Internet og domænet skifter |
28: ## Kildegrundlag
39: ## Kendte uoverensstemmelser (historik → beslutning)
43: | Porte `80/443` | Ældre docs og aktiv nginx bruger public `80/443`; nyere krav siger TimeLapse ikke må eje dem på Mac Headend | ~~Public `80/443` må ejes af Cloudflare/website/proxy; Mac Headend-origin flyttes til `127.0.0.1:18443`~~ (**rettet, periodisk tjek #49:** denne 18443/Cloudflare Tunnel-anbefaling er forældet — CrushFTP ejer fortsat 80/443/21/22 på staging/prod-maskinerne, og backend eksponeres i stedet **direkte på port 8443**, certifikat via DNS-01 (`certbot-dns-cloudflare`), INGEN Cloudflare Tunnel; besluttet 2026-07-05, se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4) |
44: | SFTP port | Ældre docs bruger `22`/`2222`; nyere portprofil bruger `22222`, portplan foreslår `12222` | Ny production bør bruge `12222`; aldrig TimeLapse på `22` |
46: | Auth tokens i UI | Ældre docs siger ingen localStorage; aktuel UI bruger localStorage | Før production bør auth-cookie være primær, localStorage risikovurderes/ryddes |
48: | Update flow | Ældre scripts har `git pull`/apt-veje; nyere krav siger Edge må ikke bruge Internet | Legacy paths lab-only/opt-in; må ikke være production path |
49: | OS updates | Ældre flow brugte `apt-get upgrade`; nyere krav kræver Headend-signeret offline artifact | Kun offline artifact med manifest/signatur/hash og `apt-get --no-download` |
52: | Backup | Docs omtaler backup, men restore-test mangler | Ikke production-godkendt før restore-test foreligger |
54: | Open WebUI | UI/link findes, men service/rolle uklar | **Løst (2026-08-20-markeret):** Open WebUI-runtime er committet (`headend/openwebui_runtime.py`, R27 lukket), siden `/openwebui` er admin-gated, og Ollama-runtime-styring (Normal/Pause/Lav-memory) er bygget 2026-07-20. Status: lab-komponent med launchd + RBAC. Sektionen "Peter vil gerne lege med Ollama" er eksplicit eksperimentel |
56: | Storage | Ældre paths peger på `/Volumes/data`; aktiv storage er `/Volumes/data-fast` | `/Volumes/data-fast` er canonical; startup-preflight og single source of truth mangler |
58: ## Samlet status

## Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md

1: # TimeLapse Pro — DPIA-skabelon + Retention Policy (v1, udkast)
6: mangler) i `RISK_ASSESSMENT_v10.md`, samt GO_LIVE_CHECKLIST_v10.md §G-01/G-02.
9: juridisk kompetence) skal gennemgå og godkende indholdet, særligt retsgrundlag
14: ## 0. Hvorfor dette dokument
24:    audit-infrastruktur, men ikke skemalagt her; foreslås som opfølgning
33: ## 1. Rolleafklaring (controller/processor)
50: ## 2. DPIA-skabelon (pr. kunde/site)
56: ### 2.1 Grunddata
67: ### 2.2 Beskrivelse af behandlingen [TLP]
83:   (billeder af en byggeplads, ikke målrettet optagelse af personer). Der findes en
85:   (`GDPRDetection`, se §3), men **den tekniske komponent, der reelt skal udføre
88:   plads, skal det antages, at billeder KAN indeholde identificerbare personer uden
91: ### 2.3 Nødvendighed og proportionalitet [KUNDE + TLP]
97: | Er kameraets synsfelt afgrænset til byggepladsen (undgår offentlig vej/naboarealer)? | **[KUNDE]** — bør bekræftes ved opsætning; TLP kan levere `fov_horizontal_deg`/`azimuth_deg`-data fra kamerakonfigurationen som dokumentation |
100: ### 2.4 Risikovurdering [TLP + KUNDE]
105: | Uautoriseret adgang til billeder | Lav — RBAC + tenant-isolation implementeret, MFA påkrævet for admin | Middel-høj | Se `RISK_ASSESSMENT_v10.md` R02/R16 (begge lukkede) |
108: | Data sendt til cloud-AI (Gemini) uden for EU | Lav, men **skal bekræftes teknisk** | Middel-høj hvis bekræftet | Se §4 — regionsindstilling er IKKE verificeret i denne gennemgang, kun at koden STØTTER EU-region |
109: | Overskridelse af rimelig opbevaringsperiode | Lav-middel (automatisk sletning implementeret, men kræver per-kamera konfiguration) | Middel | Se §3 (retention policy) — **teknisk implementeret 2026-07-07** (Camera.retention_days, cleanup loop, API, UI, tests). Mangler: per-kamera konfiguration, verifikation i production. |
111: ### 2.5 Foranstaltninger og konklusion [KUNDE]
113: - Foreslåede foranstaltninger: **[KUNDE + TLP i fællesskab]**
115: - Skal Datatilsynet høres forud for behandlingen (GDPR art. 36)? **[KUNDE, vurderes typisk ikke nødvendigt for denne type behandling, men er en juridisk vurdering]**
119: ## 3. Retention policy — implementeret 2026-07-07
139: ### 3.1 Foreslået model
161: ### 3.2 Ikke inkluderet i dette udkast
164:   ikke kode. Foreslås som næste konkrete opgave, hvis Peter godkender modellen.
173: ## 4. Subprocessor-liste [TLP]
178: | Google Cloud / Gemini (Vertex AI eller AI Studio) | Cloud AI-billedanalyse ved eskalering | Billeder sendt til analyse, evt. inkl. personer i baggrunden | **Skal bekræftes:** `headend/ai/gemini_service.py` understøtter en EU-region-indstilling til Vertex AI-batch-processering (kodekommentar fremhæver eksplicit at bucket'en SKAL ligge i samme EU-region), men den faktisk KONFIGUREREDE region er ikke verificeret i denne gennemgang — kræver opslag i det faktiske deployment (miljøvariabler/GCP-projektindstillinger) |
180: | Cloudflare | Netværksrouting (Tunnel) til den offentlige webadresse | Transporterer trafik, herunder billeddata i transit | Bør bekræftes om Cloudflare har adgang til at inspicere/cache indhold, eller udelukkende router trafik (TLS-terminering-detaljer bør tjekkes) |
184: der skal rettes (potentiel tredjelandsoverførsel uden gyldigt overførselsgrundlag).
197: ## 5. Udkast til oplysningspligt (GDPR art. 13/14) [KUNDE, skabelon-tekst]
209: ## 6. Sammenhæng til øvrige dokumenter
213:   brudprocedure (G-06) mangler stadig og kræver en jurist.
215:   dokument: `gdpr_manager.py` mangler helt i kodebasen, hvilket betyder GDPR-

## Dokumentation/EDGE_GENERATOR_REVIEW_2026-08-03.md

1: # Edge Generator Review - 2026-08-03
3: ## Status
7: Det er en nødvendig release-kontrol; en endelig `.img.gz` skal derfor bygges fra et
10: ### Evidens
16: - Målrettede generator-/releasekontrakter: 40 bestået.
19: ## Med i et flashbart Orange Pi 4 Pro-image
43: ## Ikke med i image
49: - NPU C++-kilde og leverandørkilde. En kompileret, valideret NPU-komponent skal
56: ## Lokal serviceadgang
63:   klienten. En fremtidig destinationsliste skal være Headend-styret og bruge
69: ## Resterende før første endelige flash
78: 4. Godkend testresultatet før samme artifact eller release fremmes til staging

## Dokumentation/EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_2026-09-13_CLAUDE.md

1: # Read-only arkitektur-/sikkerhedsassessment — `/mgmt/cli/bash/*` på main
13: ## 1. Hvorfor blev endpointet introduceret?
17: - **[Inference]** Sammenholdt med at `/mgmt/cli/run` (den typede, allowlistede variant) allerede eksisterede på samme tidspunkt, ser den rå shell ud til at være en bevidst "escape hatch" for scenarier den typede CLI ikke dækker — men jeg har ikke fundet et skriftligt krav- eller designdokument der siger dette eksplicit. Jeg har ikke fundet en HANDOVER_LOG-entry med begrundelsen for denne specifikke commit.
19: ## 2. Hvilke dokumenter/PR'er/krav gav mandat til det?
21: - **[Verificeret]** Ingen HANDOVER_LOG-entry, ADR eller krav-/risikodokument nævner denne specifikke commit eller giver et eksplicit mandat til en generel shell. Jeg har søgt bredt (`git show <commit>:Dokumentation/HANDOVER_LOG.md` omkring datoen) uden resultat.
23: - **Konklusion:** endpointet blev ikke introduceret ud fra et separat, sporbart krav — det er en del af en bredere "forbedr teknikerens UI"-commit, efterfølgende hærdet reaktivt.
25: ## 3. Hvem/hvad kan tilgå det?
30: ## 4. Autentifikation og autorisation
33: - **[Verificeret]** Autorisation: **ingen rollemodel.** Der er kun én tilstand — "gyldig TOTP-session" — og den giver adgang til hele management-UI'et inklusive shell (hvis policy-flaget er sat). Der er ikke noget "Observer/Technician/Senior Technician"-hierarki som `agent/core-design-principles`-dokumentet foreslår (se separat analyse). Session-cookien er `httponly, secure, samesite=strict`, bundet til klient-IP (`_valid_token`), med konfigurerbar timeout (default 3600s).
36: ## 5. Hvilke privilegier har processen faktisk?
41: ## 6. Kan vilkårlige kommandoer udføres?
45: ## 7. Audit/logging
51: ## 8. Network exposure og binding
53: - **[Verificeret]** Kun `br-bt` (Bluetooth PAN-bridge), ikke det almindelige LAN/WAN-interface. `iptables`-default-deny undtagen port 8443, indtil TOTP-succes whitelister klient-IP'en specifikt. Ingen ekstern/offentlig eksponering identificeret — dette er en fysisk-nærhed-gated kanal, konsistent med `agent/core-design-principles`' princip 13 ("fysisk nærhed er ikke autentifikation," som her suppleres af TOTP — det er faktisk i tråd med princippet, ikke en overtrædelse af det, isoleret set).
55: ## 9. Failure modes
60: ## 10. Konkrete operationelle use cases shell'en løser
64: ## 11. Kan disse use cases løses med begrænsede, typede/capability-baserede operationer i stedet?
66: - **[Verificeret]** Delvist allerede sådan: `/mgmt/cli/run` + `CLI_ALLOWED_FLAGS` (28 navngivne flag: `--status`, `--doctor-json`, `--network-status`, `--camera-detect`, `--service-operation`, `--commissioning-report` m.fl.) dækker allerede en bred vifte af diagnosticerings- og servicehandlinger uden vilkårlig kommandokørsel. Dette er præcis det mønster `agent/core-design-principles` foreslår som målarkitektur (§43, "deny-by-default"-API).
67: - **[Inference]** Den rå shell er sandsynligvis bevaret for de tilfælde der IKKE er forudset i `CLI_ALLOWED_FLAGS` — men dette er i sagens natur svært at afgrænse på forhånd. En mere typet tilgang ville kræve enten (a) løbende udvidelse af det allerede eksisterende allowlist-mønster efterhånden som konkrete behov opstår, eller (b) en skarpt afgrænset, selv-auditeret "restricted shell" (fx en begrænset kommandotolk eller en read-only diagnostic-shell) i stedet for fuld bash. Jeg foreslår ikke en løsning her — kun at det eksisterende `/mgmt/cli/run`-mønster allerede er beviset på at det er teknisk muligt for de fleste kendte behov.
69: ## 12. Hvad ændrer `codex/edge-terminal-renderer`, og forbedrer det sikkerheden eller stabiliserer det blot?
75: ## 13. Relation til `stash@{3}`
81: ## Eksplicit sikkerhedsrisiko-markering — stop for Peters beslutning
87: Dette er ikke en påstand om at endpointet skal fjernes eller ændres — det er, som bedt om, en markering til din beslutning. Ingen ændring er foretaget.

## Dokumentation/FAIR_RISK_INPUT_MODEL_v1.md

1: # TimeLapse Pro - FAIR risk input model v1
3: ## Formål
7: ## Datakilder
9: ### Kommercielt input
11: Platformadministrator registrerer kundens månedlige servicepris med valuta, ikrafttrædelsesdato, kilde og validator. Alle ændringer opretter en ny version. Månedsprisen er en proxy for TimeLapse Pros omsætningseksponering, men er ikke automatisk kundens tab.
13: ### Kundeoplyst forretningsprofil
29: ## FAIR-beregning
40: ## Governance
43: - Månedspris kan kun læses og ændres af platformadministrator.
49: ## Næste trin
54: - Godkend Monte Carlo-antagelser og rapportformat før DKK-risiko vises som beslutningsgrundlag.

