# ADR-004 scoped implementation — shell robustness + local-first audit

- **Model/session:** Claude (Sonnet 5) · **Dato:** 2026-09-13
- **Baseline:** `origin/main` = `d04798e4ab4716832be576b3134e46b55a994ecf`
- **Mandat:** Peter godkendte retningen i ADR-004 (Development and Recovery Shell Access, Proposed) og gav mandat til en scoped implementering af de forbedringer der blev identificeret i shell-assessmenten og den korrigerede analyse af `codex/edge-terminal-renderer`. ADR-004 forbliver Proposed indtil implementeringen er afprøvet på en rigtig edge.

## Hvad er implementeret

### 1. Multi-IP session-tracking (`edge/scripts/totp-service.py`)

`_sessions[token]` gemmer nu `"ips": set[str]` i stedet for `"ip": str`. `_valid_token()` afviser ikke længere en session fordi klient-IP'en ændrer sig — den tilføjer den nye IP til sættet, logger skiftet, og whitelister den via iptables. Ved session-udløb fjernes **alle** IP'er sessionen nogensinde er set fra (ikke kun den aktuelle), både i `_valid_token()`s udløbssti og i `/logout`.

**Provenance:** reimplementerer (ikke cherry-picker) reasoningen fra `codex/edge-terminal-renderer` commit `d67ca26d` (2026-08-06, aldrig merget) — samme begrundelse er gengivet ordret i kildekodekommentaren, med reference til at det er en reimplementering, ikke en direkte merge.

### 2. Korrekt cleanup af shell-sessioner ved expiry og logout

Ny registry `SHELL_SESSIONS` (token → {pid, master_fd}) + idempotent `_close_shell_session(token, reason)`, kaldt fra tre steder:
- `_valid_token()`s udløbssti (session timeout mens en shell stadig er "åben")
- `/logout` (eksplicit session-afslutning — **fundet og rettet som en ny bug under implementeringen**: `/logout` fjernede tidligere kun iptables/bluetooth for den aktuelle IP og lukkede slet ikke en åben shell)
- Websocket-handlerens egen `finally`-blok (normal frakobling), som nu selv "claimer" registry-posten før den udfører sin oprindelige, mere grundige SIGTERM→200ms-vent→SIGKILL→blocking-waitpid-eskalering — bevaret uændret for at undgå at svække en eksisterende, testdækket kontrakt (`tests/test_edge_technician_terminal_runtime.py::test_shell_cleanup_terminates_and_reaps_child`, som fejlede i første iteration af denne ændring og blev rettet, se §Tests).

Idempotens er garanteret ved at begge stier `pop()`'er fra samme lock-beskyttede dict — uanset hvilken sti der når det først, sker selve drab+audit kun én gang.

### 3. Local-first audit af shell-session start/stop

`_emit_shell_audit_event()` i `totp-service.py` skriver `shell_session_start`/`shell_session_end`-hændelser (med kort tokenprefix, TOTP-`sid`, klient-IP, tidsstempel, reason) til en lokal JSONL-fil (`/var/log.hdd/timelapse/totp-shell/pending_events.jsonl`) — **ren lokal filoperation, ingen netværkskald**. `edge/agent.py` får to nye søsterfunktioner til det eksisterende break-glass-mønster (`_collect_totp_shell_events_for_sync()`, `_persist_totp_shell_cursor_after_sync()`), som drænes ind i den allerede eksisterende, periodiske sync-cyklus. Hvis Headend er utilgængeligt, ophobes hændelserne blot lokalt.

**Provenance:** genbruger mønstret fra `edge/agent.py::_collect_breakglass_events_for_sync()` (allerede accepteret, allerede i produktion) — ikke fra den aldrig-merged branch.

### 4. Terminal-kontroltaster (lav risiko, høj værdi)

Udvidede `keydown`-handleren i den indlejrede JS med piletaster, Home/End, Delete, Escape — tidligere kun Enter/Backspace/Tab/Ctrl+bogstav. Verificeret ved at ekstrahere og syntakstjekke den faktisk **renderede** JS (efter Python-strengfortolkning) med `node --check`.

**Provenance:** reimplementerer `codex/edge-terminal-renderer` commit `b5d3ab7e` (2026-08-03, aldrig merget).

## Hvad er bevidst IKKE implementeret

