# Direct-Edge terminalemulator: capability-regression, root cause og genbrugsarkitektur

**Forfatter:** Claude Sonnet 5, 2026-09-13
**Baseline:** `origin/main` `8452c5ef` (efter #238)
**Status:** Implementeret på branch `claude/edge-terminal-emulator-2026-09-13` (PR afventer)

## Resumé

Peter har fysisk verificeret at direct-Edge/TOTP recovery-terminalen
(`https://192.168.86.144:8443` → CLI → "Åbn terminal") virker, men med en
dårlig terminalemulator: Ctrl-C, Tab, pil-op/ned og Home/End fungerer ikke
korrekt. Headend's "Åbn terminal" (SSH-tunnel) giver derimod en god oplevelse.

**Root cause (verificeret via git-historik, ikke antaget):** Der har
eksisteret to parallelle udviklingsspor for samme capability:

1. **Mainline-sporet** (nu på `main`): en håndrullet, dependency-fri
   textarea-renderer, der stripper ANSI-sekvenser i stedet for at fortolke
   dem. Fladet ud via `56f8c6f7` (PR #198, "restore usable technician
   terminal pty", 2026-09-08) og videreført uændret af #238 (2026-09-13).
   PR #198's kildekodekommentar *"intentionally dependency-free"* er skrevet
   af #198 selv — det er ikke en henvisning til en tidligere beslutning.

2. **Et separat, aldrig merged spor**: commits `afdc3e01→c136fecc→b5d3ab7e→
   918282a2→b25703ed→a5dc02fc→d67ca26d→6c5e3cac`. Commit `d67ca26d`
   ("fix(edge): replace hand-rolled terminal parser with xterm.js", forfattet
   af **Peter selv**, 2026-08-06) erstattede netop den håndrullede renderer
   med et rigtigt terminalemulator-bibliotek (xterm.js, vendoret lokalt, ikke
   CDN) — og commit-beskeden bekræfter en **reel live-test**: *"Verified with
   jsdom+canvas end-to-end simulation and a live deploy to TL-C87FF9587CA0."*
   Dette er højst sandsynligt den gode oplevelse Peter husker at have testet
   — dog for over en måned siden (2026-08-06), ikke "for få dage siden" som
   antaget. Sporet blev aldrig merged til main; branchen `codex/edge-terminal-
   renderer` er en senere afstikker af samme, stadig aldrig-merged linje.

Samme commit (`d67ca26d`) implementerede desuden **uafhængigt allerede**
multi-IP session-tracking (`sess["ips"]` som set, whitelisting af nye IP'er,
oprydning af alle spores IP'er ved expiry) — nøjagtig samme kapabilitet som
#238 (2026-09-13) genopfandt fra bunden, fordi det oprindelige spor var tabt
af syne. Dette er et selvstændigt eksempel på samme underliggende
governance-problem: patch-/implementation-equivalence blev antaget uden at
tjekke capability-historikken. Se `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_
CLAUDE.md` for den foreslåede procesrettelse.

## Genbrugsarkitektur — identificeret før implementation

**Headend's "Åbn terminal":**
- Bibliotek: `@xterm/xterm@^6.0.0` + `@xterm/addon-fit@^0.11.0` (npm,
  `timelapse-ui/package.json`), bundlet via Vite — ikke CDN.
- Frontend: `timelapse-ui/src/components/SshTerminalModal.tsx`.
- Backend: `headend/api/ssh_tunnel_terminal_api.py` — Headend er selv
  SSH-klienten (paramiko) gennem den etablerede reverse-tunnel;
  transport er en websocket med rå PTY-bytes plus én kontrolramme
  (`\x01RESIZE:cols,rows`) til resize.

**Direct-Edge (`edge/scripts/totp-service.py`), før denne rettelse:**
Textarea + regex-baseret ANSI-strip, ingen ægte terminalemulering.

**Det tabte, allerede-gode spor (`d67ca26d`/`codex/edge-terminal-renderer`):**
Vendoret `@xterm/xterm@5.5.0` under `edge/scripts/static/xterm/`, men på
**polling-transport** (`/mgmt/cli/bash/{start,output,input,close}`, ikke
websocket) og **uden** dynamisk resize (fast 80×24, sat én gang ved åbning).

**Valgt genbrugsarkitektur (mindst mulige korrekte løsning):**
Behold #238's websocket-transport, multi-IP session-robusthed, shell-lifecycle-
cleanup, logout-oprydning og local-first audit **uændret** — de er allerede
implementeret og testet. Erstat **kun** frontend-rendereren med xterm.js,
vendoret i samme version som Headend bruger (`@xterm/xterm@6.0.0` +
`@xterm/addon-fit@0.11.0`, hentet fra npm registry, MIT-licens, samme
LICENSE-fil som originalt vendoret i `d67ca26d` verificeret at være samme
projekt/licens). Dette giver: samme bibliotek/komponent som Headend (som
Peter bad om), ingen CDN-afhængighed (assets ligger under
`edge/scripts/static/xterm/`, serveret via en ny `StaticFiles`-mount på
`/mgmt/static`), og ingen regression af #238's allerede fysisk-relevante
robusthedsarbejde.

## Implementerede ændringer

`edge/scripts/totp-service.py`:
- Nye imports: `struct`, `termios`, `fcntl`, `fastapi.staticfiles.StaticFiles`.
- `app.mount("/mgmt/static", StaticFiles(...))` — server vendoret xterm.js/css.
- `_cli_page()`: shell-panel bruger nu `<div id="term">` + `<link>`/`<script>`
  til xterm.js/addon-fit i stedet for `<textarea>`.
- `shell_script`: opretter en rigtig `Terminal`, indlæser `FitAddon`, sender
  tastetryk direkte via `term.onData()` (ingen manuel keycode-liste længere —
  xterm.js håndterer Ctrl-C, Tab, pil-taster, Home/End, Escape osv. korrekt af
  sig selv), skriver rå websocket-data direkte via `term.write()` (ingen
  ANSI-strip).
- **Resize (ny funktionalitet, fandtes ikke i det gamle spor heller):**
  frontend sender `\x01RESIZE:<cols>:<rows>` over den eksisterende websocket
  ved åbning og ved `window.resize`; backend genkender præfikset og kalder
  `fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ...)`, hvilket får kernen til at
  sende `SIGWINCH` til bash's forgrunds-procesgruppe automatisk.
- Initial pty-vindue sat til 80×24 (matcher xterm.js' standard) umiddelbart
  efter `pty.fork()`, som en fornuftig startværdi før første RESIZE-besked.

`edge/scripts/static/xterm/{xterm.js,addon-fit.js,xterm.css,LICENSE}` — nye,
vendorede filer (samme MIT-licens, samme xterm.js-projekt som Headend bruger).

`tests/test_edge_technician_terminal_runtime.py` — den forældede
`test_fallback_renderer_does_not_expose_ansi_control_sequences` er erstattet
af fire nye tests der låser den nye arkitektur fast (xterm.js bruges, ingen
`<textarea>`, assets er lokale/ikke-CDN, resize går via `TIOCSWINSZ`). De to
oprindelige tests (forked controlling tty, SIGTERM→SIGKILL-eskalering) er
bevaret uændret.

## Verifikation udført i denne session

- `python3 -m py_compile` PASS.
- Fuld relevant test-suite (86 tests: terminal-runtime, shell-session-
  robusthed, break-glass, self-heal, architecture-ratchet, bluetooth-peer,
  policy-watch, sync-unification, release-contract) — **86/86 PASS**.
- Bred sweep af hele `tests/` (892 tests, eksklusive kendte miljøbegrænsede
  filer) — **892/892 PASS**, ingen nye fejl introduceret.
- Den faktiske genererede JS (efter Python-streng-interpolation, ikke en
  hånd-transskriberet kopi) blev udtrukket og kørt gennem `node --check`
  samt en jsdom-baseret smoke-test: `Terminal`-konstruktion, `FitAddon.fit()`,
  `term.open()`, `term.write()`, korrekt opbygget `wss://`-URL i `openShell()`,
  og `sendResize()` — alt eksekverede uden fejl mod de faktiske vendorede
  bibliotek-filer (samme metode som `d67ca26d`s "jsdom+canvas end-to-end
  simulation", uden canvas-rendering som kun påvirker pixel-output).

## Ikke verificeret endnu — kræver fysisk Edge-accepttest

Ctrl-C/job control, Tab-completion, history (pil op/ned), Home/End, resize
(faktisk vinduesstørrelse-ændring i en levende session), samt at det hele
fungerer uden Headend/internet. Se den opdaterede fysiske testplan i
handover-svaret til Peter.

## Kendte forskelle vs. det oprindelige tabte spor (bevidste valg)

- **Transport forbliver websocket** (#238), ikke polling som i `d67ca26d`.
  Websocket er allerede implementeret, testet og har lavere latenstid;
  intet i Peters mandat bad om at rulle tilbage til polling.
- **xterm.js-version er 6.0.0** (matcher Headend), ikke den oprindeligt
  vendorede 5.5.0. Samme bibliotek, nyere version, fuld API-kompatibilitet
  for de anvendte metoder (`Terminal`, `.open()`, `.write()`, `.onData()`,
  `FitAddon`).
- **Dynamisk resize er ny funktionalitet** — hverken mainline eller det tabte
  spor understøttede det tidligere (begge brugte fast 80×24).
