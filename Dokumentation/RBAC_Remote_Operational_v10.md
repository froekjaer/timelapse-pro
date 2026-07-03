# TimeLapse Pro — RBAC · Remote Access · Operational (v10, konsolideret)

**Version:** 10 (konsolideret; oprindeligt TLP-OPS-2026-001 v1.0, Sprint C-design)
**Dato:** 2026-07-02
**Klassifikation:** FORTROLIGT — kun autoriserede modtagere
**Konverteret fra:** `TimeLapse_RBAC_Remote_Operational_v1.docx` (arkiveret i `Gamle versioner/`).
**Dækker:** RBAC-design, auth-arkitektur, reverse SSH, customer approval, kommando-whitelist, DB-schema, API-endpoints, driftsguide.

> Note: Beskriver Sprint C-designet (JWT RS256, MFA, multi-tenant, reverse SSH). Anden aktuel implementeringsstatus (fx HS256 vs. RS256) føres i `RISK_ASSESSMENT_v10.md` og `KRAVREGISTER_og_STATUS_v10.md`.

> **Opdatering 2026-07-02 — MFA er nu policy-drevet og enforced (Codex).** MFA-kravet afgøres af en session-policy: global `mfa_required` (default off) + `mfa_required_by_role` med **default `super_admin: True`, `admin: True`** (operator/viewer: False) + `mfa_exempt_usernames` (fritagelsesliste). Ved requests kastes `403 "MFA kræves for denne rolle"` hvis rollen kræver MFA og sessionen ikke er MFA-verificeret (`_mfa_required_for_user` / `_session_is_mfa_verified` i `main.py`). WebAuthn er et separat flag (`webauthn_required`, default off). Claude/Codex-testkonti er pt. på fritagelseslisten, så de kan arbejde i testsystemet. Roller-tabellens "MFA"-kolonne (§2.1) skal derfor læses som: **KRÆVET = enforced for super_admin/admin**; "Anbefalet/Valgfrit" for øvrige styres via policy.

## 1. Formål

Sprint C transformerer TimeLapse Pro fra internt staging-system til production-klar multi-tenant platform med fuld bruger-autentificering, auditeret adgangskontrol og kundekontrolleret remote-adgang.

## 2. RBAC-design

### 2.1 Roller (5)

| Rolle | Scope | Typisk bruger | Tilladte handlinger | MFA | Oprettelse |
|---|---|---|---|---|---|
| super_admin | Alle kunder | Systemadministrator | Alt — brugere, kunder, enheder, config, audit-log, SSH niveau 1-3 | KRÆVET | Manuel |
| admin | Én kunde | Teknisk ansvarlig | Kundens config, tekniker-tildeling, rapporter | KRÆVET | Af super_admin |
| technician | Tildelte kunder | Felttekniker | Tildelte kunders enheder, config, SSH niveau 1+2 | Anbefalet | Af admin |
| viewer | Én kunde | Kundens medarbejder | Se egne billeder/timelapse, godkende SSH-anmodninger | Valgfrit | Af admin |
| device | Ét device | Edge-node (M2M) | Heartbeat, capture-upload, config-hentning, tunnel-åbning | N/A | Automatisk |

### 2.2 Permission-matrix (uddrag)

| Handling | super_admin | admin | technician | viewer | device |
|---|---|---|---|---|---|
| Opret/slet brugere | ✓ | Egne | — | — | — |
| Opret/slet kunder | ✓ | — | — | — | — |
| Se/konfigurer enheder | ✓ | Egne | Tildelte | — | — |
| Se/download billeder, opret timelapse | ✓ | Egne | Tildelte | Egne | — |
| Anmod SSH-adgang | ✓ | Egne | Tildelte | — | — |
| Godkend SSH-anmodning | ✓ | Egne | — | ✓ (egne) | — |
| SSH kommando niveau 1/2 | ✓ | ✓ | ✓ | — | — |
| SSH kommando niveau 3 | ✓ | — | — | — | — |
| Se audit-log | ✓ | Egne | — | — | — |
| Heartbeat/capture upload | — | — | — | — | ✓ (eget) |

