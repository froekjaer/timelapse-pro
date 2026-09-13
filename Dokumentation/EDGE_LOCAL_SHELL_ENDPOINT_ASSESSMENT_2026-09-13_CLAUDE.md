# Read-only arkitektur-/sikkerhedsassessment — `/mgmt/cli/bash/*` på main

- **Model/session:** Claude (Sonnet 5, denne session)
- **Tidspunkt:** 2026-09-13
- **Baseline:** `origin/main` = `d04798e4ab4716832be576b3134e46b55a994ecf` (verificeret via `gh api` + `git ls-remote`)
- **Mandat:** Peter — read-only assessment, **ingen ændring/fjernelse/forbedring af shell-endpointet**.
- **Metode:** Læsning af `edge/scripts/totp-service.py` (main, 2212 linjer) i sin helhed, `edge/scripts/timelapse-totp.service`, `git log -S`/`git blame` for at datofæste introduktion og hærdning, samt read-only inspektion (`git diff`, `git stash show` — ingen pop/drop) af `stash@{3}`.

Hvert punkt er mærket **[Verificeret]**, **[Dokumenteret intention]** eller **[Inference]**, som bedt om.

---

## 1. Hvorfor blev endpointet introduceret?

- **[Verificeret]** Endpointet (`@app.websocket("/mgmt/cli/bash/ws")`, rå PTY-bash via `subprocess.Popen`) blev først tilføjet 2026-07-04, commit `00aa40a4` — "Enhance edge technician UI and CLI tools". På det tidspunkt var der **ingen** policy-gate; enhver gyldig TOTP-session kunne åbne shell'en.
- **[Dokumenteret intention]** UI-labelen ved siden af knappen (tilføjet 2026-07-14) siger: *"SSH bash — Interaktiv lokal shell på edgen bag TOTP-sessionen. Luk terminalen når du er færdig."* — dvs. eksplicit tiltænkt som en generel ad hoc-debugging-facilitet, ikke en afgrænset operation.
- **[Inference]** Sammenholdt med at `/mgmt/cli/run` (den typede, allowlistede variant) allerede eksisterede på samme tidspunkt, ser den rå shell ud til at være en bevidst "escape hatch" for scenarier den typede CLI ikke dækker — men jeg har ikke fundet et skriftligt krav- eller designdokument der siger dette eksplicit. Jeg har ikke fundet en HANDOVER_LOG-entry med begrundelsen for denne specifikke commit.

## 2. Hvilke dokumenter/PR'er/krav gav mandat til det?

- **[Verificeret]** Ingen HANDOVER_LOG-entry, ADR eller krav-/risikodokument nævner denne specifikke commit eller giver et eksplicit mandat til en generel shell. Jeg har søgt bredt (`git show <commit>:Dokumentation/HANDOVER_LOG.md` omkring datoen) uden resultat.
- **[Verificeret]** Hærdningen 10 dage senere (`aaaa5917`, 2026-07-14, "fix(edge): harden local management and release evidence") tilføjede `enable_interactive_shell: False` som standard og fail-closed-gaten i selve WebSocket-handleren — dette ER dokumenteret i selve commit-beskeden som en hærdning, ikke en ny funktion.
- **Konklusion:** endpointet blev ikke introduceret ud fra et separat, sporbart krav — det er en del af en bredere "forbedr teknikerens UI"-commit, efterfølgende hærdet reaktivt.

## 3. Hvem/hvad kan tilgå det?

- **[Verificeret]** Servicen (`totp-service.py`) lytter kun på Bluetooth PAN-bridge-interfacet `br-bt`, IP `192.168.42.1:8443` (se filens egen docstring). `iptables`-kæden `TL_MGMT` blokerer al trafik på dette interface undtagen port 8443, indtil en klient-IP eksplicit whitelistes efter TOTP-succes (`_iptables_add`). Adgang kræver derfor: fysisk/BLE-nærhed → etableret Bluetooth PAN-parring → gyldig TOTP-kode.
- **[Verificeret]** Selve shell-endpointet kræver **derudover** at `management.enable_interactive_shell` er sand — enten sat lokalt i `/etc/timelapse/bt-config.yaml`, eller synkroniseret ned fra Headend's centrale `service_access.interactive_shell_enabled`-politik (`_refresh_service_policy()`). Standard er `False` (fail-closed) for enheder der aldrig har fået en eksplicit Headend-politik.

