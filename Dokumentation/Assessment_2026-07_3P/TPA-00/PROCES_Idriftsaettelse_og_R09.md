# Proces — Idriftsættelse af ny edge (TPA-00), TPA-01 & R09-restore-drill

Praktisk runbook der hører til `ADR-CL-TPA00-commissioner-provisioning.md`. Målgruppe: Peter + Codex. Al kode er additiv, fail-closed og testet i sandkasse; live-verifikation kræves før prod (se §5).

## 1. Idriftsætter-proces (TPA-00) — sådan kommer en ny edge sikkert ud

**Forberedelse i headend (online, før udrejse):**
1. Opret/markér idriftsætter-brugere med den nye rolle `commissioner` (Brugere-UI). Hver får password + personlig TOTP og evt. WebAuthn (Windows Hello/Touch ID).
2. Generér edge-image via headend-generatoren. Ved generering:
   - der mintes et **per-device bootstrap-secret** (`bt_totp_security.generate_bootstrap_secret`) — unikt, aldrig delt. Det trykkes på idriftsættelses-arket / vises i generator-UI'et.
   - der bages en **signeret, device-bundet idriftsætter-cache** ind (`commissioner.build_commissioner_bundle`): idriftsætter-brugernes password-hash (bcrypt), krypterede personlige TOTP-secrets, WebAuthn-cred-id'er, rolle=commissioner, udløb (30 dage default).

**I marken:**
3. Idriftsætteren tænder edge. Login-UI'et kalder `resolve_login_method(...)` og **viser altid hvilken metode der gælder**:
   - Online + WebAuthn → Windows Hello/Touch ID (mod headend).
   - Online uden WebAuthn → bruger + password + personlig TOTP (mod headend).
   - Offline med gyldig cache → bruger + password + personlig TOTP (mod lokal signeret cache; viser udløbsdato).
   - Første idriftsættelse (ingen cache endnu) → per-device bootstrap-kode + idriftsætter-login.
   - Intet af ovenstående → **nægtet** (fail closed): "Enheden er ikke idriftsat…".
4. Så snart der er netværk, henter agenten frisk signeret cache (`GET /api/commissioner/bundle`) → idriftsættere, roterede TOTP og WebAuthn holdes synkroniseret. Offline bruges seneste gyldige cache indtil udløb.

**Det der forsvinder:** den verdenskendte `JBSWY3DPEHPK3PXP` er fjernet som funktionel fallback overalt (headend `main.py` ×2, edge `totp-service.py` default + `/verify`, `database.py`-kommentar). Den optræder nu kun i en **denylist** der aktivt afviser den.

## 2. Nødvendige nye/ændrede filer

Nye (fuldt unit-testede, 24 tests grønne):
- `headend/bt_totp_security.py` — per-device secret, fail-closed base-resolver, weak-secret-denylist.
- `headend/commissioner.py` — byg/verificér signeret device-bundet idriftsætter-cache.
- `edge/commissioner_auth.py` — login-metode-resolver + offline-verifikation + obligatorisk login-besked.
- `headend/tests/test_tpa00_commissioner.py` — 20 tests.
- `headend/tools/restore_drill.py` + `headend/tests/test_restore_drill.py` — R09 (se §4).

Ændrede (kirurgisk, fail-closed, py_compile-verificeret, ratchet holdt på 18541):
- `headend/main.py` — `commissioner`-rolle i whitelists ×2; base-secret fail-closed ×2.
- `edge/scripts/totp-service.py` — default-secret tømt (unprovisioned), `/verify` nægter ved svag/tom secret.
- `headend/database.py` — opdateret kommentar (NULL = uprovisioneret, ikke fabriks-secret).

## 3. Åbne integrationspunkter (kræver Codex/live — jeg kunne ikke køre systemet)

- **Signering:** referencekoden bruger HMAC for testbarhed; produktion skal bruge den eksisterende asymmetriske OTA/config-signeringskæde (Ed25519). Byt `_sign`/`_verify` — bundtformat er uændret.
- **`GET /api/commissioner/bundle`** router er specificeret, ikke wired i `main.py` (bevidst — så ratchet ikke sprænges her; wires ved auth/RBAC-udtræk).
- **TOTP-kryptering på edge:** `decrypt_totp_secret` er et injektionspunkt; produktion bruger enhedens eksisterende Fernet/nøgle.
- **Enrollment sætter faktisk per-device secret:** verificér i den rigtige enrollment-sti at `bt_totp_secret_<device_id>` sættes.

## 4. R09 — non-destruktiv restore-drill

`headend/tools/restore_drill.py` gendanner et backup-arkiv til et **kasserbart** scratch-mål og verificerer (tabeller, row-counts, billed-sha256 mod manifest) uden at røre produktion. Fail-closed guard: nægter hvis scratch-DB == prod-DB eller ikke matcher allowlist (`restoretest|_drill|_scratch|_tmp`).

- **Selvtest (kørt, grøn her):** `python3 headend/tools/restore_drill.py --selftest` — beviser drill-logikken end-to-end inkl. at korruption fanges og at guarden afviser prod-mål. Kørt i CI via `test_restore_drill.py`.
- **Produktion (Mac Mini):**
  ```bash
  python3 headend/tools/restore_drill.py --engine postgres \
    --archive /Volumes/Backup/timelapse-backup-headend-<dato>.tar.gz \
    --prod-db timelapse_db --scratch-db timelapse_db_restoretest \
    --evidence-out /tmp/restore-drill-<dato>.md
  ```
  Producerer et evidens-dokument til GRC-registret (lukker R09/P0-03). Kør efter hver release jf. operational-model.

Dette gør R09-testen non-destruktiv **og** gentagelig **og** evidens-producerende — svaret på "find en non-destruktiv metode at afteste".

## 5. TPA-01 — route-auth-gaten repareret

Den stale hardkodede sti (`/api/settings/config`, KeyError) er fjernet. Testen er omskrevet til prefix-baseret med tre selvforsvar: (a) fejler hvis app ikke mounter nogen /api-routes, (b) sentinel-prefix `/api/admin` SKAL have routes (ellers nægter den at "bestå" en no-op-gate), (c) fejler hvis ingen high-risk-routes blev tjekket (listen er stale). Begge auth-tests grønne. **➡️ Peter:** aktivér branch protection på `main` (kræv grøn CI) — ellers kan gaten stadig omgås ved at pushe udenom.

## 6. Verifikationsstatus

- 24 nye unit-tests grønne + arkitektur-ratchet 2/2 + begge route-auth-tests grønne (kørt i sandkasse mod midlertidig sqlite).
- Ikke kørt: fuld integrations-suite mod prod-lignende Postgres, BT-PAN-hardware, WebAuthn-online. **➡️ Codex bedes køre fuld suite + live-verificere §3.**
