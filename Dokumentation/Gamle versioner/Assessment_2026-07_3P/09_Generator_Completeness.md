# 09 — Generator-completeness: "virker det bare?"

Peters mål: headend- og edge-generatorerne skal have ALT med, så det bare virker. Denne gennemgang er kode-forankret (statisk), ikke en faktisk kørsel af generatorerne (kræver Docker + Mac-target). Konklusion først: **generatorerne er velbyggede og signeringssikre, men headend-generatoren er efter eget udsagn IKKE komplet — SFTP-ingress er et manuelt trin. Det betyder "virker næsten", ikke "virker bare".**

## Headend-generator (`headend/api/headend_generator_api.py`, 542 l + `deploy/install/headend_generator.sh`)

**Med (godt):** signeret release-katalog + validering (`_signed_release_catalog`, `_validate_release_selection`), platform-admin-krav på alle endpoints (`_require_platform_admin`), engangs-bootstrap-token med udløb, GPG-verificeret release-hentning, preflight der nægter ved portkonflikt (CrushFTP 21/22/80/443), DNS-01-cert-vej, DB-defaults-seeding.

**Mangler / "virker ikke bare" (fra koden selv):**

| ID | Gap | Evidens |
|---|---|---|
> **Codex-verifikation 2026-07-31:** GEN-02 er bekræftet lukket — `sftp_port` bruger DB-setting med 22222-fallback, og generatorens artefaktmappe/repo-URL er UI-redigerbare settings (`headend_image_artifact_dir`, `headend_repo_url`). GEN-01 (SFTP-ingress som automatiseret trin) og GEN-10 (`_headend_api_url()`s `127.0.0.1:8000`-fallback) forbliver åbne. Konklusionen nedenfor står.

| GEN-01 | **SFTP-ingress (22222) er ikke et generator-trin.** Uden det kan en ny headend ikke modtage edge-uploads — kernefunktionen. Kaldet returnerer eksplicit "Fase 2b (SFTP 22222) er et manuelt trin". | `headend_generator_api.py:388`, README-render §3 |
| GEN-03 | Reverse-tunnel-ingress-port på staging/prod udefineret (edge-fallback = 22) | handover; kræver Peter-beslutning |
| GEN-04 | Tunnel-port-allokator (2201++) kolliderer med reserveret 2222 ved enhed nr. 22 | handover |
| GEN-07/08 | `admin/changeme`-vindue på offentlig 8443 (manual foreskriver login FØR eksponering); enroll mod 127.0.0.1 fejler på cert (brug domæne) | handover |
| GEN-11 | Uafklaret hvor prod-edge-images bygges (Docker på prod vs. promotion fra R&D) | handover; Peter-beslutning |

**➡️ For at "det bare virker":** gør Fase 2b (SFTP-socket + sshd-hardening + per-site RBAC-render + `sftp_port=22222`) til et **scriptet trin i generatoren** (mekanikken findes i `deploy/ssh/` — den skal bare wires ind), og luk GEN-03/04/07/08 som del af samme fase. Indtil da bør README'ens "manuelt trin"-boks stå meget tydeligt, så en installation ikke tror den er færdig.

## Edge-generator (`headend/tools/build_edge_disk_image.py`, 591 l + Dockerfiles)

**Med (stærkt):** git-provenance-guard der nægter build ved uncommittede edge-inputs (`_git_provenance`, linje 225-242 — rigtig god secure-by-design), manifest-signering (`_sign_manifest`), SHA256 på artefakter, enrollment via kortlivet bootstrap-token, WiFi-image-injektion, target-baseret Dockerfile-valg (armhf/arm64).

**Verificér før udsendelse af rigtig edge:**

| ID | Punkt | Hvorfor |
|---|---|---|
| E-01 | Per-device TOTP/identitet skal genereres i build/enroll — ikke arve TPA-00 factory-default | Kritisk: en edge bygget i dag kan ende med den kendte secret |
| E-02 | Bekræft at bootstrap-token-udløb er kort nok, og at enrollment fejler fail-closed ved udløbet token | Undgå langtlevende enrollment-credential i felten |
| E-03 | Nikon Z30-profil/fokus/video (kendt åben i go-live-listen) medtaget i image-config | Ellers virker kameraet ikke "bare" |
| E-04 | NPU/edge-QA-model med i image for target-hardware (Orange Pi 4 Pro) | Payload-funktion |
| E-05 | Reverse-tunnel-config matcher headend-generatorens tunnel-portbeslutning (GEN-03) | Ellers kan edge ikke nå hjem |

## Samlet svar til Peter

Edge-generatoren er tæt på "bare virker" (og har forbilledlig build-provenance), men arver TPA-00-secret-problemet (E-01) — det SKAL lukkes før en rigtig edge går ud. Headend-generatoren "virker næsten": den mangler SFTP-ingress som automatiseret trin (GEN-01), hvilket er selve modtagersiden af edge-uploads. Anbefaling: luk TPA-00 + GEN-01 (+ Peter-beslutningerne GEN-03/11) FØR første staging-install; så er begge generatorer reelt "sæt-i-gang-og-det-kører".
