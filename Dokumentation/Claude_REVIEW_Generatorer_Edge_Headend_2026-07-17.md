# Claude — Review af Edge- og Headend-generatorerne (med CrushFTP-sameksistens)

**Dato:** 2026-07-17 · **Forfatter:** Claude (Cowork) · **Status:** Til fælles gennemgang (Peter + Claude + Codex)
**Omfang:** (a) Edge-generatoren: `headend/tools/build_edge_disk_image.py`, `inject_edge_image`, `prepare_edge_provisioning`/`enroll_device` i main.py, `edge/tools/bootstrap_cli.py`, jetson-installeren. (b) Headend-generatoren: `deploy/install/bootstrap_headend_macos.sh`, `install_headend.sh`, `enroll_headend_cmdb.sh`, example-confs, node-agent-installer. (c) Sameksistens med CrushFTP (21/22/80/443) på staging/prod.
**Metode:** Fuld kodelæsning af alle nævnte scripts/flows + krydstjek mod `PORTS.md`, `HEADEND_GENERATOR_v1.md`, `INSTALLATION_GUIDE_HEADEND_v1.md`, `Installationsguide_v10.md`, `deploy/ssh/timelapse-sshd-sftp.conf`.

---

## 1. Samlet vurdering

Begge generatorer er arkitektonisk rigtige og langt: headend-generatorens 4-fase-model (preflight → signeret stage → apply → enroll) er eksemplarisk secure provisioning (IEC 62443-holdbar), og edge-generatoren har multi-hardware-targets, signerede manifests+SBOM, one-time bootstrap-tokens og zero-touch enrollment med credential-rotation. **Men sameksistens-kæden er kun halvt lukket:** nginx/API-laget respekterer CrushFTP konsekvent (8443, DNS-01, hårde port-afvisninger), mens **SFTP-upload-vejen og reverse-tunnel-vejen gør ikke** — de peger i praksis stadig på port 22, som CrushFTP ejer på staging/prod. En headend genereret i dag ville stå pænt på 8443 uden at kunne modtage billeder.

---

## 2. Headend-generatoren — hvad virker

| Element | Verificeret |
|---|---|
| Preflight (Fase 0) | Read-only evidens-JSON (`headend-preflight.v1`), bind-test på 8443, hård afvisning af `TL_BACKEND_PORT` ∈ {21,22,80,443}, listener-/LaunchDaemon-/brew-inventar. Fanger også hvis CrushFTP selv skulle bruge 8443 (bind-testen fejler → exit 3). |
| Stage (Fase 1) | `git verify-tag` (GPG) + fuld 40-tegns commit-SHA-pinning + clean-tree-check + `protocol.file.allow=never`. Immutabel, verificeret release. |
| Apply (Fase 2) | Idempotent; genererer frisk `JWT_SECRET` (64 tegn — opfylder prod-kravet i main.py), rører aldrig eksisterende `headend.env`, nginx KUN på `TL_BACKEND_PORT`, DNS-01-cert (rører ingen port — CrushFTP-sikkert), plain-HTTP-bootstrap-block indtil cert findes, `nginx -t` før reload med backup. |
| Enroll (Fase 3) | Fail-closed: bootstrap-token fra fil (aldrig som argument), `node_type=headend` → `KeyCredential(entity_type="headend")` (verificeret i `enroll_device`), venter på autentificeret inventory-kvittering, ellers non-zero exit. Node-agent-installeren kræver eksplicitte `--device-id/--headend-url/--api-token-file` — ingen R&D-defaults tilbage. ✅ HEADEND_GENERATOR §8 punkt 1-3 bekræftet implementeret. |

---

## 3. Fund — sameksistens-huller (vigtigst først)

### 3.1 🔴 GEN-01: SFTP-ingress (22222) er slet ikke en del af headend-generatoren

Edge-upload-kæden er API-først med `customer_sftp` som sekundær/fallback — men på en ny staging/prod-headend:

