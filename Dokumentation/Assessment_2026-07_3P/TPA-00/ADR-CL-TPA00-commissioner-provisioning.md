# ADR — Commissioner Provisioning & Fail-Closed Edge Access (TPA-00 / SEC-016)

- **Status:** Proposed (implementering vedlagt; kræver live-verifikation + Codex kryds-review før deploy)
- **Dato:** 2026-07-31 · **Forfatter:** Claude · **Erstatter:** den verdenskendte fabriks-TOTP-fallback
- **Fund:** TPA-00 (assessment) = SEC-016 (handover 2026-07-15), CRA Annex I / IEC 62443-4-2 CR 1.5
- **Tre spørgsmål:** *Hvorfor?* Sikker, simpel idriftsættelse af ny edge uden verdenskendt secret. *Fordi?* Den nuværende base i BT-PAN-TOTP-hierarkiet er `JBSWY3DPEHPK3PXP` (pyotp-demo, fail-open). *For hvem?* Idriftsætteren i marken, kunden (sikkerhed), CRA/62443-compliance.

## Kontekst (verificeret i kode, HEAD eed9e3c8)

- Edge-management tilgås over BT PAN via TOTP (`edge/scripts/totp-service.py`). Secret-hierarki (headend `main.py:5270-5296`): **fabriksstandard → global → kunde → site → kamera**. Basen er den verdenskendte secret, og manglende secret giver adgang (fail-**open**).
- Headend har allerede: brugere med `password_hash`, `totp_secret`, `mfa_enabled`, `role` (`database.py:268`); WebAuthn/FIDO2 = Windows Hello/Touch ID (`main.py:1175+`, `WebAuthnCredential`-tabel); per-kamera secret-regenerering (`/api/admin/cameras/{id}/bt-totp-regenerate`); enheds-ed25519-nøgle (`Device.ssh_pubkey`); QR-teknikerlogin der kræver netværk (`edge/technician_auth.py`).
- Roller i dag: `super_admin, admin, operator, viewer` (whitelist `main.py:2069,2095`). Ingen idriftsætter-rolle.

## Beslutning

### 1. Ny RBAC-rolle: `commissioner` (idriftsætter)

Additiv rolle med ét formål: bootstrappe og konfigurere nye edge-enheder. Rettigheder: edge-lokal management-adgang (BT PAN) + enrollment-bekræftelse. IKKE kundedata-adgang, IKKE headend-admin. Tilføjes de to whitelists + `require_role`-brug. Rollen kan tildeles pr. bruger i Brugere-UI'et.

### 2. Fabriks-fallback fjernes → fail-closed per-device secret

Den verdenskendte `JBSWY3DPEHPK3PXP` fjernes som base. I stedet:

- **Per-device bootstrap-secret** genereres ved image-generering (`headend/bt_totp_security.py::generate_bootstrap_secret`), gemmes krypteret i CMDB på enheden og trykkes på idriftsættelses-arket / vises i headend-generatoren. Aldrig en delt konstant.
- Findes intet secret (uprovisioneret) → edge-management **nægter** og viser "ikke idriftsat" (fail closed), i stedet for at acceptere en default.
- Base-laget i hierarkiet leveres nu af `resolve_bt_totp_base(db, device)` som returnerer per-device bootstrap-secret eller `None` (→ deny). Global/kunde/site/kamera-lagene er uændrede ovenpå.

### 3. Offline idriftsætter-cache (bagt ind ved image-generering)

Ved edge-generering bages en **signeret** offline-kopi af idriftsætter-brugerne ind (`headend/commissioner.py::build_commissioner_bundle`):

```
CommissionerBundle (signeret af headend signing-key, SemVer'd, med udløb):
  issued_at, expires_at, headend_key_id
  device_id (bundtet er bundet til netop denne enhed — kan ikke flyttes)
  commissioners: [ {username, password_hash(bcrypt), totp_secret(krypteret),
                    webauthn_cred_ids[], role: commissioner} ]
```

Edge verificerer signatur + `device_id` + udløb før den stoler på cachen (`edge/commissioner/auth.py::load_verified_cache`). Fail closed ved ugyldig/udløbet/forkert-device signatur.

### 4. Login-metode-resolver + obligatorisk login-besked

`edge/commissioner/auth.py::resolve_login_method(online, cache, factors)` vælger stærkeste tilgængelige metode og returnerer en **besked der SKAL vises i login-UI'et**:

| Situation | Metode | Login-besked (dansk) |
|---|---|---|
| Online + WebAuthn tilgængelig | Platform-authenticator | "Online — Windows Hello / Touch ID (verificeret mod headend)" |
| Online + TOTP | Bruger + adgangskode + personlig TOTP mod headend | "Online — bruger, adgangskode og personlig TOTP (verificeret mod headend)" |
| Offline + gyldig cache | Lokal bruger + adgangskode + personlig TOTP mod signeret cache | "Offline — verificeret mod lokal, signeret idriftsætter-cache (udløber {dato})" |
| Første idriftsættelse (per-device bootstrap) | Bootstrap-kode + idriftsætter-bruger/adgangskode | "Førstegangs-idriftsættelse — per-device bootstrap-kode (engangs, skift ved online-sync)" |
| Ingen af ovenstående | — | Fail closed: "Enheden er ikke idriftsat / cachen er udløbet. Kontakt headend." |

### 5. Online-sync holder idriftsætterne opdateret

Når edge har netværk henter agenten periodisk et frisk signeret bundle (`GET /api/commissioner/bundle`, rolle-gated) og erstatter cachen. Herved: nye/fjernede idriftsættere, roterede TOTP-secrets og WebAuthn-registreringer propagerer. Offline bruges seneste gyldige (ikke-udløbne) bundle.

## Alternativer overvejet

- **Beholde fabriks-default men kræve skift ved enrollment.** Afvist: stadig fail-open i vinduet før skift; CRA forbyder kendt default overhovedet.
- **Kun online-login (nuværende QR-flow).** Afvist: idriftsættelse sker ofte uden netværk — det er hele pointen med offline-cachen.
- **Symmetrisk delt idriftsætter-secret.** Afvist: samme klasse som TPA-00 (delt hemmelighed).

## Konsekvenser

Positive: ingen verdenskendt secret; idriftsættelse virker offline men sikkert; stærkere faktorer bruges automatisk online; brugeren ser altid hvilken metode der gælder. Negative: signeringsnøgle-disciplin (genbruger eksisterende OTA/config-signeringskæde); cache-udløb kræver periodisk online-sync (bevidst — begrænser en stjålet edge). Migration: eksisterende enheder på factory-default skal re-provisioneres (engangs; se runbook).

## Valideringsvej

Vedlagte moduler er unit-testede i sandkasse (rene funktioner + hmac/hashlib). **Kan ikke** verificeres mod kørende system herfra: (a) at enrollment faktisk sætter per-device secret, (b) BT-PAN-service-integration, (c) WebAuthn-online-kald. Codex bedes live-verificere disse tre + køre fuld suite. Reversibelt: alt er additivt bag ny rolle/moduler; de to `main.py`-litteral-edits + edge-default-edit er de eneste ændringer i eksisterende filer og er py_compile-verificeret.