- **Transport-skift til polling** (item 5's tunge del): main bruger fortsat WebSocket. Vurderet, men ikke skiftet — items 2-4 krævede det ikke (shell-registreringen virker uafhængigt af transport), og den specifikke ekstra robusthedsgevinst (shell-*processen* overlever et fuldt reconnect, ikke kun sessionen) kræver verifikation på en fysisk edge for at kunne påstås "demonstrably more robust", som Peter's betingelse for item 5 krævede. **Kræver fysisk-edge-test før evt. senere beslutning.**
- **xterm.js-vendoring:** ikke gjort i denne omgang — kræver den samme slags manuelle/live jsdom+canvas-verifikation som blev brugt til at bekræfte `d67ca26d` oprindeligt, hvilket ikke kan gøres pålideligt som en automatisk Python-test. **Kræver fysisk-edge/browser-test.**
- **Fuld transskript-logging:** eksplicit ikke et krav (Peters punkt 6). Ikke implementeret.
- **Individuel tekniker-identitet:** uden for scope — `totp_sid` er det nærmeste vi har til "hvem", uændret fra før.

## Tests

Ny/ændret testdækning, alle grønne:

- `tests/test_totp_service_shell_session_robustness.py` (ny, 13 tests): multi-IP-adfærd, expiry-oprydning af alle IP'er, shell-session-cleanup + idempotens, dødt-barn-tolerance, lokal audit-logning (inkl. eksplicit test for at ingen netværkskald sker), `/logout`-adfærd.
- `tests/test_totp_shell_events_for_sync.py` (ny, 6 tests): drain/rename/persist-mønstret for den nye sync-kilde, inkl. "unsent .sending file merges, doesn't lose events" og malformed-linje-tolerance.
- **Regression fundet og rettet:** `tests/test_edge_technician_terminal_runtime.py::test_shell_cleanup_terminates_and_reaps_child` (eksisterende, source-text-kontrakt) fejlede efter min første version af websocket-finally-refaktoreringen — rettet ved at bevare den fulde SIGTERM/SIGKILL/blocking-waitpid-sekvens i selve websocket-handleren, med registry-pop kun som idempotens-guard, ikke som erstatning for logikken.
- Fuld relevant sweep kørt (`tests/test_totp_service_*`, `tests/test_edge_release_contract.py`, `tests/test_break_glass_edge.py`, `tests/test_self_heal_retries_every_sync.py`, `tests/test_architecture_ratchet.py` m.fl.): alle grønne.
- Bred `tests/`-sweep (937 passed) — resterende fejl/errors er alle urelaterede, pre-eksisterende miljøbegrænsninger i denne sandkasse (kræver rigtig Postgres, GPG-nøgler, eller mTLS-CA-opsætning: `test_auth_integration`, `test_device_management`, `test_mfa_ui_workflow`, `test_artifact_openpgp_verification`, `test_mtls_security`, `test_webauthn_origin_rp_contract` m.fl.) — ingen af dem rører `edge/scripts/totp-service.py` eller `edge/agent.py`s sync-mekanisme.
- `python3 -m py_compile` på begge ændrede filer + hele det trackede Python-træ: grønt. `node --check` på den faktisk renderede (ikke rå kildetekst-) JS: grønt.

## Kendte rests/risici

- **Ikke afprøvet på en rigtig edge.** Al verifikation her er statisk (syntaks, unit-tests med mockede subprocess/iptables/PTY-kald). `pty.fork()`, faktisk iptables-adfærd, faktisk Bluetooth PAN-reconnect og faktisk lokal-fil-permission (`/var/log.hdd/timelapse/totp-shell` skal kunne oprettes af root ved `timelapse-totp.service`s første kørsel) er **ikke** verificeret i praksis.
- Skal desuden verificeres på en rigtig edge: at `edge/agent.py`s nye sync-forwarding rent faktisk finder og sender `totp-shell`-hændelser sammen med break-glass-hændelser i et ægte sync-poll, og at Headend-siden håndterer `event_type: shell_session_start/end` fornuftigt (ingen Headend-side-ændring er lavet eller undersøgt her — kun edge-siden).
- Transport (WebSocket vs. polling) og xterm.js er bevidst udskudt, som beskrevet ovenfor.

## Filer rørt

`edge/scripts/totp-service.py`, `edge/agent.py`, `tests/test_totp_service_shell_session_robustness.py` (ny), `tests/test_totp_shell_events_for_sync.py` (ny).