### 2.3 Multi-tenancy (customer_id isolation)

Row-level security: alle queries filtreres automatisk på `customer_id` hentet fra JWT-payload — **aldrig** fra request body. super_admin: NULL (ingen filter). admin/viewer: `WHERE customer_id = jwt.customer_id`. technician: `WHERE customer_id IN (jwt.assigned_customers)`. device: kun eget `device_id`.

## 3. Autentificeringsarkitektur

### 3.1 Auth-metoder

| Metode | Flow | TTL | Sikkerhedskrav |
|---|---|---|---|
| Password + JWT | POST /api/auth/login → bcrypt verify → JWT + refresh | JWT 30 min | bcrypt cost≥12, timing-safe |
| Magic link | POST /api/auth/magic → token_urlsafe(32) → e-mail → GET /api/auth/magic/{token} | 15 min | SHA-256 i DB, single-use, HTTPS |
| OAuth2/SSO | Redirect Google/Microsoft → callback → JWT | JWT 30 min | PKCE, state, validér iss+aud |
| TOTP/MFA | Efter password: POST /api/auth/mfa/verify (6-cifret) | 30s window | hmac.compare_digest, valid_window=1 |

### 3.2 JWT-specifikation

RS256 (privat nøgle kun på headend). Header `{alg:RS256, typ:JWT, kid:...}`. Payload: `sub` (user_id UUID4), `role`, `customer_id` (NULL for super_admin, liste for technician), `jti` (revocation), `iat`/`exp` (exp=iat+1800s). **Browser-lagring: memory (React state) — ALDRIG localStorage/sessionStorage (XSS).** Refresh token: SHA-256 i sessions-tabel, HttpOnly Secure SameSite=Strict cookie, 7 dages TTL, roteres ved brug, revokes alle ved password-skift.

### 3.3 MFA (TOTP)