## 4. Autentifikation og autorisation

- **[Verificeret]** Autentifikation: 6-cifret TOTP mod en per-enhed hemmelighed (ingen delt fabrikskode — fjernet ved en tidligere sikkerhedslukning, `_default_config()`'s kommentar bekræfter dette eksplicit). Brute-force-lås efter 5 fejl / 15 min (`AUTH_FAILURE_LIMIT`/`AUTH_FAILURE_WINDOW_S`).
- **[Verificeret]** Autorisation: **ingen rollemodel.** Der er kun én tilstand — "gyldig TOTP-session" — og den giver adgang til hele management-UI'et inklusive shell (hvis policy-flaget er sat). Der er ikke noget "Observer/Technician/Senior Technician"-hierarki som `agent/core-design-principles`-dokumentet foreslår (se separat analyse). Session-cookien er `httponly, secure, samesite=strict`, bundet til klient-IP (`_valid_token`), med konfigurerbar timeout (default 3600s).
- **[Verificeret]** Selve shell-WebSocket'en har ingen egen, yderligere autorisationskontrol ud over: (a) gyldig session-token+IP, (b) `enable_interactive_shell`-flaget. Enhver med en gyldig teknikersession og det flag sat kan åbne shell'en — der er ikke en separat, strengere rolle for "må bruge rå shell" vs. "må bruge management-UI."

## 5. Hvilke privilegier har processen faktisk?

- **[Verificeret]** `edge/scripts/timelapse-totp.service`: `User=root`, `NoNewPrivileges=no`, kommentar i filen: *"Minimal security hardening (kræver root pga. iptables)"*. Bash-processen der spawnes via `pty.fork()` + `os.execvpe(BASH_PATH, [BASH_PATH, "-l"], env)` arver derfor **fuld root** uden yderligere begrænsning (intet seccomp, ingen namespace-isolation, ingen cgroup-begrænsning, ingen chroot).
- **Konklusion:** dette er ikke en begrænset teknikershell — det er en interaktiv root-shell på edge-enheden.

## 6. Kan vilkårlige kommandoer udføres?

- **[Verificeret] Ja, uden begrænsning.** WebSocket-handleren (`mgmt_cli_bash_ws`) skriver rå brugerinput direkte til PTY master (`os.write(master_fd, msg.encode())`) uden nogen form for allowlisting, escaping eller kommandofiltrering. Dette står i skarp kontrast til `/mgmt/cli/run`, som **er** begrænset: `_parse_cli_args()` kræver at alle flag er i `CLI_ALLOWED_FLAGS` (en fast liste), og kører `bootstrap_cli.py` via `subprocess.run(cmd, ...)` med en argumentliste (ikke `shell=True`) — ingen shell-interpretation, ingen vilkårlig kommandokørsel.

## 7. Audit/logging

- **[Verificeret]** TOTP-login logges (`log.info(f"TOTP verificeret fra {client_ip}...")`), og session-udvidelse til nye IP'er logges i den nyere, **ikke-mergede** variant (se punkt 12). Men: **selve shell-sessionens indhold — hvilke kommandoer der køres, hvad de returnerer — logges eller auditeres slet ikke** på main i dag. Der er ingen transskript, ingen SIEM-forwarding, intet der viser hvad en tekniker faktisk gjorde i shell'en efter login.
- **[Verificeret]** Til sammenligning: main har **allerede** en fuldt auditeret, tilsvarende "vilkårlig adgang"-mekanisme et andet sted i systemet — `edge/scripts/breakglass_shell_wrapper.sh` + `edge/agent.py::_repair_emergency_breakglass_account()`, hvor kommentaren siger *"breakglass_shell_wrapper.sh (full session recording, forwarded to..."* SIEM, med dedikerede tests (`test_break_glass_audit_actor_binding.py`, `test_break_glass_delivery.py` m.fl.). Det er en **anden, separat adgangsvej** (emergency SSH, ikke Bluetooth-TOTP-portalen) — men det viser at projektet allerede har løst præcis dette problem (uafgrænset shell kræver audit) for én adgangsvej, og ikke for denne anden.
- **Dette er det klareste, konkrete sikkerhedsfund i denne assessment: en uaudited root-shell eksisterer parallelt med en fuldt auditeret root-shell-mekanisme til samme grundlæggende formål (nødadgang/debugging), uden at samme kontrol er anvendt konsekvent.**

## 8. Network exposure og binding

- **[Verificeret]** Kun `br-bt` (Bluetooth PAN-bridge), ikke det almindelige LAN/WAN-interface. `iptables`-default-deny undtagen port 8443, indtil TOTP-succes whitelister klient-IP'en specifikt. Ingen ekstern/offentlig eksponering identificeret — dette er en fysisk-nærhed-gated kanal, konsistent med `agent/core-design-principles`' princip 13 ("fysisk nærhed er ikke autentifikation," som her suppleres af TOTP — det er faktisk i tråd med princippet, ikke en overtrædelse af det, isoleret set).

## 9. Failure modes

- **[Verificeret]** Ved WebSocket-disconnect eller exception: `finally`-blokken sender `SIGTERM` til child-processen, venter 0.2s, sender `SIGKILL` hvis den stadig lever, og lukker master-fd. Ved session-udløb (`_valid_token` returnerer falsk pga. timeout) fjernes iptables-whitelisting og Bluetooth-peer — men **kun ved næste HTTP-request**, ikke aktivt ved shell-session-udløb i sig selv; en allerede-åben shell-WebSocket-forbindelse har ingen egen timeout-kontrol ud over den underliggende sessions udløb, og der er ikke set kode der aktivt lukker en åben shell-WebSocket når den overordnede session udløber imens forbindelsen er åben.
- **[Inference]** Dette betyder en teoretisk risiko: en åben, allerede-autentificeret shell-forbindelse overlever muligvis session-udløb, indtil selve WebSocket'en lukkes af andre årsager (netværksafbrydelse, browser lukket). Jeg har ikke testet dette live — det er en læsning af koden, ikke en observeret adfærd.

## 10. Konkrete operationelle use cases shell'en løser

- **[Inference, baseret på UI-tekst og omkringliggende kode]** Ad hoc-debugging der ikke er dækket af de faste `bootstrap_cli.py`-flag: fx inspicere filsystem/logs direkte, teste netværkskommandoer der ikke har et dedikeret flag, manuel proces-inspektion, engangsfejlsøgning under udvikling af nye tekniker-funktioner. Der findes ikke en skriftlig liste over tiltænkte use cases.

## 11. Kan disse use cases løses med begrænsede, typede/capability-baserede operationer i stedet?

- **[Verificeret]** Delvist allerede sådan: `/mgmt/cli/run` + `CLI_ALLOWED_FLAGS` (28 navngivne flag: `--status`, `--doctor-json`, `--network-status`, `--camera-detect`, `--service-operation`, `--commissioning-report` m.fl.) dækker allerede en bred vifte af diagnosticerings- og servicehandlinger uden vilkårlig kommandokørsel. Dette er præcis det mønster `agent/core-design-principles` foreslår som målarkitektur (§43, "deny-by-default"-API).
- **[Inference]** Den rå shell er sandsynligvis bevaret for de tilfælde der IKKE er forudset i `CLI_ALLOWED_FLAGS` — men dette er i sagens natur svært at afgrænse på forhånd. En mere typet tilgang ville kræve enten (a) løbende udvidelse af det allerede eksisterende allowlist-mønster efterhånden som konkrete behov opstår, eller (b) en skarpt afgrænset, selv-auditeret "restricted shell" (fx en begrænset kommandotolk eller en read-only diagnostic-shell) i stedet for fuld bash. Jeg foreslår ikke en løsning her — kun at det eksisterende `/mgmt/cli/run`-mønster allerede er beviset på at det er teknisk muligt for de fleste kendte behov.

## 12. Hvad ændrer `codex/edge-terminal-renderer`, og forbedrer det sikkerheden eller stabiliserer det blot?

- **[Verificeret]** Denne branch (aldrig merget) indeholder en commit-kæde der (a) ændrer transportlaget væk fra WebSocket til et polling-baseret PTY-flow (`c136fecc "make local terminal work without websockets"` m.fl.), (b) forbedrer terminal-rendering (kontrolsekvenser, senere xterm.js i `d67ca26d`), og (c) **i samme commit (`d67ca26d`)** løsner session-IP-pinning ("Deliberately NOT pinned to a single client IP... per-device TOTP secrets and per-device SSH keys already in place... that's the real access-control boundary") og tilføjer break-glass SSH-audit-forwarding til SIEM.
- **Vigtig præcisering:** punkt (c)'s break-glass-audit-tilføjelse gælder den **separate** emergency-SSH-mekanisme, ikke `/mgmt/cli/bash/ws` selv. Jeg har **ikke** verificeret om denne specifikke audit-tilføjelse er den samme som findes på main i dag, eller en anden variant — det kræver en selvstændig sammenligning af `edge/agent.py`s break-glass-kode mellem branch og main, hvilket er uden for denne assessments afgrænsede scope (main's *eksisterende* `/mgmt/cli/bash/*`).
- **Konklusion for selve shell-endpointet (`/mgmt/cli/bash/ws`):** branchens ændringer til **dette specifikke** endpoint er stabilisering/kvalitet (mere pålidelig transport, korrekt terminal-rendering) — **ikke** en sikkerhedsforbedring af selve autorisations- eller audit-modellen for denne portal-shell. Session-IP-pinning-løsningen og break-glass-audit hører til en anden del af samme commit, ikke til `/mgmt/cli/bash/ws`'s egen sikkerhedsmodel.

