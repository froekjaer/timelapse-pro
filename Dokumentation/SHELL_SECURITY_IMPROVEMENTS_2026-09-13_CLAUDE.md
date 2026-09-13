# Sikkerhedsforbedringer til det eksisterende shell-endpoint — anbefaling (ingen implementering)

- **Model/session:** Claude (Sonnet 5) · **Dato:** 2026-09-13
- **Baseline:** `origin/main` = `d04798e4ab4716832be576b3134e46b55a994ecf`
- **Mandat:** Peter — undersøg hvordan `/mgmt/cli/bash/*` kan gøres mere sikkert uden at reducere recovery-evnen. **Ingen ændring udført** — dette er en anbefaling til efterfølgende implementering, båret af ADR-004.

Dette dokument besvarer punkt for punkt de forhold Peter bad om at få undersøgt.

## 1. Session-/audit-logging

**Anbefaling:** genbrug break-glass-mønstret direkte, ikke journal-baseret SIEM-forwarding.

- `edge/agent.py::_collect_siem_events_for_sync()` læser `journalctl -u timelapse-edge.service` — men `totp-service.py` kører som sin egen systemd-enhed (`timelapse-totp.service`) med `StandardOutput=append:/var/log.hdd/timelapse/totp-service.log`, **ikke** journald. Dens logs indgår derfor ikke i dag i den generelle SIEM-journal-sti, uanset log-niveau.
- Break-glass-mønstret (`BREAKGLASS_EVENTS_PATH = .../breakglass/pending_events.jsonl`, drænet af `_collect_breakglass_events_for_sync()` ind i samme konsoliderede sync-POST som alt andet SIEM-materiale) er derimod allerede bygget netop til at være **procesuafhængigt**: enhver proces der kan skrive en JSON-linje til en fil kan bruge det, uanset hvilken systemd-enhed den kører som.
- **Konkret forslag:** `totp-service.py` skriver et `shell_session_start`/`shell_session_end`-hændelsespar til en tilsvarende lokal JSONL-fil (enten en ny, parallel fil, eller — hvis semantisk ønsket — samme `pending_events.jsonl`, blot med en anden `event_type`), med felter: tidsstempel, `totp_sid` (hvilket CMDB-lag TOTP-hemmeligheden kom fra — det nærmeste vi har til en bruger-identitet i dag, se §4), klient-IP(er) sessionen er set fra, og (ved slut) varighed. `edge/agent.py` udvides med en lille søster-funktion til `_collect_breakglass_events_for_sync()` der dræner denne fil ind i samme sync-cyklus.
- **Hvorfor dette ikke skaber en ny afhængighed:** skrivningen er en lokal filoperation i `totp-service.py` selv — ingen netværkskald, intet afhængigt af at Headend/agent kører. Forward sker asynkront, næste gang `edge/agent.py` alligevel synkroniserer. Er Headend nede, ophobes hændelserne blot lokalt, præcis som break-glass-hændelser gør i dag. Verificeret ved læsning af `breakglass_shell_wrapper.sh`: hændelsesskrivning (`_emit_event`) er en ren lokal `printf >> $EVENTS_FILE`-operation uden netværksafhængighed.

## 2. Transskript-logging — muligt, men ikke garanteret, og skal verificeres separat

- Break-glass' fulde transskript-forsøg (`script -f -q -c "$REAL_SHELL -l" "$SESSION_LOG"`) blev **forladt i praksis** (dokumenteret i `breakglass_shell_wrapper.sh`s egen kommentar, 2026-08-25): en dobbelt-PTY-relæ (sshd's pty + `script`s egen indre pty) fik terminal-vindue/echo-tilstand galt for visse klienter, og blev droppet til fordel for en shell der rent faktisk virkede.
- `/mgmt/cli/bash/ws` har **ikke** dette problem strukturelt: Python-koden ejer selv PTY'en direkte (`master_fd, slave_fd = pty.openpty()` / `pty.fork()`) og pumper allerede al I/O gennem sig selv (`os.read(master_fd, ...)` → WebSocket, og omvendt). At logge denne allerede-passerende datastrøm til en lokal fil kræver ikke et ekstra PTY-relæ — kun at tilføje en fil-skrivning i den eksisterende læse-løkke.
- **Anbefaling:** forsøg fuld transskript-logging her (den arkitektoniske hindring for break-glass gælder ikke på samme måde), men **behandl det som noget der skal verificeres empirisk før det loves** — ikke antag det virker uden test, givet at projektet allerede én gang blev overrasket af PTY-relæ-kompatibilitetsproblemer i en beslægtet sag.

## 3. Tydelig registrering af hvem/hvornår shell blev aktiveret

- Dækket af §1's `shell_session_start`-hændelse. Begrænsning der skal være eksplicit: der er **ingen** individuel teknikeridentitet i dag — kun en delt, per-enhed (eller per-kunde/site/kamera-lag) TOTP-hemmelighed. "Hvem" kan derfor kun angives som "nogen med adgang til den TOTP-kode der var gyldig for `sid=X`," ikke et navngivet menneske. Dette er en eksisterende begrænsning i hele TOTP-portalens autorisationsmodel, ikke noget denne forbedring kan løse alene uden en separat, større ændring (individuelle teknikerkonti) — som eksplicit **ikke** er en del af dette mandat.

## 4. Genbrug af eksisterende TOTP/session/policy-kontroller

- **[Verificeret uændret, skal forblive uændret]:** TOTP-verifikation (`pyotp`, per-enhed hemmelighed, ingen delt fabriksfallback), session-cookie (`httponly, secure, samesite=strict`), brute-force-lås (5 fejl/15 min), og `enable_interactive_shell`-policyflaget (default `False`, synkroniseret fra Headend, fail-closed ved manglende central politik) er allerede solide og kræver ingen ændring. De skal genbruges som de er — audit-forbedringen lægges **oven på** dem, ikke i stedet for.

## 5. Fail-closed-status

- **[Verificeret]** Allerede korrekt: `_default_config()["management"]["enable_interactive_shell"] = False`; WebSocket-handleren tjekker flaget først og lukker (kode 1008) hvis det ikke er sat — før session-tjek overhovedet udføres. Ingen ændring nødvendig eller anbefalet her.

## 6. `codex/edge-terminal-renderer` — indeholder den stabilitetsforbedringer der gør debug-adgang mere robust?

**Ja, konkret og verificerbart — se separat anbefalingsdokument** (`R04_EDGE_TERMINAL_RENDERER_ANBEFALING_2026-09-13_CLAUDE.md`) for den fulde vurdering under det korrigerede krav.

## Opsummeret anbefaling

Implementér (som en separat, afgrænset opgave — ikke udført her):
1. Lokal JSONL-hændelseslog for shell-session-start/slut i `totp-service.py`, drænet af en ny lille funktion i `edge/agent.py` efter break-glass-mønstret.
2. Forsøg (og verificér empirisk) fuld transskript-logging, da arkitekturen her er gunstigere end break-glass'.
3. Ingen ændring af TOTP/session/policy/fail-closed-lagene — de er allerede korrekte.
4. Ingen individuel teknikeridentitet indføres som del af dette — eksplicit uden for scope.
