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

## Brug fra MacBook
```bash
ssh -p 9122 -L 5901:127.0.0.1:5900 peter@backend.timelapse-pro.dk
```
Åbn derefter `vnc://localhost:5901`. Lokal port 5901 undgår konflikt med MacBook'ens egen skærmdeling.

## Rækkefølge og status (2026-10-01)
| Trin | Status |
|---|---|
| 1. Root-ejet modul + PAM-linje (`nullok`) | ✅ Peter. Backup `/etc/pam.d/sshd.bak-totp-20261001` |
| 2. Password-login uændret | ✅ Peter |
| 3. TOTP-nøgle oprettet | ✅ Peter. Fil verificeret (TOTP_AUTH, DISALLOW_REUSE, RATE_LIMIT 3 30, WINDOW_SIZE 3) |
| 4. Login kræver password + kode | ✅ Peter. DISALLOW_REUSE har registreret brugt kode |
| 5. Installér admin-sshd 9122 | afventer |
| 6. Lokal test 9122 | afventer |
| 7. Router NAT 9122 | afventer |
| 8. Test fra MacBook udefra + tunnel 5900 | afventer |
| 9. Luk password-adgang på 9022/22222 (Match-blokke) + fjern NAT 2222/22022/22222 + slå routerens WAN-SSH (port 22) fra | afventer, **først efter 8** |

## Fund 2026-10-01
- 🔴 Headends almindelige sshd (port 9022/22222 via NAT) tilbød `password`/`keyboard-interactive` til `peter` fra internettet. Det betyder fuld shell med kun Mac-adgangskode. Lukkes i trin 9.
- 🟠 Offentlig IP port 22 svarer med `OpenSSH_8.4p1 Debian-5+deb11u7` (ikke Headend). Sandsynligvis routerens egen SSH-administration på WAN.
