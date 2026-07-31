# 07 — Prioriteret Handlingsplan

Rækkefølge mod: (A) staging-test, (B) headend på rigtig prod-server, (C) ny edge i den virkelige verden, (D) modulært framework v1. Hvert punkt: fund-reference + ejer-felt (tomt = Peter tildeler). Kan importeres i GRC.

## Gate 0 — MÅ lukkes før nogen Internet-eksponering (Kritisk/blocker)

1. **TPA-00** — Fjern default TOTP-secret; per-device secret; fail-closed uden secret; CI-scan for kendte demo-secrets. *(CRA/62443 blocker)*
2. **R09 / P0-03** — Kør og evidensér restore-drill (headend-DB + billedstore). *(ISO 27001 A.8.13, go-live-blocker)*
3. **Branch protection på `main`** — krav om grøn CI (fuld dependency-liste) før push/merge. *(Bemærk: TPA-01 er nedgraderet til Lav — route-auth-gaten er IKKE rød i CI, jf. Codex-evidens; testens KeyError er rettet på `feature/tpa-00-commissioner-auth`. Branch protection er stadig den reelle beskyttelse.)*

## Gate 1 — Før staging-test (Høj)

4. **GEN-01** — Gør SFTP-ingress (22222) til et scriptet trin i headend-generatoren (dok. 09). Uden det kan staging-headend ikke modtage uploads.
5. **E-01/E-02** — Sikr at edge-image genererer per-device-identitet og fail-closed enrollment (dok. 09).
6. **TPA-02** — Per-device nøglepar (Ed25519) ved provisionering, public key i CMDB. *(før ny edge)*
7. **GEN-03 / GEN-11** — Peter-beslutninger: tunnel-port + hvor prod-edge-images bygges.
8. **GOV-01** — Vedtag RATCHET-EXCEPTION-regel (dok. 08).

## Gate 2 — Under staging / før prod-kunde (Mellem)

9. **TPA-11 + TPA-12** — Baggrundsjob-registry (health/restart) + trådpulje for exif-enrich. Superviser især retention (GDPR).
10. **TPA-04** — Whitelist for dynamiske SQL-identifiers.
11. **TPA-03 / TPA-15** — Én `config_fingerprint()` (SHA-256) + én settings-adapter; fjern duplikation.
12. **H-01..H-07 + §3.2** — Flyt hardkodede stier/porte og drifts-env-vars til DB-settings/UI; CI-sweep-gate (dok. 03).
13. **TPA-20..22** — UI: gruppér menu i 4 sektioner, ét sprog + i18n-nøgler, sitemap-doc (route→page→menu→rolle).
14. **GDPR** — DPA-skabeloner + controller/processor-rolleafklaring + aktivt AI-register (dok. 05). *(jurist-input)*

## Gate 3 — Modulært framework v1 (parallelt, additivt — dok. 06)

15. **F1** — Land `contracts/` + 4 arkitektur-gates som tests-only (næste sikre skridt).
16. **F2** — Auth/RBAC-udtræk fra `main.py`; ratchet → nedtælling.
17. **F3–F6** — Job-registry, dataplan-wrapper, edge agent/payload-split (SPIKE på Orange Pi), andet payload som anti-koblingsbevis.

## Lav / hygiejne (løbende)

18. TPA-05/06 (SameSite-Strict/CSRF, replay-test), TPA-13 (cache-TTL), TPA-14 (lifespan-migration), TPA-07 (SIEM-heuristik-mærkning), docs-oprydning (ISSUES.md, `.bak`, `docs/`-split), Node20/checkout-bump.

## Anbefalet sekvens i én linje

Luk Gate 0 (TPA-00, R09, TPA-01) → Gate 1 (generator-SFTP + per-device edge) → **installér staging** → soak-/restore-/upload-test → luk Gate 2 → **prod-headend + første rigtige edge** → kør framework v1 (Gate 3) additivt hele vejen. Ingen af framework-faserne blokerer staging; Gate 0 blokerer alt.