- `install_headend.sh` opretter **ingen** SFTP-ingress: ingen dedikeret sshd-socket på 22222, ingen `sftp_*`-brugere, ingen hardening-blok, ingen RBAC-config (`render_sftp_rbac_config.py`).
- `INSTALLATION_GUIDE_HEADEND_v1.md` indeholder **ikke ét** "22222". `HEADEND_GENERATOR_v1.md` nævner 22222 i portmodellen, men intet installations-trin dækker den.
- Mekanikken FINDES (`deploy/ssh/timelapse-sshd-sftp.conf` + `apply_timelapse_sftp_hardening.sh` + launchd-socket `ssh-2222.plist` med `SockServiceName=22222`) — den er bare aldrig blevet et trin i generatoren.

**Konsekvens:** ny headend kan ikke modtage SFTP-uploads; fallback-upload-vejen er død ved fødslen. **Anbefaling:** gør SFTP-ingress til et eksplicit "Fase 2b"-trin (script + manual — se INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md §7, skrevet i dag).

### 3.2 🔴 GEN-02: `sftp_port`-default er **22** — kollisionskurs med CrushFTP

`headend/main.py:4006`: `"port": int(_get_setting(db, "sftp_port", os.getenv("SFTP_PORT", "22")))`. Hvis `sftp_port`-settingen ikke sættes eksplicit på den nye headend, fortæller config-hierarkiet **alle edges** at uploade SFTP på **port 22** — dvs. direkte ind i CrushFTP på staging/prod. Resultat: fejlede uploads, støj/lockout-risiko i CrushFTP, og et brud på PORTS.md-reglen "`sftp_*` users are only valid on TCP/22222".

**Anbefaling:** (1) skift kode-defaulten til `22222` (PORTS.md er policy — koden bør følge den), (2) lad install_headend.sh seede `sftp_host`/`sftp_port`/`sftp_remote_base`-settings i DB, (3) tilføj kontrakttest: config-hierarkiets sftp.port må aldrig være 21/22/80/443. Bemærk også at `backup_sftp`-blokken har samme hardcodede `"port": 22`-default.

### 3.3 🟠 GEN-03: Reverse-tunnel-indgangen er udefineret på staging/prod

`edge/tunnel/ssh_manager.py:300`: SSH-endpoint-fallback er port **22**. På R&D virker det (macOS Remote Login på 22), men på staging/prod ejer CrushFTP/system-SSH port 22, og generatoren opsætter hverken tunnel-bruger, authorized_keys eller port. Hardening-profilen siger selv "Human/admin SSH and reverse-debug tunnels must be configured separately" — men ingen definerer *hvor*.

**Anbefaling (beslutning, Peter):** fastlæg tunnel-ingress-port for staging/prod (fx genbrug 22222-socketen med en dedikeret `tltunnel`-bruger, der IKKE matcher `sftp_*`-blokkene, eller en ny dedikeret port + PORTS.md-opdatering). Derefter: gør det til et generator-trin + sæt tunnel-endpointet eksplicit i edge-config (aldrig fallback til 22).

### 3.4 🟠 GEN-04: Tunnel-port-allokatoren kan tildele 2222 (reserveret)

`prepare_edge_provisioning` tildeler `reverse_tunnel_port = max(eksisterende, 2200) + 1` — enhed nr. 22 får port **2222**, som PORTS.md eksplicit reserverer til anden produktionsapplikation. Allokatoren har hverken reserved-port-exclusion, øvre grænse eller bind-/kollisionscheck. **Anbefaling:** ekskludér {2222} + alle PORTS.md-reserverede porte, definér range (fx 23000-23999) for fremtidige headends, og logga tildelingen til CMDB.

### 3.5 🟠 GEN-05: Dokument-modstrid om SFTP-opsætning (v10 vs hardening-profil)

