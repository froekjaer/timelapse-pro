# SEC-016: Fabriks-BT-TOTP — delt secret lukket korrekt, erstatning nu bygget

**Dato:** 2026-08-16 (opdateret samme dag efter Peters beslutning: byg trust-forankret auto-sync)
**Status:** ✅ LØST — delt secret lukket, per-enhed mandatory secret bekræftet allerede håndhævet, automatisk trust-forankret sync bygget
**Prioritet:** HIGH
**Fundet via:** Claude_QA_Review_2026-07-17.md; gen-identificeret af Kimi 2026-08-15; gen-identificeret ved TL-043EB9E72EFD-incident 2026-08-16
**GRC:** `SEC-016` (finding, closed), `SEC-016-BOOTSTRAP-GAP` (finding, closed), `ACT-SEC-016-BOOTSTRAP-GAP` (action, implemented)

## Baggrund

Dette er tredje gang samme emne dukker op i en AI-assistent-session uden at blive permanent dokumenteret — først fundet 2026-07-17, en `HANDOVER_LOG`-entry samme periode uddelegerede eksplicit "SEC-016-dokument + GRC-entry" til "Claude næste session", Kimi fandt en beslægtet rest 2026-08-15, og Peter måtte forklare hele det tiltænkte design igen 2026-08-16 under en live incident. Dette dokument er skrevet for at det ikke skal ske en fjerde gang.

## Del 1 — Det lukkede fund: delt fabrikssecret

`headend/main.py` og `edge/scripts/totp-service.py` brugte tidligere `JBSWY3DPEHPK3PXP` — pyotp's offentligt kendte demo-secret, brugt i utallige tutorials — som fail-open fallback for BT PAN TOTP lokal-management-login, når intet secret var sat i customer/site/device/kamera-hierarkiet. Et **delt** secret på tværs af hele flåden er et known-default-credential-brud:

- **CRA (Cyber Resilience Act) Annex I:** forbyder kendte/gættelige default-credentials.
- **IEC 62443-4-2 CR 1.5:** kræver unikke credentials pr. enhed.

Enhver der kendte (eller googlede) `JBSWY3DPEHPK3PXP` havde reelt lokal management-adgang til **enhver** TimeLapse Pro-enhed i produktion, uanset kunde.

**Status: LUKKET.** Fail-closed erstatning verificeret i commits `48dcbbe9` ("commissioner provisioning + fail-closed edge auth"), `540daea4` ("Close shared TOTP config fallback"), `6bb4299a` ("Close LAB preview traversal and shared TOTP fallback"), `ec277259` ("Security closure: block LAB preview traversal and shared factory TOTP"). Bekræftet 2026-08-16: `grep -rn "JBSWY3DPEHPK3PXP"` i kørende kode på `main` giver **ingen** hits — kun i regressionstests der eksplicit forbyder reintroduktion (`tests/test_edge_release_contract.py`, `tests/test_edge_image_build_contract.py`, `headend/tests/test_security_closure_f001_current.py`). Config-merge-endpointet (`headend/main.py`, `get_config`) returnerer nu `{"secret": "", "sid": "unprovisioned"}` når intet er sat — samme fail-closed adfærd Kimi efterspurgte.

## Del 2 — Det åbne gap: ingen sikker erstatning for bootstrapping

At lukke en sårbarhed fail-closed uden at erstatte den legitime funktion den dækkede, flytter blot problemet. Det er præcis hvad der skete her.

### Det tiltænkte design (per Peter, forklaret 2026-08-16)

> Der er supposed to be a factory deployed TOTP code, that the service technician can use during boot/start-up/initial setup. As soon as the edge has headend connection, the users that has the service technician tag enabled in RBAC will be deployed with relevant TOTP codes and certificates. When the Service Technician is comfortable with the setup, and has tested that her/his login works, the factory TOTP can be permanently disabled.

Dvs.: et **per-enhed** (ikke delt) fabrikssecret til allerførste login, automatisk erstattet af rigtige tekniker-credentials så snart headend-forbindelse er etableret og en RBAC-tagget (`users.on_site_service`) bruger har bekræftet login, hvorefter fabrikssecretet permanent deaktiveres.

### Hvad der faktisk findes i kodebasen

- `headend/tools/inject_edge_image.py` har allerede parametre til at bage et **unikt per-enhed** secret ind ved image-build (`bt_totp_secret`/`bt_totp_sid`) — det er den korrekte, sikre form af "fabriks-TOTP" (modsat det lukkede delte secret). **Korrigeret fund:** ved nærmere kodegennemgang er dette allerede **obligatorisk**, ikke valgfrit — `inject_edge_image()` (linje ~1128) kaster `ValueError("Flashable image kræver en unik, provisioneret BT TOTP-secret og identifikator")` og producerer intet image, hvis parametrene mangler. Bekræftet til stede allerede i commit `dc69c6b2` (2026-08-06). TL-043EB9E72EFD's mangel var derfor historisk/uden-om-værktøjet-provisionering, ikke en kodefejl i den nuværende byggepipeline.
- `users.on_site_service` (Boolean, `headend/database.py:288`) er den RBAC-tag Peter refererer til — den styrede indtil nu kun hvem der har LOV til at se/oprette et BT-TOTP-secret i admin-UI'en (`CameraPage.tsx`).
- `edge/scripts/totp-service.py::_sync_totp_from_headend()` var indtil nu den ENESTE kode-vej der hentede et secret fra CMDB ned til enheden — men den blev **udelukkende** kaldt fra en knap inde i den allerede-loggede-ind `/mgmt/*`-UI, et høne-æg-problem for en fabrikssecret-løs enhed.

