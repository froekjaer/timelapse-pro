# Codex arbejdsordre — TPA-00 live-verifikation & lukning

**Fra:** Claude · **Dato:** 2026-07-31 · **Branch:** `feature/tpa-00-commissioner-auth` (commit `48dcbbe`)
**Til Codex:** Peter beder dig live-verificere og lukke fire integrationspunkter. Jeg har rørt så lidt som muligt i eksisterende filer; alt nyt er additivt og fail-closed. Rør gerne det hele — det er din lane (provisionering/ops). Line-referencer er pr. commit `48dcbbe`.

## Kontekst i én sætning

Den verdenskendte fabriks-TOTP `JBSWY3DPEHPK3PXP` er fjernet som funktionel fallback (TPA-00/SEC-016); i stedet: per-device bootstrap-secret + signeret, device-bundet offline idriftsætter-cache + login-metode-resolver med obligatorisk besked. Reference-signering er HMAC (testbar); produktion skal bruge jeres Ed25519 OTA/config-kæde.

## Filoversigt

Nye (fuldt unit-testede — 28 grønne): `headend/bt_totp_security.py`, `headend/commissioner.py`, `edge/commissioner_auth.py`, `headend/tools/restore_drill.py`, `headend/tests/test_tpa00_commissioner.py`, `headend/tests/test_restore_drill.py`.
Ændrede (kirurgisk): `headend/main.py` (rolle-whitelist ×2, base-secret fail-closed ×2), `edge/scripts/totp-service.py` (default tømt + `/verify`-guard), `headend/database.py` (kommentar).
Design: `Dokumentation/Assessment_2026-07_3P/TPA-00/ADR-CL-TPA00-commissioner-provisioning.md` + `PROCES_Idriftsaettelse_og_R09.md`.

## De fire integrationspunkter (dét jeg ikke kunne køre)

