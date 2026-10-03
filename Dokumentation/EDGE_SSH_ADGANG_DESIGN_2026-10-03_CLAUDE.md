# Én tydelig SSH-vej til Edge — designforslag (2026-10-03, Claude)

**Status:** FORSLAG — afventer Peters godkendelse. Intet er implementeret.
**Anledning (Peter, 2026-10-03):** "Der burde være en helt tydelig måde at logge ind på edgen med SSH."
**Branch:** `claude/edge-ssh-access-design-20261003` (fra `origin/main` `06efb3c8`).

## 1. Hvad findes i dag (verificeret 2026-10-03)

| Del | Hvor | Fund |
|---|---|---|
| Teknikernøgler | `headend/technician_keys.py`, tabel `user_ssh_keys` | Kun public key, label, created_at/by og revoked_at. **Intet fingeraftryk.** Kun brugere med `field_role` installer/technician og adgang til kunden kommer med i sync. |
| Nøglegenerering i browser | `timelapse-ui/src/pages/UsersPage.tsx` `generateEd25519KeyPair` (#100, 2026-08-23) | Den private nøgle downloades én gang som `<label>.key`. Labelen saneres med `[^a-zA-Z0-9._-]` → `-`, så "Nøgle oprettet 3.10.2026" bliver `N-gle-oprettet-3.10.2026.key`. **Kommentaren er tom** i både public og private key. Det forklarer, hvorfor nøglen er svær at finde igen. |
| Live DB | `user_ssh_keys` | Én nøgle: `peter`, "Peters MacBook Pro", 2026-08-23 17:06, `SHA256:Ntih4R/XGHN/QZ4h1yWGuyWDrA+ObERv9B/5Quh3SSc`, ingen kommentar. Den forventede fil er `Peters-MacBook-Pro.key` på den maskine, der kørte browseren. Den findes ikke i `~/Downloads` på Headend. |
| Levering til Edge | `headend/edge_sync.py` → `edge/agent.py::_apply_technician_keys` → `/etc/timelapse/authorized_technicians.json` → `edge/scripts/technician_authorized_keys.py` (sshd `AuthorizedKeysCommand`, `Match User servicetekniker`) | Envejs. **Edgen rapporterer ikke, hvilke nøgler den har.** Uden fungerende sync kan en ny nøgle ikke nå frem. |
| Bevis for teknikerlogin | `devices.servicetekniker_verified_at` (sat ud fra Edgens journal) | **NULL for både Edge1 og Edge2.** Teknikernøgle-vejen er aldrig bevist på nogen Edge. |
| Reverse tunnel | Tunnel-sshd 9222 (`deploy/ssh/timelapse-tunnel-sshd.conf` — **kun på #259-branchen**, ikke main), `-R 127.0.0.1:<port>:localhost:22` | Edge1 2201: `failed` siden lab.56 (PR #273). Edge2 2204: `connected` 13:09:58. Porte bindes kun på Headends loopback. |
| Web-terminal | `headend/api/ssh_tunnel_terminal_api.py` | Logger ind som `ssh_login_user()` med Headends delte commissioning-nøgle, ikke med brugerens egen nøgle. `terminal_trust_status()` kender årsagen ("No active reverse SSH tunnel" / host key ikke trusted), men UI'en viser den ikke tydeligt. |
| Edge-lokal shell | `edge/scripts/totp-service.py` `/mgmt/cli/bash/ws` | Viser kun "[closed]". Dækkes af det åbne spor #239. **Ikke en del af dette forslag.** |
| Admin-SSH Headend | 9122 (#270, `deploy/ssh/timelapse-admin-sshd.conf`) | `AllowUsers peter`, adgangskode + TOTP via PAM, `PermitOpen 127.0.0.1:5900` alene. Ingen ProxyJump-historik i `git log --all`. |
| Edge sshd | `headend/tools/inject_edge_image.py` | `Match User emergency` → `PasswordAuthentication yes`. Edge1 har globalt `PasswordAuthentication yes` + `PermitRootLogin yes` (GRC `FIND-EDGE1-INSECURE-SSH-AND-PACKAGE-DRIFT-20260924`, åben). |
| UI | `DevicePage.tsx` | Ingen SSH-, tunnel- eller nøgleinformation. Terminal og tunnel-log ligger kun på den separate `SshTunnelPage.tsx`. |

**Relevante åbne spor:** #273 (tunnel loopback-bind, Edge1), #259 (tunnel-sshd + mTLS, ikke afstemt med main), #253 (sandfærdig tunnel-health: "verificeret Headend-side kl."), #239 (Edge-lokal terminal), GRC `ACT-BREAKGLASS-EMERGENCY-ACCESS-DECISION` (in_progress), `FIND-BREAKGLASS-EMERGENCY-ACCESS-NEVER-TRACKED` (open), R10 "SSH tunnel misbrug".

## 2. Om 9122 egner sig som ProxyJump

**Nej, ikke som den fælles vej.** Begrundelse:

1. 9122 er `AllowUsers peter` og bruger macOS-konto + PAM-TOTP. Teknikere er web-brugere, ikke macOS-konti, og `pam_google_authenticator` er pr. Unix-bruger. Dermed bliver der aldrig én vej for alle.
2. ProxyJump kræver, at `PermitOpen` udvides med hver Edges tunnelport. sshd-config understøtter ikke intervaller, så listen skulle genrenderes og sshd genindlæses ved hver ny Edge. Desuden er der ingen begrænsning pr. bruger/kunde.
3. 9122's invariant er "eneste admin-shell, 2FA, kun 5900". Den beskyttes af en fail-closed vagt. Den invariant bør ikke blandes med Edge-adgang.

**Peters admin-vej forbliver uændret** (adgangskode + TOTP, 5900). Kan Peter allerede i dag nå en Edge via 9122? Kun hvis `PermitOpen` udvides. Det anbefales ikke. Peter bruger den nye vej (§3) med sin nøgle og sit web-MFA-grant.

## 3. Anbefalet design: dedikeret jump-sshd med centralt styrede nøgler

```
MacBook ──ssh -J──▶ backend.timelapse-pro.dk:9322 (timelapse_jump, kun nøgle, ingen shell)
                         │  direct-tcpip kun til 127.0.0.1:<Edge-port> fra aktivt grant
                         ▼
                    127.0.0.1:2201 ──reverse tunnel──▶ Edge sshd :22 (servicetekniker, kun nøgle)
```

### 3.1 Jump-sshd (Headend)
- Ny instans `dk.froekjaer.timelapse-jump-sshd` på **TCP/9322** (<10000, ved siden af 9122/9222). Samme mønster som tunnel-sshd og admin-sshd: egen config i `/etc/ssh/timelapse-jump/`, egen host-nøgle, egen launchd-tjeneste og installer med `--verify-only`/`--self-test`.
- Én servicekonto `timelapse_jump` (shell `/usr/bin/false`). `AuthenticationMethods publickey`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitTTY no`, `ForceCommand /usr/bin/false`, `AllowTcpForwarding local`, `PermitListen none`, `X11/Agent/StreamLocal/Tunnel no` og `PerSourcePenalties` som 9122.
- `AuthorizedKeysCommand /usr/local/libexec/timelapse/jump_authorized_keys %u %f` (fingeraftrykket som argument). Det kører som en dedikeret ikke-login-bruger og spørger Headend lokalt: `GET http://127.0.0.1:8000/api/internal/ssh-jump/authorized-keys?fingerprint=…`, med et token fra en root-ejet fil (0400). Svaret er højst én linje:
  ```
  restrict,port-forwarding,permitopen="127.0.0.1:2201",expiry-time="20261003T1405Z" ssh-ed25519 AAAA… peter:Peters-MacBook-Pro
  ```
  - `restrict` slår alt fra, `port-forwarding` åbner kun for forwarding, og `permitopen` begrænser `-W` til netop de Edge-porte, brugeren har et aktivt grant til.
  - **Fail-closed:** fejl, timeout eller ukendt fingeraftryk giver tomt output.
  - **Central revokering virker øjeblikkeligt** på internetvejen, fordi opslaget sker live ved hvert login.
  - `/api/internal/` blokeres i nginx. Tokenet er den egentlige gate, da nginx også forbinder fra 127.0.0.1. Routeren ligger i `headend/api/`, ikke i `main.py` (ratchet).
- **2FA-ækvivalent uden PAM:** knappen "Åbn SSH-adgang i 60 min" på enhedssiden udsteder et `EdgeServiceGrant` (eksisterende `issue_edge_service_grant`, `mfa_required=True`, purpose `ssh_jump`). Det kræver MFA-verificeret web-session ligesom browserterminalen. Uden aktivt grant får nøglen ingen `permitopen` og kan intet. Altså nøgle **og** MFA-session.
  - **Restrisiko:** `expiry-time` stopper kun nye logins. En åben session lever videre efter grantets udløb. Mulig opfølgning: Headend lukker jump-sessioner, når grantet udløber.

### 3.2 Edge (forudsætning, før 9322 åbnes)
- Ny `Match Address 127.0.0.1,::1`-blok med `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitRootLogin no`.
  - Den skal stå **før** `Match User emergency`. I sshd vinder første værdi, så ellers ville `emergency`'s `PasswordAuthentication yes` vinde.
  - Alt, der kommer gennem tunnelen, er dermed kun-nøgle, også `emergency` og `orangepi`. Password-login (break-glass) virker fortsat kun lokalt på LAN/konsol.
  - Det er nødvendigt, fordi jump-vejen ellers ville give internetbrugere adgang til at prøve adgangskoder mod Edge1 (global `PasswordAuthentication yes`).
  - Leveres som agent-selvheling efter mønsteret i `_repair_sshd_authorized_keys_command_missing_u_token()` plus i `inject_edge_image.py`, med `sshd -t` før reload.
  - Browserterminalen (commissioning-nøgle, loopback) påvirkes ikke.
- **Rapport om nøglestatus i sync-payloaden:** `technician_keys_report` = `{fingerprints: [SHA256:…], count, cache_sha256, applied_at, sshd_wired: bool, last_servicetekniker_login_at}`.
  - `sshd_wired` = `Match User servicetekniker` + `AuthorizedKeysCommand … %u` er til stede.
  - Kun public-fingeraftryk. Intet hemmeligt.

### 3.3 Headend-data
- `user_ssh_keys.fingerprint_sha256` (ny kolonne, backfill beregnet fra `public_key`) og `user_ssh_keys.filename_hint`.
- Ny tabel `edge_technician_key_reports` (device_id, reported_at, fingerprints jsonb, cache_sha256, sshd_wired, applied_at). Sammenligningen sker på **fingeraftryk-mængder**, ikke rå hash, så JSON-serialisering ikke giver falsk "ude af sync". Den historik bruges til audit: "hvilke nøgler var gyldige på Edgen kl. X".
- **Indstillinger i DB (`settings`) og redigerbare i Global Config → ny sektion "Fjernadgang (SSH)"** (Peters regel):

| Nøgle | Default | Betydning |
|---|---|---|
| `ssh_jump_enabled` | `false` | Viser kommando/knap. Uden den er jump-opslaget altid tomt. |
| `ssh_jump_public_host` | `backend.timelapse-pro.dk` | Navn i kommando og config-snippet |
| `ssh_jump_public_port` | `9322` | Installeren læser værdien fra DB. UI'en advarer, hvis listeneren afviger. |
| `ssh_jump_user` | `timelapse_jump` | |
| `ssh_edge_login_user` | `servicetekniker` | |
| `ssh_jump_grant_minutes` | `60` (maks. 480) | Varighed for "Åbn SSH-adgang" |
| `ssh_jump_require_grant` | `true` | `false` = permanent permitopen for alle Edges, brugeren har adgang til (anbefales ikke) |
| `ssh_key_report_stale_minutes` | `15` | Hvornår en nøglerapport regnes som forældet |

## 4. UI

### 4.1 Enhedssiden — ny boks "SSH-adgang"
Statusrækker, hver med tidsstempel og kilde:
1. **Tunnel:** oppe/nede, port, "verificeret fra Headend kl. …" (genbruger #253's verifikationstid og `_active_reverse_tunnel`) og seneste `connected`/`failed`-hændelse.
2. **Edgens teknikernøgler:** "Synkroniseret kl. … (N nøgler, sshd korrekt sat op)" / "Afventer sync — Headend har ændringer siden …" / "Ukendt — Edgens version rapporterer ikke nøglestatus".
3. **Dine nøgler på denne Edge:** pr. nøgle label + fingeraftryk + ✓ på Edgen / ⏳ ikke endnu / ✗ revokeret.
4. **Teknikerlogin bevist:** `servicetekniker_verified_at` eller "aldrig".

**Grøn tilstand:** knappen "Åbn SSH-adgang i 60 min" og derefter en kopierbar kommando:
```bash
ssh -J timelapse_jump@backend.timelapse-pro.dk:9322 -o HostKeyAlias=tl-c87ff9587ca0 -p 2201 servicetekniker@127.0.0.1
```
Desuden "Kopiér ~/.ssh/config-blok" (§4.2) og "Hent known_hosts-linjer". Linjerne indeholder jump-host-nøglen og Edgens host-nøgle fra `ssh_host_key_trust` (trusted), så første forbindelse ikke kræver blind TOFU.

**Rød tilstand (tunnel nede)** — forklaring ud fra fakta i DB i stedet for en tavs fejl. Eksempel for Edge1 i dag:
> Tunnelen er nede siden 13:13 (seneste forsøg 21:33: *failed*, port 2201). Edgen er online — den har hentet opdateringspolitik for 3 min siden — men har ikke synkroniseret siden 13:13. Headend kan derfor ikke nå Edgen, og nye eller revokerede nøgler når ikke frem.
> **Muligheder:** (1) På samme LAN: `ssh servicetekniker@<LAN-IP fra inventar>` — virker kun med nøgler, Edgen allerede har (✓ ovenfor). (2) Lokal teknikerside `https://<LAN-IP>:8443` (TOTP). (3) Bluetooth-tekniker. (4) Fysisk konsol / break-glass (se `ACT-BREAKGLASS-EMERGENCY-ACCESS-DECISION`).

Browserterminalens knap viser `terminal_trust_status().reason`, før den prøver at forbinde, i stedet for en tom fejl.

### 4.2 Brugersiden — "Mine SSH-nøgler"
- Tabel: label, fingeraftryk (`SHA256:…`), oprettet (dato + af hvem), filnavn ved download, status (aktiv/revokeret) og "findes på N af M Edges".
- **Rettelser i nøglegenerering:**
  - Kommentar `peter@timelapse-pro 2026-10-03 <label>` i både public og private key.
  - Filnavn `timelapse_<brugernavn>_<yyyymmdd>_ed25519` med translitteration (ø→oe, æ→ae, å→aa) i stedet for `-`.
  - Fingeraftrykket vises på skærmen ved download med instruktionen `mv ~/Downloads/<fil> ~/.ssh/ && chmod 600 ~/.ssh/<fil>`.
  - Anbefalet primærvej: `ssh-keygen -t ed25519 -C "peter@timelapse-pro"` lokalt + indsæt public key (findes allerede).
- **"Kopiér ~/.ssh/config"** genereret fra DB-indstillingerne og de Edges, brugeren har adgang til:
  ```
  # TimeLapse Pro — genereret 2026-10-03 for peter
  Host timelapse-jump
    HostName backend.timelapse-pro.dk
    Port 9322
    User timelapse_jump
    IdentityFile ~/.ssh/timelapse_peter_20261003_ed25519
    IdentitiesOnly yes
    RequestTTY no

  Host tl-c87ff9587ca0
    HostName 127.0.0.1
    Port 2201
    User servicetekniker
    ProxyJump timelapse-jump
    HostKeyAlias tl-c87ff9587ca0
    IdentityFile ~/.ssh/timelapse_peter_20261003_ed25519
    IdentitiesOnly yes
  ```
  Derefter `ssh tl-c87ff9587ca0`. Grantet skal stadig åbnes på enhedssiden.

## 5. Sikkerhed

| Krav | Opfyldt sådan |
|---|---|
| Ingen password-SSH til Edges fra internettet | Jump er kun-nøgle. Edge-loopback (= alt via tunnelen) er kun-nøgle for alle konti (§3.2), og det gøres til forudsætning før NAT 9322. |
| Kun nøgle + central revokering | Jump-opslaget er live mod `user_ssh_keys` og stopper øjeblikkeligt. Edge-cachen fjernes ved næste sync (≤ `sync_poll_interval`). **Restrisiko:** LAN-vejen virker med en revokeret nøgle, indtil Edgen synker. Den er synlig i UI'en ("⏳ revokering ikke leveret"). |
| Admin-vejen beholder 2FA | 9122 er uændret. |
| Mindste privilegium | `permitopen` pr. bruger pr. Edge, kun med aktivt MFA-grant og tidsbegrænset. Ingen shell, PTY eller forwarding ud over det. |
| Audit | Jump-sshd `LogLevel VERBOSE` (fingeraftryk), Headend-opslagslog (bruger/fingeraftryk/porte/grant), Edge-journal `Accepted publickey for servicetekniker … SHA256:…` (findes) og `edge_technician_key_reports`. Fingeraftrykket binder dem sammen. |
| Ny eksponeret port | 9322 ved NAT. Det er Peters beslutning. `PerSourcePenalties`, kun nøgle, og intet kan nås uden grant. |

## 6. Faser (hver fase: tests, HANDOVER_LOG, verificering på kørende system)

- **F0 (ingen kode — Peter):**
  - Find nøglen på MacBook: `find ~ -name "*.key" -newermt 2026-08-23 ! -newermt 2026-08-24 2>/dev/null`, og sammenlign derefter med `ssh-keygen -lf <fil>` mod `SHA256:Ntih4R/XGHN/QZ4h1yWGuyWDrA+ObERv9B/5Quh3SSc`.
  - Bevis servicetekniker-login på Edge2 over LAN (sætter `servicetekniker_verified_at`).
  - Edge1: tunnel via #273 / lab.57.
- **F1 (ingen ny angrebsflade):**
  - Fingeraftryk + filnavn/kommentar-rettelse + config-snippet på brugersiden.
  - Edge-nøglerapport + Headend-lagring + statusboksen på enhedssiden (kun visning).
  - Forklaring ved tunnel nede og årsag i browserterminalen.
- **F2:** Edge-loopback kun-nøgle (selvheling + generator). Verificeret på begge Edges før F3.
- **F3:** Jump-sshd 9322 + `AuthorizedKeysCommand` + grant-knap + indstillinger. NAT af Peter. Test udefra:
  - Uden grant → afvist.
  - Med grant → shell.
  - Revokér → afvist straks.
  - Forkert Edge-port → `administratively prohibited`.

## 7. Beslutninger til Peter
1. Ny jump-sshd på **9322** (anbefalet) eller udvide 9122 (kun Peter, ingen kunde-/teknikerafgrænsning)?
2. Kræv **web-MFA-grant pr. Edge** for at åbne jump (anbefalet, 60 min) eller permanent adgang til alle tilladte Edges?
3. OK til at gøre **alt via tunnelen kun-nøgle på Edgen** (også `emergency`/`orangepi`)? Password-break-glass kan så kun bruges lokalt.
4. Behold browser-genereret nøgle (med rettelserne) som standard, eller vis `ssh-keygen` + indsæt som primær vej?
5. Rækkefølge: F1 med det samme, F2/F3 efter Edge1 er oppe igen?

## 8. OP-001 Step 7
Ingen ny Framework Finding. Mønstret "levering uden leveringskvittering" (Headend sender nøgler, Edgen bekræfter aldrig) er et konkret tilfælde af det eksisterende kandidat-Finding i PR #245 ("control-plane state vs runtime outcome"). Når F1 bygges, tilføjes det som evidens dér.