### Bygget fix (2026-08-16, samme dag): trust-forankret auto-sync

Peter besluttede design **B**: brug den allerede-eksisterende enheds-identitet (`device_id` + API-token, MAC-bundet ved provisionering) som tillidsanker i stedet for at opfinde en ny tillidsmekanisme. Implementeret i `edge/agent.py`:

- `EdgeAgent._sync_bt_totp_config()` kaldes fra `_apply_config_changes()`, som allerede kører hver gang enhedens `config_version` ændrer sig via den eksisterende, device-token-autentificerede `/config/{device_id}`-heartbeat (`_verify_device_token` på headend-siden — samme tillidsgrænse som alt andet config-flow, ingen ny attack surface).
- Når headend's hierarki (global/kunde/site/kamera) har et reelt secret sat (`sid != "unprovisioned"`) OG det afviger fra enhedens lokale `/etc/timelapse/bt-config.yaml`, skrives det automatisk (atomisk, `0o600`, samme mønster som `totp-service.py::save_config`) og `timelapse-totp.service` genstartes — helt uden at en tekniker skal klikke noget lokalt først.
- Er der **intet** reelt secret sat i hierarkiet endnu (`sid == "unprovisioned"`), rører funktionen IKKE den lokale fil — et eksisterende fabrikssecret overlever urørt, og enheden degraderer aldrig til "ikke provisioneret" bagefter.
- Effekten er at fabrikssecretet reelt erstattes (og dermed de facto deaktiveres) i det øjeblik headend tildeler et rigtigt secret — ingen separat "deaktivér"-handling nødvendig, fordi kun ét secret kan være aktivt ad gangen i den nuværende `totp-service.py`-model.
- **Bevidst forenklet i forhold til Peters fulde beskrivelse:** der er ingen eksplicit "teknikeren har testet login og bekræfter" mellemtrin — overgangen sker automatisk så snart headend har et rigtigt secret, ikke først når en tekniker har logget ind og bekræftet det virker. Praktisk effekt er næsten identisk (fabrikssecretet holder op med at virke), men uden det eksplicitte bekræftelses-gate. Hvis det bekræftelses-trin er vigtigt for jer, er det en opfølgende udvidelse (kræver at `totp-service.py` kan acceptere to secrets samtidig i en overgangsperiode).
- Testdækning: `tests/test_bt_totp_auto_sync.py` (7 tests — skriver nyt secret, rører aldrig et fabrikssecret når headend ikke har noget endnu, idempotent når allerede synkroniseret, bevarer andre `management`-indstillinger i filen, atomisk skrivning med `0o600`, korrekt wiring ind i `_apply_config_changes`, og at en sync-fejl ikke vælter resten af config-apply'en).

### Konkret konsekvens: TL-043EB9E72EFD

Reproduceret 2026-08-16 under en ikke-relateret incident (se `HANDOVER_LOG.md` samme dato): enhedens image blev tydeligvis bygget uden `bt_totp_secret`/`bt_totp_sid` (uden om den nuværende, håndhævede pipeline). `/etc/timelapse/bt-config.yaml` havde derfor aldrig et secret, og login-siden på port 8443 viste "Lokal adgang er ikke provisioneret" uden kodefelt overhovedet. Eneste virkende vej ind var direkte SSH til manuelt at skrive filen. Fra og med denne fix vil enheden nu automatisk hente et rigtigt secret, næste gang et bliver sat for kameraet i CameraPage — ingen manuel filskrivning nødvendig fremover.

## Status

1. ✅ **Obligatorisk per-enhed-secret ved image-build** — bekræftet allerede håndhævet, ingen kodeændring nødvendig.
2. ✅ **Trust-forankret auto-sync-pipeline** — bygget, testet (7/7 grønne), se ovenfor.
3. ⚠️ **Eksplicit teknikerbekræftelse før factory-secret retires** — bevidst udeladt i denne første version (se "bevidst forenklet" ovenfor); kan tilføjes senere hvis ønsket.

## Referencer

- `Claude_QA_Review_2026-07-17.md` — første fund
- `HANDOVER_LOG.md` 2026-08-16 — TL-043EB9E72EFD-incident, gen-fund, Peters forklaring af tiltænkt design
- Lukningscommits: `48dcbbe9`, `540daea4`, `6bb4299a`, `ec277259`
- `headend/tools/inject_edge_image.py` (per-enhed secret-parametre)
- `edge/scripts/totp-service.py` (`_sync_totp_from_headend`, `_login_page`)
- `tests/test_edge_release_contract.py::test_local_totp_qr_never_returns_a_shared_factory_secret`