`Installationsguide_v10.md` Del A §12 instruerer den GAMLE model: én `sftpuser` med `ChrootDirectory` + bred `Match User`-blok på port 22 — præcis det mønster `timelapse-sshd-sftp.conf` beder om at FJERNE ("Remove the old broad Match User sftp_* block"; macOS-chroot-problemet er også derfor løst med ForceCommand). En ny person der følger v10-guiden genindfører den udfasede model. **Anbefaling:** ret Del A §12 til at henvise til `deploy/ssh/`-profilen + 22222 (lille, additiv docs-rettelse).

### 3.6 🟡 GEN-06: Release-disciplin-hul i Fase 2

`example-{staging,prod}.conf` sætter `TL_REPO_DIR=/Users/peter/projects/timelapse-pro`, men Fase 1 staged den verificerede release i `--destination` (fx `~/tl-staging-release`). Hvis Peter følger example-conf'en ordret, installeres der fra en almindelig arbejdskopi — udenom GPG-verifikationen. **Anbefaling:** example-confs skal pege `TL_REPO_DIR` på staged-release-mappen, og install_headend.sh bør advare hvis `TL_REPO_DIR` er et git-checkout med dirty tree/uden verificeret tag.

### 3.7 🟡 GEN-07: `admin/changeme`-vinduet på offentlig 8443

Efter Fase 2 står headenden offentligt på 8443 med default-login `admin/changeme` indtil første MFA-enrollment (guide §7). Samme fejlklasse som SEC-016 (default credentials). **Anbefaling:** kør første login FØR DNS-record oprettes/firewall åbnes (manualen skriver det nu eksplicit), og på sigt: installer genererer et engangs-admin-password i `headend.env`-stil i stedet for `changeme`.

### 3.8 🟡 GEN-08: Enroll mod `https://127.0.0.1:8443` fejler på certifikat

`enroll_headend_cmdb.sh` kræver `https://` (godt), men HEADEND_GENERATOR §4 foreslår `HEADEND_URL=https://127.0.0.1:8443` — LE-certifikatet dækker kun domænet, så urllib fejler TLS-verifikation mod 127.0.0.1. **Anbefaling:** brug altid det rigtige backend-domæne i enroll/agent-URL (manualen gør det), eller tilføj eksplicit CA-/hostname-håndtering.

---

## 4. Fund — edge-generatoren

### 4.1 🟠 GEN-09: Device-SSH-privatnøgler genereres centralt, ligger i klartekst i DB og bages ind i image

`prepare_edge_provisioning` genererer Ed25519-nøglepar på headenden og gemmer **privatnøglen i `Camera.ssh_private_key`** (klartekst); flashable-flowet bager den + WiFi-password + bootstrap-token ind i `.img.gz`, som registreres som artifact. Konsekvens: (a) DB-kompromittering giver tunnel-nøgler til hele flåden, (b) et image-artifact er en fuld credential-pakke. Zero-touch-enrollment understøtter allerede det rigtige mønster (`ssh_pubkey` i EnrollRequest — enheden genererer selv nøglen). **Anbefaling:** (1) dokumentér nu: flashable images behandles som hemmeligheder, slettes/expires efter flash (token-expiry findes allerede: default 48 t, max 14 dage — godt); (2) på sigt: device-genereret nøgle ved første boot + rotation af den bagte nøgle efter enrollment; (3) kryptér `ssh_private_key`-kolonnen eller flyt til secrets-store. (Relaterer til R19/tunnel-conduit og ADR-001 amendment 5.)

### 4.2 🟡 GEN-10: `_headend_api_url`-fallback er `http://127.0.0.1:8000/api`

Hvis hverken settings eller env er sat på en ny headend, genereres bootstrap.yaml/images med en ubrugelig localhost-URL — stille fejl frem for fail-fast. Lav risiko i praksis (install_headend.sh sætter `BASE_URL`), men provisioning bør nægte at generere med localhost-URL når `TIMELAPSE_ENV=staging|prod`.