## 13. Relation til `stash@{3}`

- **[Verificeret, read-only inspektion — ingen pop/drop/ændring]** `stash@{3}` ("pre-main-deploy-safety-backup-20260815T125231Z", taget på `codex/edge-terminal-renderer` 2026-08-15) er en generel pre-deploy-sikkerhedskopi af **ikke-relateret** WP-0/WP-1 release-convergence-arbejde (edge lifecycle records, credential inventory, SFTP RBAC-config). Dens eneste berøring af `totp-service.py` er to linjer kosmetisk UI-hjælpetekst om automatisk kamera-session-fornyelse — **ikke relateret til shell-endpointet eller dets sikkerhedsmodel**. Stashen er ikke yderligere relevant for denne assessment.

---

## Eksplicit sikkerhedsrisiko-markering — stop for Peters beslutning

Jeg vurderer at der er **én reel, konkret sikkerhedsrisiko**, ikke kun en teoretisk observation:

> **Main's `/mgmt/cli/bash/ws` giver en uaudited, fuldt privilegeret (root, `NoNewPrivileges=no`) interaktiv shell, tilgængelig for enhver med en gyldig TOTP-session og `enable_interactive_shell`-flaget sat — uden nogen logning af hvad der faktisk udføres i sessionen. Projektet har allerede løst præcis dette problem (uafgrænset shell kræver session-audit) for en anden, sammenlignelig adgangsvej (break-glass SSH), men den samme kontrol er ikke anvendt her.**

Dette er ikke en påstand om at endpointet skal fjernes eller ændres — det er, som bedt om, en markering til din beslutning. Ingen ændring er foretaget.
