# Remote admin-adgang til Headend: SSH 9122 med adgangskode + TOTP

**Beslutning (Peter, 2026-10-01):** der skal være én sikker vej ind på Headend fra internettet, og den skal være den eneste. Den kræver brugernavn + adgangskode + TOTP, og der skal kunne laves en tunnel til skærmdeling (5900).

## Design
- **Dedikeret sshd** `dk.froekjaer.timelapse-admin-sshd` på **TCP/9122**. Config: `deploy/ssh/timelapse-admin-sshd.conf`. Installer: `deploy/ssh/install_timelapse_admin_sshd.sh`. Bygget efter tunnel-ingress-mønsteret fra #259.
- **Autentificering:** kun `keyboard-interactive` via PAM. `pam_opendirectory` tjekker macOS-adgangskoden, og `pam_google_authenticator` tjekker TOTP. Begge sker **under** login, så hverken shell, kommando eller tunnel kan nås med adgangskoden alene.
  - En tidligere prøvet `ForceCommand`-gate blev droppet, fordi `ssh -N -L` omgår den.
- **PAM-modul:** root-ejet kopi i `/usr/local/lib/pam/pam_google_authenticator.so` (444). Homebrew-stien er skrivbar for `peter` og må aldrig refereres fra root-sshd's PAM.
  - macOS' sshd har `com.apple.private.security.clear-library-validation`, så tredjepartsmoduler må indlæses.
- **`/etc/pam.d/sshd`** har `auth required /usr/local/lib/pam/pam_google_authenticator.so nullok` lige efter `pam_opendirectory`.
  - `nullok` betyder, at brugere uden TOTP-nøgle (`sftp_*`) ikke påvirkes. Edge-tunneller bruger nøgler, ikke PAM-auth.
  - **Konsekvens:** `peter` skal bruge TOTP ved alle sshd-logins, også port 22 på LAN, og kun via keyboard-interactive.
