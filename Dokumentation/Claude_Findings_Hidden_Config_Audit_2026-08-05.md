# Findings — Fuld gennemgang: skjult/hardkodet config, MFA-huller, session-model (2026-08-05)

> **Format:** Per Mission Framework Collaborative Intelligence Evaluation
> Protocol (samme evidensdisciplin som
> `Claude_Findings_Edge_Generator_og_TL-043EB9E72EFD_2026-08-04.md`) og
> `froekjaer/mission-framework`s principper (Evidence over Assumptions,
> Provenance Matters, Trust by Design). Ingen påstand uden fil:linje-evidens.
> Fire parallelle, uafhængige agent-gennemgange (edge/, headend/*.py,
> headend/api/*.py, timelapse-ui) blev kørt og krydsrefereret; findings under
> er konsolideret og verificeret af mig (Claude) før implementering.

**Opdrag (Peter, 2026-08-05):** "sikre der ikke er skjulte variable i kode
eller env. variable, der ikke er i databasen, og kan skiftes via UI'en...
Dette er vigtigt, da der er for mange der har ændret kode." + sikre at
væsentlige edge-parametre kan ændres via UI'en + løsne session-IP-pinning så
Edge'en er nåbar fra alle interfaces (BT/WiFi/Ethernet/routet net).

**Kontekst:** Udført alene, uden opsyn (Peter tog på havnen), efter grundig
autorisation til at "komme så langt som muligt". Alt arbejde er testet
(`py_compile`, fuld ikke-integrationssuite) før commit til denne rapport.
**Intet er deployeret til nogen fysisk enhed** — alt er repo-ændringer.

---

## Del A — Implementeret og testet i dag

### A-1 · Session-IP-pinning løsnet (edge lokal portal)

**Fil:** `edge/scripts/totp-service.py`

Sessionen var før hårdt bundet til klientens IP (`sess["ip"] != ip` →
øjeblikkelig afvisning). Det brød legitim adgang fra en tekniker, hvis
apparente kilde-IP skiftede midt i besøget — BT-PAN uddeler dynamiske IP'er
(`192.168.42.10-50`), WiFi kan roame mellem AP'er, og routet adgang kan NAT'e
forskelligt ved reconnect. **Rettet:** sessionen valideres nu udelukkende på
selve tokenet (256-bit HMAC-afledt, kun udstedt efter korrekt TOTP-kode) —
IP'en spores stadig (audit-log + BT-PAN relay-whitelisting følger nu
sessionen, ikke kun login-IP'en), men er ikke længere en hård gate. Al
oprydning (iptables-whitelist, PTY-shell-lukning) sker fortsat korrekt ved
reel timeout.

**Status:** Kun i repoet — **ikke deployeret** til `TL-C87FF9587CA0`.

### A-2 · MFA-håndhævelse rettet i 3 admin-API-routere

**Filer:** `headend/api/grc_register_api.py`, `headend/api/storage_api.py`,
`headend/api/headend_generator_api.py`

**Fund:** Disse tre filer genimplementerede hver deres egen
`_current_viewer`/`_require_platform_admin`-autentificering i stedet for at
bruge den delte `require_role()` (main.py), og havde alle glemt MFA-tjekket,
som `require_role()` ellers håndhæver automatisk. Konsekvens: en
admin/super_admin-session autentificeret med KUN password (ingen fuldført
MFA-udfordring) kunne stadig mutere GRC-registret, generere
bootstrap-tokens/download installationspakker med SSH-bootstrap-materiale
(headend-generator), og oprette/ændre storage-bindings — mens de korrekt var
blokeret fra andre, arguably mindre følsomme endpoints. Bekræftet ved
kode-læsning: alle tre filers `_require_platform_admin` bygger allerede på
`_current_viewer`, så MFA-tjekket kun manglede ét sted pr. fil.

**Rettet:** Tilføjet identisk MFA-tjek (samme kald til
`_mfa_required_for_user`/`_session_is_mfa_verified`/`_session_payload` som
`require_role()` selv bruger) i alle tre filers `_current_viewer`. Minimal,
mekanisk ændring — ingen ny funktionalitet, ingen breaking change for
brugere der allerede har MFA aktiveret korrekt.

**Confidence:** Høj — direkte kode-sammenligning mellem de "korrekte" filer
(`customer_risk_api.py`, `capture_access_api.py`, som allerede havde
MFA-tjekket) og de tre mangelfulde.

### A-3 · Env-variabel overskrev stille UI-redigerbar DB-indstilling

**Fil:** `headend/api/headend_generator_api.py` (`_bundle_storage_dir`)

**Fund:** `TIMELAPSE_HEADEND_IMAGE_DIR` (env) blev tjekket FØR
`headend_image_artifact_dir` (DB-setting, UI-redigerbar via
`PUT /api/admin/settings`). Kodekommentaren kaldte selv feltet
"UI-redigerbar" — men en admin der ændrede stien i UI'en fik ingen effekt og
ingen fejl, hvis env-variablen stod tilbage fra en tidligere deploy/systemd-
unit. **Samme fejlklasse som den historiske JWT_SECRET-fallback-bug.**

**Rettet:** Precedence vendt om — DB vinder nu, env er kun
bootstrap-fallback før nogen admin har sat DB-værdien.

### A-4 · Site-Look config: hardkodet 'admin' som ændrings-aktør + defense-in-depth

**Fil:** `headend/api/site_look_config_api.py`

**Fund:** `upsert_config`/`delete_config`/`reset_config` skrev alle
bogstaveligt `updated_by='admin'`/`deleted_by='admin'`/`reset_by='admin'`
(med `# TODO: get from auth context`) — audit-loggen for denne feature kunne
derfor ALDRIG vise hvilken admin der reelt lavede en ændring, uanset hvem
der var logget ind. Desuden havde ingen af routerens endpoints sin egen
`require_role`-afhængighed; adgangskontrollen sad KUN på
`app.include_router(..., dependencies=[require_role("super_admin")])` i
main.py — en kommentar der selv erkendte dette ("Keep it platform-admin-only
until tenant-aware authorization is implemented") gør det til et reelt
enkelt-fejlpunkt: hvis routeren nogensinde genmountes eller
`dependencies=[...]`-linjen fjernes ved en fremtidig refaktorering, åbner
site-look-konfiguration for hver kunde/site/kamera sig stille for
uautentificeret læs/skriv.

**Rettet:** Ny `_actor_username()`-afhængighed, der (a) slår den faktiske
brugers username op og bruger det i stedet for den hardkodede streng, og (b)
genchecker `role == "super_admin"` direkte på de tre write-endpoints som
defense-in-depth, uafhængigt af mount-niveau-beskyttelsen.

### A-5 · JWT_SECRET-guard manglede `staging` (samme bug-klasse, ét resterende hul)

**Fil:** `headend/main.py:84-92`

**Fund:** `JWT_SECRET`s fail-closed-tjek (kaster `RuntimeError` hvis
manglende/for kort) gjaldt kun `{"prod", "production"}` — men
`_AGENT_LOCKED_ENVIRONMENTS = {"staging", "prod", "production"}` (linje
1031) behandler `staging` som produktions-nært alle andre steder i filen. En
staging-Headend med et defekt/uindlæst env-file ville stille falde tilbage
til en tilfældig `JWT_SECRET` ved hver genstart — ugyldiggør alle sessions
uden advarsel. **Rettet:** `staging` tilføjet til det håndhævede sæt.

### A-6 · `JWT_EXPIRE_H`-drift: 3 af 4 login-veje ignorerede den admin-konfigurerede session-policy

**Fil:** `headend/main.py` — `webauthn_login_complete`, `confirm_mfa`,
`verify_mfa`

**Fund:** Kun password-login-stien læste den DB-konfigurerbare
`session_policy.session_duration_hours` (via `_resolve_session_policy`).
WebAuthn-login, MFA-enrollment-bekræftelse og TOTP-verify hardkodede alle
`JWT_EXPIRE_H * 3600` (12 timer) direkte. En admin der strammer
session-levetiden til fx 2 timer af compliance-grunde ville opdage, at
MFA/WebAuthn-logins stadig udsteder 12-timers sessions — reel
sikkerhedspolitik-drift, ikke kun kosmetisk.

**Rettet:** Alle tre veje beregner nu `session_duration_hours` via samme
`_resolve_session_policy(db, user)` som password-stien, OG indlejrer den
resulterende `max_age` i selve JWT-payloaden (ikke kun cookie-headeren) —
nødvendigt fordi `/api/auth/me`s rullende session-fornyelse læser `max_age`
tilbage UD AF det eksisterende token for at bevare den oprindeligt tiltænkte
session-længde ved hver fornyelse. Uden dette ville en korrekt udstedt
kortere session stille blive forlænget til 12 timer ved første
`/api/auth/me`-kald.

### A-7 · Edge: legacy unsigneret git-update-vej dobbelt-lukket + gjort audit-synlig

**Fil:** `edge/agent.py` — `_check_update()`, `_run_update()`

**Fund (HØJESTE severity i hele gennemgangen):** To separate kodeveje kunne
køre et **unsigneret** `git fetch/pull`/`edge_update.sh` i stedet for det
centrale, Ed25519-signerede artifact-baserede update-flow:
- `_check_update()`: gate var `self._cfg.get("legacy_git_update_enabled") is
  True **OR** os.getenv("TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE") == "1"` — env
  variablen ALENE var nok, ingen Headend-synlighed krævet, og INGEN
  `TIMELAPSE_ENV`-begrænsning overhovedet.
- `_run_update()`: gate var kun env-variabel + `TIMELAPSE_ENV` i
  lab/dev/rd — helt usynligt for Headend/CMDB, ingen DB/config-tilstedeværelse.

Samme fejlklasse som den historiske `JWT_SECRET`-fallback: en
sikkerhedskritisk kontrol (signaturverifikation af kode der køres med fuld
enhedsadgang) der kan deaktiveres af lokal, ikke-auditeret tilstand alene.

**Rettet:** Begge veje kræver nu ALLE TRE samtidigt: Headend-config-flaget
`legacy_git_update_enabled` (aldrig sat nogen steder i kodebasen i dag —
bekræftet ved grep, så denne ændring er strengt mere restriktiv, ingen
eksisterende flow kan gå i stykker) **OG** den lokale env-variabel **OG**
`TIMELAPSE_ENV` i `{lab, dev, development, rd}`. Desuden: et
`_emit_siem_event("legacy_unsigned_update_executed", "warning", ...)`-kald
tilføjet på begge veje, så det aldrig igen kan ske stille — enhver reel
brug bliver nu synlig i SIEM/CMDB.

**Ikke gjort:** Fjernede IKKE koden helt, da jeg ikke med sikkerhed ved om
den er en bevidst dev/lab-bootstrap-nødvej Peter aktivt bruger. Anbefaling:
overvej at fjerne den helt, når/hvis der bekræftes at intet aktivt R&D-flow
afhænger af den.

**Test (alle 6 headend-fixes + edge-fixet):** `py_compile` ren på alle
ændrede filer. Fuld ikke-integrationssuite: **395 passed, 4 skipped**
(samme kendte auth-smoke-mønster som hele ugen), 0 nye fejl. De to allerede
kendte GOV-01-ratchet-fejl (linjetal/routes mod uændret loft) er upåvirkede
i retning — `main.py` fik nødvendige linjer for sikkerhedsrettelserne, men
**0 nye direkte routes**.

---

## Del B — OPDATERET 2026-08-05 (samme dag, efter Peter kom tilbage): begge besluttet og implementeret

Peter tog stilling til begge, samme dag: **B-1 = detektion + alarm, ikke
blokering** (allowlist droppet til fordel for DoS-mitigering). **B-2 =
break-glass skal være reelt ubegrænset — kompenserende kontrol er fuld
session-logning, ikke adgangsbegrænsning.** Se ny handover-entry
2026-08-05 (sen eftermiddag) for fuld evidens/test. Kort status:

### B-1 · Løst: global rate-limiter + DoS-alarm (IKKE allowlist)

Peters beslutning: en allowlist er rigtig på sigt, men for nu i stedet en
DoS-mitigering + mail/SMS-alarm ved udløsning. `syslog_receiver.py` havde
allerede en per-kilde rate-limiter (600/min) — men UDP-kilde-IP'er er
trivielt at forfalske, så den beskytter reelt ikke mod en spredt flod.
**Implementeret:** en GLOBAL rate-limiter (alle kilder tilsammen, default
6000/min) som den reelle DoS-bremse, plus en cooldown'et (15 min) alarm via
den eksisterende email/SMS/Teams-pipeline (`ai/notify.py`) når enten den
globale eller en per-kilde-grænse udløses. Testet: en simuleret flod fra 15
forfalskede kilde-IP'er udløste den globale grænse korrekt og sendte
præcis ÉN alarm, ikke 15.

### B-2 · Løst (fundament): break-glass-kontoen findes nu reelt på enheden

Peters beslutning bekræftede noget vigtigt jeg fandt undervejs: der er i
dag **ingen kode nogen steder**, der rent faktisk opretter `emergency`-kontoen
på en fysisk enhed — break-glass var indtil nu kun database-bogføring
(bekræftet ved grep). **Implementeret:** kontoen bages nu ind i alle
fremtidige images ved første boot (`timelapse-breakglass-setup.service`),
kun nøgle-login (password låst), fuld ubegrænset sudo (Peters eksplicitte
instruks), og enhver session gennem kontoen optages i sin helhed (kommandoer
OG output) og sendes videre til SIEM. Aktive break-glass-nøgler leveres til
enheden via den eksisterende, allerede-autentificerede config-poll-kanal
(ikke et nyt, usikkert push-flow). Fuldt testet i isoleret container
(kontooprettelse, sudo, session-optagelse) + Python-enhedstests
(nøgle-anvendelse, hændelses-videresendelse).

**IKKE bygget endnu, bevidst afgrænset til en senere runde:** upload af
session-transskripter til et permanent Headend-arkiv udover selve
SIEM-hændelserne, Ollama-baseret gennemgang af transskripterne for
mistænkelig aktivitet, og en eventuel "enheden er under revision efter
break-glass"-tilstand før normal tillid genoptages. Se ny handover-entry
for det konkrete forslag til næste runde.

### B-3 · Base URL for reverse-tunnel-ingress under provisionering hævder at være "governed" men er env-only

`edge_provisioning_security.py:47-52` — docstring siger "Resolve... from
governed settings", implementeringen bruger rene env-variabler
(`TIMELAPSE_TUNNEL_HOST/PORT/USER`). Mønsteret for at gøre det rigtigt
findes allerede i samme fil (`sftp_port` via `_get_setting`). Lav risiko,
men kommentar/implementering stemmer ikke overens — bør rettes eller
kommentaren nedtones.

---

## Del C — Fuldt katalog, ikke ændret (til fremtidigt arbejde)

Se de fire agent-rapporter (gemt i sessionen, ikke som separate filer for
at undgå dokumentationseksplosion) for komplet linje-for-linje-evidens.
Konsolideret oversigt efter alvorlighed:

**Medium (operationelle knapper der plausibelt bør være DB/UI-styrede, men
hvor default-værdien er sikker):**
- ITIM-tærskler (disk/mem/cpu-temp/heartbeat-staleness/defect-rate) hardkodet
  i `itim.py`, IKKE wired ind i den allerede eksisterende, DB-drevne
  `ItimAlertRule`-motor i samme fil.
- SIEM retention (`TIMELAPSE_SIEM_RETENTION_DAYS`, default 0 = ubegrænset
  vækst) og ingest-ratebegrænsning, env-only.
- Login-rate-limits (`10/minute` login, `20/hour`/`30/minute`
  technician-auth) hardkodet som decorator-literals — ingen DB/UI-vej til at
  stramme/løsne lockout-følsomhed.
- `live_view_max_duration_s` default (180s) og grænser (30-86400s)
  hardkodet — kun selve per-enheds-værdien er DB-styret.
- SSH break-glass-parametre (`_CANDIDATE_USERNAMES`, `_SSH_TIMEOUT_S=8`,
  nøglesti) fuldt hardkodet i `device_ssh_access_api.py`.
- Edge: HTTP/SFTP retry-/timeout-politik (`headend_client.py`,
  `upload/sftp.py`), SSH-tunnel timing-konstanter (inkonsistent med
  søskendefelter der ER config-drevne), TOTP brute-force-lockout-politik
  (ingen config-flade overhovedet), `session_timeout` for lokal portal (kun
  rettelig via SSH), TOTP `valid_window` (kun sættelig LOKALT, aldrig fra
  Headend — en tekniker kan udvide replay-tolerance uden Headend-synlighed).
- `key_audit_events`-tabellen (formål: "audit trail for key lifecycle") IKKE
  brugt af nogen af `headend/api/`s SSH-nøgle/TOTP-mutationer — tre
  forskellige, ikke-overlappende audit-destinationer
  (`key_audit_events`/`events`/SIEM) for beslægtede sikkerhedshandlinger.
- `_get_setting()` sluger ALLE DB-fejl stille og returnerer hardkodet
  default — samme "fail silent, not closed"-form som JWT_SECRET-buggen,
  mindre alvorlig da ingen af dens nuværende brugssteder er secrets.
- `redaction_api.py` har sin egen, separate hardkodede storage-root-sti
  adskilt fra den DB-styrede `sftp_base` — reel config-drift-risiko.

**UI-dækningshuller (fundet af UI-mapping-agenten):**
- `RedactionPage.tsx` sender ALTID hardkodet `blur_kernel=51, blur_sigma=30,
  auto_approve=false` — ingen UI-felt overhovedet, selvom backend-API'et
  tydeligvis understøtter tunbare værdier.
- `DriftPage.tsx`: alarm-tærskler (`metric/op/threshold/for_seconds/
  severity`) vises pr. række men er IKKE editerbare — kun enabled/notify.
- `KeyManagementPage.tsx`: `trust_policy` (artifact-verifikationskrav,
  betroede release-signerere) vises, ingen redigeringsvej.
- `SiteLookConfigPanel.tsx`: `storage_path`, `warm_lab_threshold`,
  `cool_lab_threshold`, `warm/cool_kelvin_multiplier` findes i frontend-typen
  og "runder trip" gennem save-payloaden, men har intet input-felt — en
  bruger kan aldrig bevidst ændre dem.
- `CompliancePage.tsx`: update-`accept()` sender hardkodet
  `maintenance_window`/`reboot_required: false` på hver "godkend"-handling.
- `backup_nas_path` har TO separate UI-indgange (generisk Settings-dict og
  BackupPages dedikerede formular) — ubekræftet om de rammer samme
  DB-kolonne.

---

## Del D — Prioriteret anbefaling til Peter

1. **B-1/B-2** — beslut om default-værdierne skal vendes til fail-closed;
   kræver din tilstedeværelse til at verificere break-glass/log-ingest
   fortsat virker bagefter.
2. Overvej at fjerne `edge/agent.py`s legacy git-update-vej helt, hvis intet
   aktivt R&D-flow er afhængigt af den (A-7 er dæmpet, ikke fjernet).
3. Wire ITIM's hardkodede probe-tærskler ind i den eksisterende
   `ItimAlertRule`-motor — arkitekturen findes allerede, kun disse specifikke
   metrics mangler at bruge den.
4. `RedactionPage.tsx`/`DriftPage.tsx`/`KeyManagementPage.tsx` UI-huller —
   relativt afgrænsede, enkeltstående UI-tilføjelser.
5. Konsolidér de tre audit-destinationer (`key_audit_events`/`events`/SIEM)
   for nøgle-/credential-mutationer til én, eller dokumentér eksplicit at
   `key_audit_events` kun dækker `KeyCredential`.