### IP-1 — Mint + gem per-device secret ved bootstrap (fail-closed base)
- **Hvor:** `headend/main.py::bootstrap` (`@app.post("/api/bootstrap")`, ~linje 2126). Her oprettes/opdateres `Device` ved edgens første kontakt — det naturlige sted.
- **Gør:** ved oprettelse af en ny device, mint `secret = bt_totp_security.generate_bootstrap_secret()` og gem krypteret som setting-nøgle `bt_totp_secret_<device_id>` (så `resolve_bt_totp_base`'s getter i `main.py` finder den — jeg brugte `_get_setting(_d, f"bt_totp_secret_{_x}", "")`). Brug `cmdb._encrypt`/`_decrypt` (Fernet, `cmdb.py:448/453`) hvis I vil kryptere i settings, eller gem på `Device`-kolonne — jeres valg, men **aldrig** en delt konstant.
- **Verificér:** efter bootstrap returnerer `GET /api/admin/cameras/{id}/bt-totp-qr` nu `source="device-bootstrap"` (ikke `factory-default`), og `is_factory_default=false`. En uprovisioneret enhed giver `source="unprovisioned"` og tomt secret (edge nægter — det er meningen).

### IP-2 — Byt HMAC-signering ud med Ed25519 OTA/config-kæden
- **Hvor:** `headend/commissioner.py::_sign` og `edge/commissioner_auth.py::load_verified_cache` (begge HMAC-SHA256 nu).
- **Gør:** erstat `_sign`/verifikationen med jeres eksisterende asymmetriske signering (samme trust-model som signeret OTA/config). **Bundleformat, felter, device-binding og udløb ændres IKKE** — kun signeringsprimitiven. Behold `hmac.compare_digest`-mønsteret → brug konstant-tids signaturverifikation.
- **Verificér:** `verify_commissioner_bundle` afviser stadig tampered/forkert-device/udløbet bundle (mine tests dækker adfærden; byt nøglen og kør dem igen).

### IP-3 — Wire `GET /api/commissioner/bundle` (online-sync)
- **Hvorfor ikke gjort:** jeg wire'de den bevidst IKKE i `main.py` for ikke at hæve arkitektur-ratchet (18541). Læg den i et **API-modul/router** (jf. K2: ingen nye endpoints i `main.py`), fx `headend/api/commissioner_api.py`, og `include_router`.
- **Kontrakt:** rolle-gated (kræv `require_role("super_admin","admin")` til at *udstede* — enheden henter med sin device-auth). Returnér `build_commissioner_bundle(device_id=<kaldende device>, commissioners=<alle aktive users med role='commissioner'>, signing_key=<Ed25519>, key_id=...)`. `password_hash` = brugerens eksisterende bcrypt; `totp_secret_enc` = brugerens TOTP-secret krypteret med enhedens nøgle (se IP-4).
- **Edge-side:** agenten kalder endpointet periodisk når online og gemmer bundle lokalt; edge verificerer med `load_verified_cache` før brug.

### IP-4 — Edge Fernet-dekryptering af TOTP-secret
- **Hvor:** `edge/commissioner_auth.py::authenticate_offline(..., decrypt_totp_secret=...)` — injektionspunkt.
- **Gør:** produktionskaldet skal sende enhedens rigtige dekryptering (edge har allerede en lokal nøgle-mekanik; brug den). Headend krypterer `totp_secret_enc` med samme enhedsnøgle når bundtet bygges (IP-3), så kun netop denne enhed kan læse det. Hold plaintext-TOTP i hukommelsen så kort som muligt.

## Kommandoer — kør disse

```bash
# 1) Governance + nye tests (samme som CI-kommandoen)
PYTHONPATH="$PWD:$PWD/headend:$PWD/edge" \
  pytest tests/test_architecture_ratchet.py headend/tests/test_route_auth_coverage.py \
         headend/tests/test_tpa00_commissioner.py headend/tests/test_restore_drill.py \
         --import-mode=importlib -m "not integration" -p no:randomly -q
# forventet: alle grønne; ratchet skal blive på 18541

# 2) Fuld suite (din miljøklasse — BT-PAN-hardware/WebAuthn kan jeg ikke)
pytest tests headend/tests edge/ai/tests --import-mode=importlib -m "not integration" -p no:randomly -q

# 3) R09 restore-drill selvtest (logikken)
python3 headend/tools/restore_drill.py --selftest    # forventet exit 0

# 4) R09 rigtig kørsel på Mac Mini (non-destruktiv — rører ALDRIG prod-DB)
python3 headend/tools/restore_drill.py --engine postgres \
  --archive /Volumes/Backup/timelapse-backup-headend-<dato>.tar.gz \
  --prod-db timelapse_db --scratch-db timelapse_db_restoretest \
  --evidence-out /tmp/restore-drill-<dato>.md
```

## Acceptkriterier (så vi ved det virker)

1. Efter bootstrap: ingen enhed rapporterer `source="factory-default"`; `grep -rn '"JBSWY3DPEHPK3PXP"'` giver kun denylist-forekomster (`bt_totp_security.py:28`, `edge/scripts/totp-service.py:49`, testen).
2. Uprovisioneret edge: `/verify` returnerer 403 "ikke idriftsat" (fail closed) — ikke adgang.
3. Login-UI viser altid den valgte metode/online-status (WebAuthn/TOTP-online/offline-cache/bootstrap).
4. `verify_commissioner_bundle` afviser tampered/forkert-device/udløbet bundle med Ed25519 aktiv.
5. R09-drill producerer et PASS-evidens-dokument → registrér i GRC (lukker R09/P0-03).
6. Route-auth-gaten er grøn OG kan ikke længere blive en stille no-op (TPA-01).

## Registrering & handover

- Registrér fund/afvigelser fail-closed i PostgreSQL GRC (som normalt).
- Skriv en handover-entry tilbage til mig/Peter når IP-1..4 er verificeret, med run-output og evt. ændrede filer.
- **Rør ikke** `timelapse-pro`-freeze-reglerne fra REVIEW-001 — de gjaldt kun review-øvelsen; dette er almindeligt produktionsarbejde på `main`-sporet.

## Pas på

Auth-kritisk kode — **må ikke deployes før dine IP-1..4 + fuld suite er grønne**. Eksisterende enheder på factory-default skal re-provisioneres (engangs; bootstrap sætter nu per-device secret). Branch protection på `main` bør aktiveres (TPA-01) så CI ikke kan omgås.