- **TOTP-nøgle:** `~peter/.google_authenticator`, oprettet med `google-authenticator -t -d -f -r 3 -R 30 -w 3`: TOTP, engangskoder, maks 3 forsøg pr. 30 s, ±30 s. 5 nødkoder gemmes af Peter.
- **Tunnel:** kun lokal forwarding til `127.0.0.1:5900`/`localhost:5900`. Alt andet er slået fra: remote/dynamic/stream/agent/X11/tun.
- **Installeren nægter at starte**, hvis modul, PAM-linje eller TOTP-nøgle mangler, så 9122 aldrig bliver password-only.
- **`nullok` bevares med vilje.** Site-SFTP-brugerne (fx `sftp_nvj17c`, Edges' `sftp_password`) logger ind med **adgangskode** gennem samme PAM-auth-stak. Uden `nullok` ville de blive afvist uden TOTP-nøgle.
  - Til gengæld kunne 9122 falde tilbage til password-only, hvis TOTP-nøglen forsvandt. Derfor er der en **fail-closed vagt**: launchd-job `dk.froekjaer.timelapse-admin-sshd-guard`, kører som root.
    - **Hændelsesstyret** via `WatchPaths` på `~peter/.google_authenticator`, `/etc/pam.d/sshd` og PAM-modulet, plus hvert 60. s som backstop.
    - En separat PAM-tjeneste til admin-sshd'en er ikke mulig: OpenSSH bruger fast `SSHD_PAM_SERVICE` = `sshd`.
  - Vagten (og installerens preflight) kræver, at `auth required pam_opendirectory.so` står **før** TOTP-linjen, at begge er `required`, og at ingen `auth`-regel er `sufficient`/`binding`. Modulet skal være root-ejet og ikke skrivbart for gruppe/andre.
  - Mangler `~peter/.google_authenticator`, PAM-modulet (root-ejet) eller PAM-linjen, så logger vagten `auth.crit` og laver `bootout` af admin-sshd'en. 9122 er dermed lukket, indtil installeren køres igen.
- **Kun IPv4** (`ListenAddress 0.0.0.0`). Offentlig eksponering styres alene af routerens IPv4-NAT. Pr. 2026-10-01 har Headend ingen global IPv6 og ingen AAAA-post.

## Brug fra MacBook
```bash
ssh -p 9122 -o ExitOnForwardFailure=yes -L 55900:127.0.0.1:5900 peter@backend.timelapse-pro.dk
```
Åbn derefter `vnc://localhost:55900`. Den lokale port er vilkårlig og ikke offentlig. 5901 var optaget på Peters MacBook.

## Rækkefølge og status (2026-10-01)
| Trin | Status |
|---|---|
| 1. Root-ejet modul + PAM-linje (`nullok`) | ✅ Peter. Backup `/etc/pam.d/sshd.bak-totp-20261001` |
| 2. Password-login uændret | ✅ Peter |
| 3. TOTP-nøgle oprettet | ✅ Peter. Fil verificeret (TOTP_AUTH, DISALLOW_REUSE, RATE_LIMIT 3 30, WINDOW_SIZE 3) |
| 4. Login kræver password + kode | ✅ Peter. DISALLOW_REUSE har registreret brugt kode |
| 5. Installér admin-sshd 9122 | ✅ Peter (host-nøgle `SHA256:rCH8T/ne6m/vv8t0gB/29y1ViMku5d1MEDrFlYdr930`). Geninstalleret med vagt (WatchPaths) + IPv4-only: verificeret `tcp4 *.9122` og vagt loaded |
| 6. Lokal test 9122 | (sprunget over, se 8) |
| 7. Router NAT 9122 | ✅ Peter. Verificeret via NAT: kun `keyboard-interactive`, samme host-nøgle |
| 8. Test fra MacBook udefra + tunnel 5900 | ✅ Peter: adgangskode + TOTP → shell; skærmdeling via `-L 55900:127.0.0.1:5900` + `vnc://localhost:55900` (5901 var optaget lokalt) |
| 9a. Luk password-login på 9022/22222 (Match-blokke i `/etc/ssh/sshd_config`) | ✅ Peter 2026-10-01 (`CONFIG-OK`). Verificeret udefra: `peter`@9022 → ingen metoder; `sftp_nvj17c`@9022 → publickey,password (SFTP uændret); `peter`@9122 → kun keyboard-interactive |
| 9b. Fjern NAT 2222/22022/22222 | ✅ Peter 2026-10-01; verificeret udefra: alle tre `refused` |
| 9c. Port 22 på den offentlige IP | **Ikke Headend og ikke vores**, se fund nedenfor. Afklares med ejeren |

## Fund 2026-10-01
- 🔴 Headends almindelige sshd (port 9022/22222 via NAT) tilbød `password`/`keyboard-interactive` til `peter` fra internettet. Det betyder fuld shell med kun Mac-adgangskode. Lukkes i trin 9.
- 🟠 Offentlig IP (93.165.255.138) port 22 svarer med `OpenSSH_8.4p1 Debian-5+deb11u7`, og det er ikke Headend. Port 80/443 på samme IP er **CrushFTP** (`ftp.hyldager.net`, `Server: CrushFTP HTTP Server`). Headend står altså på et netværk, hvor den offentlige IP deles med Hyldagers produktions-CrushFTP (jf. `PORTS.md`: CrushFTP ejer 21/22/80/443). Port 22 tilhører sandsynligvis en Debian-server i det miljø. **Rør den ikke uden ejerens accept.** Den er ikke en vej ind på Headend.

## Resultat 2026-10-01
Offentligt eksponeret mod Headend: **8443** (API/UI), **9022** (kun SFTP), **9222** (kun Edge-tunneller) og **9122** (admin: adgangskode + TOTP, tunnel kun til 5900). 2222/22022/22222 er lukket. 22/80/443 på den offentlige IP tilhører CrushFTP-miljøet og ikke Headend.