Setup → `pyotp.random_base32()` → QR (otpauth://) + Fernet-krypteret secret i `mfa_secrets` → bekræft med `pyotp.verify()` → 8 backup-koder. Login herefter: password → TOTP → JWT (eller backup-kode engangs).

### 3.4 Rate limiting / lockout

Login/IP: 5/min (429). Login/konto: 10/time (lockout 1t + e-mail). TOTP: 5/15 min. Magic link: 3/time/e-mail. API/device: 100/min.

## 4. Database-schema (Sprint C-udvidelse)

Nye tabeller (eksisterende Device/Capture/Diagnostic/Event/Customer/Site bevares):

- **users**: id, email(unik), password_hash(bcrypt, nullable for OAuth/magic), role, customer_id(NULL for super_admin), auth_methods(CSV), mfa_required, is_active, last_login, failed_attempts, locked_until, created_at, created_by.
- **mfa_secrets**: id, user_id, totp_secret_enc(Fernet), backup_codes_enc(Fernet JSON), is_active(false til bekræftet), created_at.
- **sessions**: id, user_id, refresh_hash(SHA-256), ip_address, user_agent, mfa_verified, expires_at, created_at, last_used.
- **audit_log**: id, user_id(NULL for uautoriseret), action, resource_type, resource_id, ip_address, user_agent, success, detail(JSON), timestamp(index).
- **user_customers**: id, user_id, customer_id (composite unique — technician multi-tenant).
- **ssh_approvals**: id, device_id, requested_by, purpose, tunnel_port(22200-22299), token_hash(SHA-256), status(pending|approved|rejected|expired|closed), approved_by, approved_at, expires_at(24t TTL), tunnel_opened, tunnel_closed, created_at.

## 5. API-endpoints

**Auth:** `/api/auth/login|magic|magic/{token}|refresh|logout|mfa/setup|mfa/confirm|mfa/verify|mfa/backup|oauth/{provider}|oauth/{provider}/callback`.
**Brugere:** `GET/POST /api/users`, `GET/PUT/DELETE /api/users/{id}`, `POST /api/users/{id}/assign-customer`, `GET /api/users/me`.
**SSH-tunnel:** `POST /api/provision/{device_id}`, `POST /api/tunnel/request`, `GET /api/tunnel/approve/{token}|reject/{token}|status/{device_id}|history`, `POST /api/tunnel/close/{device_id}`.
**Audit:** `GET /api/audit`, `GET /api/audit/export` (CSV, super_admin).

## 6. Reverse SSH — design

### 6.1 Nøglehåndtering

Hvert edge-device får eget ED25519 keypair genereret af headend (`Ed25519PrivateKey.generate()`). Privat nøgle Fernet-krypteres med `TIMELAPSE_MASTER_KEY` og gemmes i DB. Public key installeres på edge ved bootstrap (`authorized_keys` med `restrict,command=...`).

### 6.2 Customer approval-flow

Tekniker `POST /api/tunnel/request` → headend genererer approval-token (token_urlsafe(32), SHA-256 i DB, 24t TTL) → e-mail (DKIM/SPF/DMARC, TLS) med approve/reject-link → kunde klikker approve → status `approved` + config-flag til device → edge opdager `open_tunnel=true` ved config-pull (≤2 min) → `autossh -M 0 -R {port}:localhost:22 -i /etc/timelapse/id_ed25519 vps` (StrictHostKeyChecking=yes) → tekniker `ssh -p {port} localhost` → `restricted_shell` → tunnel lukkes ved 4t timeout eller `POST /api/tunnel/close`.

### 6.3 restricted_shell.py (ForceCommand, kommando-whitelist)

Alle kommandoer valideres mod whitelist FØR eksekution; intet gennem shell (subprocess-liste altid).

| Niveau | Tilladte kommandoer | Kræver |
|---|---|---|
| 1 | journalctl, systemctl status, df -h, free -h, top -bn1, cat /var/log/syslog | Aktiv godkendt tunnel |
| 2 | systemctl restart/stop/start timelapse-edge, gphoto2 --summary, udevadm trigger/reload-rules | Aktiv godkendt tunnel |
| 3 | scp (kun upload til /tmp/timelapse-upload/), nano /etc/timelapse/*.conf, python3 /opt/timelapse/edge/tools/*.py | Separat admin-approval |
| ALDRIG | rm, rmdir, dd, mkfs, fdisk, passwd, useradd, su, sudo, nc, nmap, curl/wget (ekstern), python3 -c, bash/sh -c | Blokeret permanent |

sshd_config: `Match User tunnel-user` → `ForceCommand /opt/timelapse/edge/restricted_shell.py`, `AllowTcpForwarding no`, `X11Forwarding no`, `PermitTTY yes`, `MaxSessions 1`.

## 7. Miljøvariabler (Sprint C)

`TIMELAPSE_MASTER_KEY` (Fernet master, 32-byte base64url), `JWT_PRIVATE_KEY_PATH`/`JWT_PUBLIC_KEY_PATH` (RS256 PEM), `SMTP_HOST/PORT/USER/PASS`, `VPS_HOST`, `TUNNEL_PORT_RANGE` (22200-22299).

## 8. Driftsguide

**Daglige/ugentlige tjek:** fejlede login (`GET /api/audit?action=login_failed`), aktive tunneler (`GET /api/tunnel/status`), session-cleanup (`DELETE FROM sessions WHERE expires_at < NOW()`), heartbeat (timeout 15 min), shutter-tæller (alarm >80%).

**Nøglerotation:** SSH ED25519/device 90 dage (`/api/provision/{id}/rotate`), JWT RS256 365 dage (zero-downtime via ny kid, begge accepteres 24t), Fernet master 365 dage (re-kryptér alle secrets, planlagt vindue), device API-tokens 90 dage (auto ved CI/CD).

**Incident response (kompromitteret konto):** deaktiver konto (`is_active=false`) → revoke sessioner (`DELETE /api/sessions?user_id=`) → luk tunneler → gennemgå audit 24t → roter SSH-nøgler hvis tekniker havde adgang → notificér berørte kunder → dokumentér + GDPR Art. 33/34 inden 72t ved brud.