### 4.3 🟡 GEN-11: Hvor bygges edge-images til prod? (beslutning mangler)

Flashable-build kræver Docker buildx på den headend hvor provisioneringen kører. Skal prod-headenden selv kunne generere edges (⇒ Docker + build-toolchain skal hærdes og præinstalleres på prod), eller bygges rootfs på R&D og promoveres som signeret artifact, mens prod kun laver injection (token/nøgler/WiFi)? Promotion-metodikken dækker ikke edge-images i dag. **Anbefaling:** afgør i promotion-sporet; indtil da dokumenterer manualen Docker-kravet eksplicit.

### 4.4 ✅ Positivt

One-time bootstrap-tokens med expiry + batch-mode med use_count, automatisk revokering af ældre åbne tokens for samme lokation, credential-rotation ved re-enrollment, auto-DeviceAssignment ved kamera-bundne tokens, GPG-signeret manifest + SBOM pr. image, `/api/api/devices/enroll`-bagudkompatibilitets-aliaset er bevidst og dokumenteret i koden, og jetson-installeren (`install_timelapse_edge.sh`) beviser at "edge oven på eksisterende Linux" allerede er et understøttet spor.

---

## 5. Sameksistens-facit (CrushFTP)

| Kanal | Port | Status på staging/prod |
|---|---|---|
| UI/API (nginx, TLS) | 8443 | ✅ Sikkert: preflight + install afviser 21/22/80/443 hårdt; DNS-01 rører ingen port |
| Certifikat | (ingen) | ✅ DNS-01 — uafhængig af CrushFTP's 80/443 |
| SFTP-upload fra edge | 22222 | 🔴 Mekanik findes, men intet generator-trin (GEN-01) OG kode-default peger på 22 (GEN-02) |
| Reverse SSH-tunnel | ? | 🟠 Udefineret; edge-fallback er 22 (GEN-03) |
| Tunnel-portallokering | 2201+ | 🟠 Kan ramme reserveret 2222 (GEN-04) |
| Marketingsite | — | ✅ Hostes bevidst separat (ingen konflikt) |
| Syslog | 5514 | ✅ Ikke-privilegeret, konfliktfri |

---

## 6. Nye dokumenter skrevet i dag

1. **`INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md`** — komplet trin-for-trin for staging/prod oven på kørende Mac med CrushFTP, inkl. det manglende SFTP-ingress-trin (manuel procedure indtil GEN-01 er scriptet) og verifikationstjekliste.
2. **`INSTALLATIONSMANUAL_EDGE_GENERATOR_v1.md`** — begge spor: (A) flashbart image (.img.gz) og (B) installation oven på eksisterende Linux (jetson-mønsteret), inkl. sikkerhedsregler for image-håndtering.

## 7. Handlingsliste

| # | Handling | Ejer (forslag) | Prioritet |
|---|---|---|---|
| 1 | GEN-02: kode-default `sftp_port` 22→22222 + seed settings i install + kontrakttest | Codex | 🔴 Før staging-install |
| 2 | GEN-01: SFTP-ingress som scriptet Fase 2b (genbrug deploy/ssh/-profilen) | Codex | 🔴 Før staging-install |
| 3 | GEN-03: Beslut tunnel-ingress-port for staging/prod | **Peter** | 🟠 Beslutning |
| 4 | GEN-04: Port-allokator: reserved-exclusion + range | Codex | 🟠 |
| 5 | GEN-05/GEN-06: docs-rettelser (v10 §12, example-confs) | Claude | 🟡 |
| 6 | GEN-09: image-som-hemmelighed-regel nu; device-genereret nøgle på sigt | Claude (doc) + Codex (kode) | 🟠 |
| 7 | GEN-11: Beslut build-sted for prod-edge-images | **Peter** (promotion-sporet) | 🟡 Beslutning |

---

*Alle linjenumre pr. working tree 2026-07-17 (main @ 5987852f). Ingen kode ændret i denne session.*
