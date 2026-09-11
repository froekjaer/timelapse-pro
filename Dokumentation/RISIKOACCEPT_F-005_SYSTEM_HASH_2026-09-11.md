# Formel risikoaccept — F-005: `system-hash` fallback for artifact-signatur

**Dato:** 2026-09-11
**Beslutningstræffer (ejer):** Peter Frøkjær — produkt-/driftsejer
**Registreret af:** Kimi (AI-assistent)
**GRC:** `RISK-ARTIFACT-SYSTEM-HASH-FALLBACK` (status: **accepted**) · `FIND-ARTIFACT-SYSTEM-HASH-FALLBACK-F005` (status: **closed** — dispositioneret via denne accept)
**Kilder:** `kimi-2026-08-15.md` (F-005) · `kimi-2026-08-15-AFSTEMNING-2026-09-11.md` · `kimi-grc-afventer-2026-08-23.md` pkt 3

---

## 1. Hvad accepteres

Headend accepterer artifact-signatur via **sha256 hash-binding** (`system-hash`) som signaturgrundlag, når der ikke er konfigureret en GPG-signeringsnøgle (verificeret i `headend/main.py:5997, 6019, 6283-6288` på `main @ 76cb2cd8`).

**Risikoen:** En angriber med skriveadgang til artifact-lageret kan genberegne hash-værdier og dermed fremstille et tilsyneladende "signeret" artifact uden at kende nogen hemmelig nøgle. Hash-binding beviser integritet fra et kendt udgangspunkt, men **ikke ophav/autenticitet**.

## 2. Acceptens omfang og begrænsninger

- Gælder **kun** drift uden konfigureret GPG-signeringsnøgle.
- Gælder **ikke** som endeligt designtilstand: målet forbliver GPG-signering af alle artifacts.
- Accepten dækker den nuværende **pre-produktionsfase** (test/udvikling). Systemet er *ikke* godkendt til ubegrænset internet-/kundeproduktion (jf. `MASTER_REVIEW_CLOSURE_2026-08-15.md` §1), og denne accept ændrer ikke det.

## 3. Begrundelse

1. **Kompenserende kontrol på Edge:** Edge afviser hash-only artifacts ved installation (PR #41 — reel OpenPGP-verifikation med sign/tamper-tests). Fallback'en kan derfor ikke alene bære et artifact helt ud på enhederne.
2. **Afbødende arkitektur:** Branch protection på main, PR-proces, artifact-lagerets adgangskontrol og update-audit-log begrænser angrebsfladen.
3. **Forretningsmæssig kontekst:** Systemet er et test-/udviklingssystem uden kundedata i produktion; RC1-gates kræver allerede signeret offline OS-bundle E2E (GRC-test `UI-UPD-06`, status `not_run`) før release-godkendelse.
4. **Alternativet** (fjern fallback'en nu) ville blokere update-flowet i det nuværende miljø, hvor GPG-signeringsnøglen endnu ikke er etableret — uden tilsvarende sikkerhedsgevinst i pre-produktion.

## 4. Kompenserende kontroller (skal forblive aktive)

| Kontrol | Bevis |
|---|---|
| Edge afviser hash-only artifacts (fail-closed OpenPGP-verifikation) | PR #41, tests i `tests/` (sign/tamper) |
| Ingen ubegrænset produktionsrelease | `MASTER_REVIEW_CLOSURE_2026-08-15.md` §1 |
| Signeret offline OS-bundle E2E som RC1-gate | GRC `UI-UPD-06` (P0, `not_run`) |
| Update-audit-log på headend | Drift |

## 5. Genbesøgskriterier — accepten udløber når ÉT af disse indtræffer

1. **RC1/release-godkendelse** — senest her skal GPG-signering være etableret, eller accepten aktivt fornyet med ny begrundelse.
2. GPG-signeringsnøgle tages i brug → fallback'en bør fjernes (opgave oprettes ved lejlighed).
3. Ændret trusselsbillede (fx ekstern eksponering af headend/artifact-lager).
4. **Senest 2027-03-11** (6 måneder) — obligatorisk genreview.

## 6. Residual risiko efter accept

**Moderate → acceptabel i pre-produktion.** Sandsynligheden for udnyttelse er lav (kræver skriveadgang til artifact-lager + passerer Edge-verifikation), konsekvensen er høj men afbødet af Edge-side fail-closed verifikation og fraværet af kundeproduktion.

---

**Besluttet af:** Peter Frøkjær — 2026-09-11 (mundtligt i arbejdssession: "F-005. Accepter formel risikoaccept")
