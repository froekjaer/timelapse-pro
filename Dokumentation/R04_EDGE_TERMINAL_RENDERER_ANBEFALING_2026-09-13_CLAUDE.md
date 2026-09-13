# `codex/edge-terminal-renderer` — korrigeret anbefaling (ingen implementering)

- **Model/session:** Claude (Sonnet 5) · **Dato:** 2026-09-13
- **Baseline:** `origin/main` = `d04798e4ab4716832be576b3134e46b55a994ecf`
- **Mandat:** Peter korrigerede det tidligere R04-stop-gate-fund: branchen skal **ikke** automatisk klassificeres som uønsket fordi den forbedrer shell-funktionalitet. Spørgsmålet er: **gør den Peters adgang til diagnosticering/recovery mere robust, uden en uacceptabel sikkerhedsmæssig regression?** Ren anbefaling — ingen kode ændret.

## Svar: Ja, med afgrænsning — men branchen bør ikke merges i sin helhed

Branchen som helhed er ekstremt gammel (merge-base ved PR #7) og 101 filer/10.480 linjer i sit fulde omfang — langt hovedparten er ikke-relateret drift/struktur fra tidlig projektfase. Den relevante undermængde er en klar, sporbar commit-kæde (2026-08-03 til 2026-08-06) i `edge/scripts/totp-service.py` + tilhørende statiske xterm.js-filer. Anbefalingen gælder **kun denne undermængde**, ikke branchen i sin helhed.

## Konkrete robusthedsforbedringer fundet (verificeret ved læsning af faktiske commits)

### A) Multi-IP session-tracking løser et reelt, dokumenteret recovery-problem

**[Verificeret]** Commit `d67ca26d` (2026-08-06) ændrer `_valid_token()` fra streng IP-pinning til at spore alle IP'er en session er set fra. Begrundelsen er skrevet direkte i koden af Peter selv (docstring, 2026-08-05): *"the Edge must stay reachable across Bluetooth PAN, WiFi, Ethernet and routed networks, and a technician's apparent source IP can legitimately change mid-session... BT-PAN reconnect on screen-lock hands out a new DHCP address..."*.

**Hvorfor dette er en reel recovery-forbedring, ikke kun bekvemmelighed:** main's nuværende kode (uændret siden før denne branch) afbryder en sessions gyldighed hvis klient-IP'en ændrer sig (`if sess["ip"] != ip: return False`, ingen genoprettelse). I en recovery-situation — netop når Peter har mest brug for stabil adgang — er en Bluetooth PAN-reconnect eller netværksskift midt i en debugging-session sandsynlig, ikke usandsynlig. Streng IP-pinning kan derfor aktivt **modarbejde** den recoverability ADR-004 nu prioriterer.

**Sikkerhedsafvejning, eksplicit:** løsningen svækker ikke den reelle autentifikationsgrænse — sessionstokenet (256-bit HMAC, kun udstedt efter korrekt TOTP) forbliver uændret det der faktisk autentificerer, ikke kildeIP'en. Ændringen **tilføjer** oven i købet logning af hver ny IP en session ses fra (`log.info(f"Session {token[:8]}… set fra ny IP {ip}...")`) — main har i dag **ingen** logning af IP-skift overhovedet. Nettoeffekten er derfor mere robusthed **og** mere synlighed, ikke mindre sikkerhed.

### B) Aktiv shell-oprydning ved session-udløb lukker en reel failure-mode

**[Verificeret]** Samme commit tilføjer `_close_shell_session()`, kaldt fra `_valid_token()` når en session udløber — den terminerer en evt. åben shell-proces og lukker dens PTY. Min tidligere assessment af main identificerede præcis dette som en gap: en åben shell-WebSocket-forbindelse har i dag ingen aktiv oprydning ved session-udløb ud over hvad selve WebSocket-forbindelsens naturlige livscyklus giver. Denne rettelse lukker det gab.

### C) Transport- og rendering-forbedringer — reel brugbarhed, ikke kun kosmetik

**[Verificeret]** Commit-kæden `afdc3e01`→`c136fecc`→`b5d3ab7e`→`918282a2`→`b25703ed` (alle 2026-08-03) erstatter WebSocket-transporten med en polling-baseret (`/mgmt/cli/bash/start`/`output`/`close`), tilføjer en rigtig "controlling terminal" (`pty.fork()` i stedet for et separat `pty.openpty()`+`Popen`, som giver bash job control den ikke havde før), og retter terminal-kontrolsekvens-rendering. `d67ca26d` (2026-08-06) erstatter en hånd-skrevet ANSI-parser med vendoret xterm.js (ingen CDN — fungerer offline, relevant for en edge uden internetadgang), begrundet med to på hinanden følgende escaping-bugs i den håndrullede parser.
**Hvorfor relevant for recovery:** en shell hvor tab-completion, `vim`, control-tegn (Ctrl-C osv.) og korrekt terminalstørrelse ikke virker pålideligt er reelt mindre brugbar til akut fejlsøgning. Dette er direkte "diagnosability"-forbedringer, ikke overfladisk polering.

## Ikke en del af denne anbefaling — kræver separat vurdering

- **Break-glass SSH-audit-tilføjelsen i samme commit (`d67ca26d`):** Verificeret (via `edge/agent.py::_repair_emergency_breakglass_account()`s egen kommentar) at `breakglass_shell_wrapper.sh` fra netop denne branch **allerede er genbrugt uændret på main** (2026-08-25, Peters beslutning om password- i stedet for pubkey-baseret levering). Denne del af branchen er altså allerede absorberet — intet nyt at gøre her.
- Branchens øvrige ~95 filer (urelateret til shell/terminal) — ikke vurderet, ikke en del af dette mandat.

## Anbefaling

**Reimplementér, som en ny, afgrænset, scoped ændring** (ikke en direkte merge af den 3+ uger gamle branch) mod aktuel main:
1. Multi-IP session-tracking med logging af IP-skift (punkt A).
2. Aktiv shell-session-oprydning ved session-udløb (punkt B).
3. Polling-transport + `pty.fork()` controlling-terminal + xterm.js-rendering (punkt C).

Kombinér dette naturligt med sikkerhedsforbedringerne fra `SHELL_SECURITY_IMPROVEMENTS_2026-09-13_CLAUDE.md` (samme filer røres alligevel) — men det er to uafhængige beslutninger; punkt A-C her handler om robusthed, ikke audit.

**Ingen uacceptabel sikkerhedsmæssig regression fundet.** Multi-IP-sporingen er den eneste ændring med sikkerhedsrelevans, og den er nettopositiv (mere robusthed + ny logning, samme reelle autentifikationsgrænse).

**Ikke udført her:** selve reimplementeringen. Dette er en anbefaling til Peters godkendelse før implementering, som mandatet krævede.
