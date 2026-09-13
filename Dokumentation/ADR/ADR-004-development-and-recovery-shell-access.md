# ADR-004: Development and Recovery Shell Access

- **Status:** Proposed
- **Dato:** 2026-09-13
- **Beslutningstagere:** Peter (beslutningsejer og risikoejer for denne beslutning)
- **Kontekst-referencer:** `Dokumentation/EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_2026-09-13_CLAUDE.md` (read-only assessment af `/mgmt/cli/bash/*`), `Dokumentation/Arkitektur/CORE_DESIGN_PRINCIPLES_ANALYSE_2026-09-13_CLAUDE.md` (§D, "No General-purpose Shell"-princippet denne ADR midlertidigt fraviger), `Dokumentation/R04_BRANCHTRIAGE_BATCH_2_2026-09-13_CLAUDE.md` (stop-gate-fundet der udløste denne beslutning), `edge/scripts/totp-service.py`, `edge/scripts/breakglass_shell_wrapper.sh`, `edge/agent.py::_repair_emergency_breakglass_account()`.

## Kontekst

TimeLapse Pro er tidligt i sin udviklings- og stabiliseringsfase. `agent/core-design-principles`-dokumentet (2026-07-31, Proposed) foreslår "No General-purpose Shell" som et målprincip for lokal service-adgang — ingen vilkårlig kommandokørsel i normal service-mode. En efterfølgende R04-branchtriage (2026-09-13) fandt at main allerede har et sådant general-purpose shell-endpoint (`/mgmt/cli/bash/ws` i `edge/scripts/totp-service.py`, en root-PTY-bash bag Bluetooth-TOTP-portalen), og at en aldrig-merget branch (`codex/edge-terminal-renderer`) indeholder ureviewede forbedringer til netop dette endpoint.

En efterfølgende read-only sikkerhedsassessment bekræftede: endpointet kører som root uden yderligere sandboxing, tillader vilkårlige kommandoer uden filtrering, og — vigtigst — **auditerer intet af selve sessionens indhold**, i modsætning til en sammenlignelig, allerede audited mekanisme andetsteds i systemet (break-glass SSH).

Peter har efterfølgende truffet en eksplicit lifecycle-beslutning: i den nuværende udviklings-/stabiliseringsfase vejer **recoverability og diagnosability højere end at eliminere general-purpose shell-adgang**. Peter skal uden større problemer kunne få fuld adgang til en edge til fejlsøgning og recovery, også når agent, Headend eller andre højere lag fejler. At fjerne, begrænse eller erstatte shell'en med typed operations på nuværende tidspunkt ville aktivt modarbejde dette behov, før der er evidens for at systemet er stabilt nok til at undvære det.

## Beslutning

**General-purpose/root shell-adgang via `/mgmt/cli/bash/*` er en bevidst accepteret development/stabilization-capability i denne fase af projektet.** Den fjernes ikke, begrænses ikke på en måde der gør recovery vanskeligt, og erstattes ikke af typed/capability-baserede operationer, før et fremtidigt review (se §Review-kriterier) beslutter andet.

**Sikkerhedsforbedringer indføres additivt, uden at reducere den faktiske recovery-evne:**

