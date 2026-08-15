# TimeLapse Pro — Update-flow gennemgang (kode + tests + brugervenlighed)

**Dato:** 2026-08-15 · **Reviewer:** Kimi · **Commit:** `main @ c2b8c36`
**Scope:** Hele update-flowet — edge-agentens poll/download/verify/install/rollback, headend-update-governance (oprettelse, signering, godkendelse, rollout, promote), headend-selvopdatering (brew), UI og operatørdokumentation.

---

## 1. Samlet konklusion

**Update-flowet er et af de stærkeste områder i kodebasen.** Arkitekturen er pull-baseret med fail-closed artefakt-tillid, og den er dokumenteret e2e-testet på rigtig hardware (Update_Flow_v10.md, QA-kørsel 2026-06-21 på `TL-C87FF9587CA0`). Flowet er overskueligt i UI'en med danske trin-for-trin-visualiseringer.

**Det virker** — med tre forbehold, som alle er kendte og afgrænsede:

| # | Forbehold | Alvor |
|---|---|---|
| 1 | Artefakt-signering kan falde tilbage til hash-binding (`system-hash`) — nu formaliseret som accepteret trust path (`main.py:6924-6938`). Hele kædens styrke afhænger af GPG-signeringen. | **Major** (= F-005 fra hovedreviewet) |
| 2 | Tvungen rollback (`_run_rollback`, `edge/agent.py:2093`) bruger stadig `bash -c "cp -r prev/* ..."` — ikke atomisk, springer dotfiles over, tjekker ikke returncode. Den automatiske fejl-rollback ved install er derimod omskrevet til `shutil` (godt). | Minor→Major afhængigt af brug |
| 3 | Hvis edgens "deployed"-rapport til headend fejler netværksmæssigt, forbliver update `approved`, og edge gen-installerer ved næste poll (hver ~5 min) indtil rapporten går igennem. Ikke farligt, men støjende og ikke idempotent-beskyttet. | Minor |

---

## 2. Det tracede flow (verificeret i kode)

### 2.1 Edge-side (`edge/agent.py`)

```
poll (5 min, konfigurerbar)
  → GET /api/updates/policy/{device_id}          (device-token auth)
  → verify_update_artifact()                     (fail-closed: schema, sha256, trusted signer, signatur)
  → rapportér: backing_up → downloading → verifying → installing
  → pre-update backup uploades til Headend FØR install
  → per-fil SHA-256-verifikation + path-sikkerhed (ingen absolute/parent-paths)
  → staging i /tmp → backup til prev/ → install
  → systemd-enheder håndteres særskilt (daemon-reload, enable, restart, is-active-verifikation)
  → atomisk release-receipt (fsync + readback-mismatch-check)
  → rapportér deployed / rolled_back / blocked
  → genstart af agent
```

**OS-updates** (`_run_artifact_os_update`) er ekstra hærdede:
- Kun offline Headend-bundles (`distribution_model`-tvang)
- Forbudte kommandoer scannes i alle bundle-scripts: `apt update/upgrade`, `curl/wget/scp/rsync`, `git clone/pull/fetch`, `pip install`
- Alle apt-kommandoer skal have `--no-download`
- argv-allowlist med tilladte exec-rødder
- Kørsel via `systemd-run --collect` med timeout

**Legacy git-update** er deaktiveret som standard og kræver både `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1` og lab/dev-miljø. Edge afviser aktivt og beder headend rydde flaget. Godt.

### 2.2 Headend-side (`headend/main.py`)

- **Oprettelse:** Edge rapporterer kun app-update-hints (`/api/updates/available`); OS-updates reconciles fra CMDB mod headend-ejet katalog — edge kan ikke selv erklære OS-mangler.
- **Artifact-katalog:** signerede artifacts med manifest, sha256, signer-fingerprint, SBOM.
- **Change tickets + signerede approvals:** `_build_change_ticket` + `_sign_payload` (GPG), `ChangeApproval`-rækker med signatur og payload-hash.
- **Godkendelse** (`/api/updates/{id}/approve`): kræver admin/super_admin (MFA håndhæves via `require_role` når brugeren har MFA-krav), scope-validering, `_assert_update_has_required_artifact` — kode-updates kan ikke godkendes uden signeret artifact.
- **Auto-godkendelse** pr. policy: `os_security=auto`, features `manual` som default; `staging_required` og `customer_acceptance_required` gates understøttes.
- **Fail-closed tilbageholdelse:** godkendt update uden artifact blokeres aktivt i policy-svaret med besked i description (`main.py:10416-10426`). Stærkt.
- **Rapport** (`/api/updates/report`): device-token + payload-device-match (403 ved mismatch), per-target `UpdateTarget`-rækker, multi-target rollup med eksplicit `db.flush()` (HLTH-008-regressionen er rettet og test-dækket).
- **Promote** (lab/test → staging → production): kræver deployed-evidens på kilden; production-kandidat starter som `pending` og kræver ny godkendelse. Korrekt governance.
- **Force-rollback** endpoint findes og er UI-eksponeret.

