# SEC-016: Fabriks-BT-TOTP — delt secret lukket korrekt, men uden sikker erstatning

**Dato:** 2026-08-16
**Status:** ⚠️ DELVIST LØST — delt secret lukket (✅), sikker erstatning mangler (❌ åben som SEC-016-BOOTSTRAP-GAP)
**Prioritet:** HIGH
**Fundet via:** Claude_QA_Review_2026-07-17.md; gen-identificeret af Kimi 2026-08-15; gen-identificeret ved TL-043EB9E72EFD-incident 2026-08-16
**GRC:** `SEC-016` (finding, closed), `SEC-016-BOOTSTRAP-GAP` (finding, open), `ACT-SEC-016-BOOTSTRAP-GAP` (action, open)

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

- `headend/tools/inject_edge_image.py` har allerede parametre til at bage et **unikt per-enhed** secret ind ved image-build (`bt_totp_secret`/`bt_totp_sid`, linje ~890, ~1079) — det er den korrekte, sikre form af "fabriks-TOTP" (modsat det lukkede delte secret). Parameteren er dog **valgfri** (`if not bt_totp_secret or not bt_totp_sid:` — logger/springer over, fejler ikke buildet).
- `users.on_site_service` (Boolean, `headend/database.py:288`) er den RBAC-tag Peter refererer til — men den styrer i dag kun hvem der har LOV til at se/oprette et BT-TOTP-secret i admin-UI'en (`CameraPage.tsx`), ikke en automatisk push-til-enhed.
- `edge/scripts/totp-service.py::_sync_totp_from_headend()` er den ENESTE kode-vej der henter et secret fra CMDB ned til enheden — men den kaldes **udelukkende** fra en knap inde i den allerede-loggede-ind `/mgmt/*`-UI. Kildekodens egen kommentar bekræfter dette er bevidst: *"TOTP synces IKKE automatisk ved boot ... Rotation sker KUN ved eksplicit handling."*
- Der findes ingen kode noget sted (headend eller edge) der automatisk pusher tekniker-credentials ved første headend-forbindelse, og ingen automatisk deaktivering af et fabrikssecret efter bekræftet teknikerlogin.

**Konklusion:** det tiltænkte design er kun halvt bygget. Per-enhed-secret-baking ved image-build eksisterer men er valgfri. RBAC-tagget til "hvem må" eksisterer. Selve auto-push-og-auto-deaktivér-pipelinen mellem dem findes ikke.

### Konkret konsekvens: TL-043EB9E72EFD

Reproduceret 2026-08-16 under en ikke-relateret incident (se `HANDOVER_LOG.md` samme dato): enhedens image blev tydeligvis bygget uden `bt_totp_secret`/`bt_totp_sid`. `/etc/timelapse/bt-config.yaml` har derfor aldrig haft et secret, og login-siden på port 8443 viser "Lokal adgang er ikke provisioneret" uden kodefelt overhovedet — der er intet at scanne, intet at logge ind med. Eneste virkende vej ind var direkte SSH (via headend-nøgle over reverse-tunnel, eller direkte LAN-adgang) til manuelt at skrive filen. En enhed uden LAN-nærhed eller fungerende SSH-tunnel ville have været permanent utilgængelig for lokal Servicetekniker-adgang.

## Anbefalede næste skridt (jf. `ACT-SEC-016-BOOTSTRAP-GAP`)

1. **Gør `bt_totp_secret`/`bt_totp_sid` obligatorisk** i `inject_edge_image.py` — fejl image-build i stedet for at producere en enhed uden bootstrap-mulighed.
2. **Design og byg** den automatiske "RBAC-tag → push tekniker-cert ved første headend-forbindelse → deaktivér fabrikssecret"-pipeline Peter beskrev, hvis det fortsat er den ønskede UX.
3. **For allerede udrullede enheder uden secret** (som TL-043EB9E72EFD var indtil i dag): dokumentér SSH/fysisk-konsol-skrivning af `bt-config.yaml` som den sanktionerede break-glass-procedure, indtil (1)/(2) er på plads.

## Referencer

- `Claude_QA_Review_2026-07-17.md` — første fund
- `HANDOVER_LOG.md` 2026-08-16 — TL-043EB9E72EFD-incident, gen-fund, Peters forklaring af tiltænkt design
- Lukningscommits: `48dcbbe9`, `540daea4`, `6bb4299a`, `ec277259`
- `headend/tools/inject_edge_image.py` (per-enhed secret-parametre)
- `edge/scripts/totp-service.py` (`_sync_totp_from_headend`, `_login_page`)
- `tests/test_edge_release_contract.py::test_local_totp_qr_never_returns_a_shared_factory_secret`