1. **Session-/audit-logging af shell-aktivering** — genbrug det allerede eksisterende, proven mønster fra break-glass SSH (`edge/scripts/breakglass_shell_wrapper.sh` + `edge/agent.py::_collect_breakglass_events_for_sync()`): en lokal, append-only JSONL-hændelseskø (`session_start`/`session_end`, tidsstemplet, med hvilken TOTP-`sid` og klient-IP der var aktiv), skrevet synkront og lokalt af `totp-service.py` selv — **ingen netværksafhængighed i selve skrivningen**. Forward til Headend SIEM sker asynkront via den eksisterende, allerede periodiske sync-cyklus i `edge/agent.py`, præcis som break-glass-hændelser i dag. Hvis Headend er utilgængeligt, skrives hændelsen stadig lokalt; kun SIEM-forwarding udskydes.
2. **Transskript-logging vurderes, men loves ikke ubetinget.** Break-glass-forsøget på fuld transskript-optagelse (`script -f -q -c ...`) blev forladt pga. reelle PTY-relæ-kompatibilitetsproblemer (dobbelt-PTY ødelagde terminal-echo på visse klienter). `/mgmt/cli/bash/ws` har en gunstigere arkitektur til dette (Python-koden ejer selv PTY'en direkte via `pty.fork()`, uden et ekstra sshd-PTY-relæ imellem) — transskript-optagelse er derfor sandsynligvis lettere at få til at virke pålideligt her end det var for break-glass, men skal verificeres konkret, ikke antages.
3. **Fail-closed er allerede på plads og skal forblive uændret:** `management.enable_interactive_shell` er `False` som standard (verificeret i `_default_config()`), synkroniseret fra Headend's centrale `service_access.interactive_shell_enabled`-politik, og WebSocket-handleren lukker forbindelsen (kode 1008) hvis flaget ikke er sat. Denne fail-closed-adfærd bevares som den primære centrale kontrol.
4. **Session-håndtering forbedres for robusthed uden at svække kontrol:** en dokumenteret, allerede designet rettelse (fra `codex/edge-terminal-renderer`, aldrig merget) løser et reelt reconnect-problem — en teknikers kildeIP kan legitimt ændre sig midt i en session på tværs af Bluetooth PAN/WiFi/Ethernet, og streng IP-pinning ville da afbryde en igangværende recovery-session. Løsningen sporer alle IP'er en gyldig session er set fra (logget), i stedet for at kræve nøjagtig IP-identitet — selve sessionstokenet (256-bit HMAC, kun udstedt efter korrekt TOTP) forbliver den reelle autentifikationsgrænse. Se separat anbefaling om denne branch.
5. **Ingen ny ekstern afhængighed må kunne blokere lokal recovery.** Enhver kontrol indført under dette punkt skal fungere fuldt ud lokalt uden Headend/netværk til stede — dette er en hård grænse, ikke en anbefaling.

## Alternativer overvejet

- **Fjern shell'en nu, erstat med typed operations (den oprindelige "No General-purpose Shell"-anbefaling):** afvist for nu. `/mgmt/cli/run` + `CLI_ALLOWED_FLAGS` dækker allerede mange scenarier typet, men ikke alle uforudsete debugging-/recovery-behov i en ung, ustabil kodebase. At fjerne den generelle shell nu ville fjerne en reel recovery-mulighed uden en påvist erstatning, i en fase hvor fejl stadig opstår i produktionslagene selv.
- **Begræns shell'en til kun break-glass-lignende, meget restriktiv brug allerede nu:** afvist for nu — det er præcis den beslutning der er udskudt til det fremtidige review, ikke noget der skal forhåndsbesluttes.
- **Vent med enhver sikkerhedsforbedring til efter det fremtidige review:** afvist. Assessmenten identificerede en reel, konkret mangel (ingen audit) der kan lukkes uden at koste noget af den ønskede recovery-evne — der er ingen god grund til at vente med det.

## Konsekvenser

**Positive:**
- Peter bevarer fuld, ubegrænset debugging-/recovery-adgang til edge-enheder, også når højere lag fejler.
- Shell-aktivering bliver synlig (hvem/hvornår), uden at det kræver Headend for at virke.
- Genbrug af et allerede bygget og proven mønster (break-glass-audit) reducerer implementeringsrisiko markant sammenlignet med at designe en ny audit-mekanisme fra bunden.

**Negative / accepteret risiko:**
- Root, ufiltreret kommandokørsel forbliver muligt for enhver med gyldig TOTP-session og det centrale policy-flag sat. Kompenserende kontrol er audit og fysisk/TOTP-adgangsbegrænsning, ikke handlingsbegrænsning — samme model som break-glass SSH allerede bevidst bruger.
- Fuld transskript-logging er ikke garanteret opnåelig; i så fald er kompensationen kun start/slut-hændelser + hvem/hvornår, ikke hvad der faktisk blev udført.

**Neutrale:**
- Denne ADR ændrer ikke `agent/core-design-principles`s status — dokumentet forbliver Proposed, bevaret som muligt fremtidigt målprincip, ikke kasseret.

## Standardmapping

- **IEC 62443 (maintenance access path):** en normalt lukket, fysisk aktiveret vedligeholdelseskanal med audit er en anerkendt kontrolmodel selv når selve handlingen er ubegrænset — konsistent med hvordan break-glass allerede er begrundet i dette repo.
- **SABSA (Accountability/Auditability vs. Availability/Recoverability):** denne ADR er eksplicit en bevidst, tidsafgrænset prioritering af Recoverability/Maintainability over fuld Accountability — ikke et forsøg på at opnå begge samtidig på nuværende tidspunkt.
- Ingen direkte GDPR/NIS2-ændring; ren udviklings-/driftskontrol.

## Review-kriterier (ikke en dato)

Dette er bevidst **ikke** tidsbestemt. Et fremtidigt review udløses af evidens/modenhed, ikke en kalenderdato. Peter er beslutningsejer for selve review-tidspunktet, men følgende er kandidatindikatorer, når de samlet set peger på stabil drift over en passende periode:

- Remote diagnostics (Headend-side observability, CMDB, health-registre) dækker de use cases der i dag kræver lokal shell.
- Update-/recovery-flowet (agent-genstart, rollback, post-restart-health) har vist sig pålideligt over reel driftstid uden at kræve manuel shell-indgriben.
- De typede `/mgmt/cli/run`-operationer er udvidet til at dække de faktiske use cases, en shell hidtil har været brugt til (kræver at disse use cases først registreres, jf. §Afgrænsning).
- Antallet af hændelser hvor shell reelt var nødvendigt (ikke bare tilgængeligt) er lavt og faldende, målt via den nye audit-log.

## Afgrænsning

- Denne ADR beslutter **ikke** at fjerne, begrænse eller erstatte shell'en — det er eksplicit udskudt.
- Beslutter **ikke** implementeringsdetaljerne for audit-loggen (filformat, præcis event-skema) — det er en opfølgende, afgrænset implementeringsopgave.
- Beslutter **ikke** dispositionen af `codex/edge-terminal-renderer` som helhed — kun at dens relevante dele (session-robusthed) er identificeret som værdifulde til en senere, selvstændig, scoped implementering. Se separat anbefaling.
- Erstatter ikke `agent/core-design-principles`s "No General-purpose Shell"-forslag — den forbliver et gyldigt fremtidigt målprincip, som denne ADR midlertidigt fraviger, ikke forkaster.