### 2.3 Headend-selvopdatering

- Homebrew-allowlist (certbot, ffmpeg, postgresql@17 m.fl.) med preflight/postflight-checks, backup, rollback-plist og global lock. Kode-deploy sker via CI (`deploy-macmini`) — her gælder fortsat F-003 (GPG-tjekket verificerer seneste tag, ikke deployet SHA).

### 2.4 UI (`UpdatesPage.tsx`, 1.867 linjer)

- Danske labels og filter-faner (Afventer/Godkendt/Blokeret/Deployet/Afvist/Erstattet/Rullet tilbage)
- Sticky "Aktivt opdateringsflow"-banner med auto-polling mens flow kører
- Trin-for-trin-visualisering pr. flow-type, fx Edge pull-flow: *Godkendt → Afventer Edge poll → Artifact trust check → Pre-update backup → Install/rollback* — med `waiting_for`-tilstande pr. target
- Blokerede OS-updates forklarer inline at der mangler et lab-bygget offline bundle, og hvad næste trin er
- Headend-deploy viser preflight/postflight og stdout/stderr-tails ved fejl
- Device-matrix og flow-status pr. target med `last_seen`-alder

**Usability-gap:** update-policy (auto/manual, staging_required, customer_acceptance) kan ikke redigeres i UI — kun via config-override-JSON. Default er fornuftig (security auto, features manual), men en dedikeret policy-editor ville gøre flowet komplet for ikke-teknikere.

### 2.5 Operatørdokumentation

`Update_Flow_v10.md` er i topklasse: konsolideret, med e2e-evidens, status-tabel med "hvad gør operatøren"-kolonne og fejlsøgningssektioner ("Når en række siger Afventer Edge", "Når en update mangler artifact", "Når man trykker Promover til prod" — inkl. forklaring af at promotion ≠ installation). Det er præcis den dokumentation der gør flowet overskueligt i praksis.

---

## 3. Tests kørt i dette review

| Suite | Resultat |
|---|---|
| `headend/tests/test_update_lifecycle.py` + `test_report_update_rollup.py` | **13/13 passed** (inkl. flush-regression og mid-rollout-device-fjernelse) |
| `tests/test_os_offline_update.py` + `test_update_supersession.py` + `headend/tests/test_change_ticket_sbom.py` | **22 passed, 4 skipped** (skips: kræver live headend) |
| E2E på rigtig hardware (2026-06-21, dokumenteret) | Bestået — app-artifact end-to-end; OS-flow ikke e2e-kørt (0 tilgængelige OS-updates på aktiv edge på daværende tidspunkt) |

---

## 4. Fund og anbefalinger (update-flow specifikt)

| ID | Fund | Severity | Anbefaling |
|---|---|---|---|
| UF-01 | Signerings-fallback `system-hash` formaliseret som accepteret trust path | **Major** | GPG obligatorisk i prod; system-hash kun lab-markeret. (Samme som F-005 — bør lukkes som ét punkt.) |
| UF-02 | Tvungen rollback via `bash -c cp -r prev/*` — ikke atomisk, springer dotfiles over, rc ignoreres | Minor | Omskriv til shutil-mønsteret fra install-fejl-path'en (som allerede er lavet rigtigt) + receipt-verifikation før service-start |
| UF-03 | Fejlet "deployed"-rapport ⇒ gen-install ved næste poll (manglende idempotens-guard) | Minor | Spring install over hvis lokal receipt allerede matcher artifact_id, og rapportér igen i stedet |
| UF-04 | OS-update-rollback: edge rapporterer `blocked` ved OS-fejl (ingen rollback mulig for apt) — semantikken er ikke dokumenteret tydeligt i UI | Observation | Afklar i UI/manual at OS-fejl = afbrudt-før-install, ikke rullet-tilbage |
| UF-05 | Update-policy (auto/manual/staging/kundeaccept) ikke redigerbar i UI — kun JSON config-overrides | Observation | Lille policy-editor på UpdatesPage eller GlobalConfigPage |
| UF-06 | Ved blokeret OS-update står CI/test-e2e-dækning af *rigtig* OS-installation stadig ude (aldrig kørt e2e på hardware) | Observation | Kør én reel OS-bundle-install på test-edge før RC1 (WP-9 canonical test dækker dette) |

## 5. Svar på det stillede spørgsmål

**Virker det?** Ja — dokumenteret e2e på hardware for app-updates, 35 grønne tests kørt i dette review, og koden viser gennemført defense-in-depth (signering, backup-før-install, per-fil-hash, atomiske receipts, forbidden-command-scanning).

**Er det overskueligt og brugervenligt?** Ja — UI'en viser flowet trin-for-trin på dansk med "hvad venter vi på"-tilstande, og operatørmanualen er fremragende. Eneste reelle usability-hul er at update-policy kun kan ændres via JSON-config (UF-05).

**Hvad mangler før det er produktions-sikkert?** UF-01 (GPG fail-closed i prod) er det eneste reelt blokerende punkt — resten er polish. Plus de generelle go-live-gates fra hovedreviewet.
