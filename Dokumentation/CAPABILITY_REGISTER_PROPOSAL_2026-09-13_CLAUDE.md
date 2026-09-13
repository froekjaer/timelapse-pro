# Capability Register — forslag til struktur og governance-integration

**Forfatter:** Claude Sonnet 5, 2026-09-13
**Status:** FORSLAG — ikke implementeret, kræver Peters beslutning før
skemaændring/kode. Denne fil beskriver anbefalingen; intet i dette dokument
er udført mod databasen.

## Baggrund — hvorfor dette forslag nu

To uafhængige eksempler fra i dag viser samme underliggende procesfejl:

1. **Terminal-capability:** Direct-Edge recovery-terminalen fik en dårlig
   renderer (PR #198, 2026-09-08), selvom et rigtigt, allerede live-testet
   xterm.js-baseret alternativ (`d67ca26d`, 2026-08-06, forfattet af Peter)
   allerede eksisterede på et andet, aldrig-merged spor. R04-branch-triage
   analyserede commits/filer/tests grundigt, men vurderede aldrig den
   *faktiske brugeroplevelse* op mod et kendt godt referencepunkt.
2. **Multi-IP session-robusthed:** Samme `d67ca26d`-commit implementerede
   allerede den nøjagtige multi-IP-session-model (`sess["ips"]` som set) som
   #238 (2026-09-13) genopfandt fra bunden — fordi det oprindelige spor var
   tabt af syne, ikke fordi løsningen var forkert eller ukendt.

Fælles rodårsag: **implementation-/patch-equivalence blev forvekslet med
capability-equivalence.** Tests var grønne, kode-diff'et var forstået — men
ingen af analyserne stillede spørgsmålet "leverer den nuværende
implementering samme *resultat* som et kendt, allerede fungerende
referencepunkt?"

## Search before create — hvad findes allerede

Repoet har allerede et modent, Postgres-baseret GRC-register
(`headend/migrations/v23_grc_register.sql` til `v25_grc_comments.sql`,
API i `headend/api/grc_register_api.py`, tests i
`tests/test_grc_register_contract.py`/`test_grc_requirement_import_contract.py`):

- `grc_items` — typet register (`item_type IN ('requirement','control','risk',
  'test','finding','action')`), med `external_id`, `title`, `description`,
  `status`, `owner`, `attributes JSONB` (fri struktureret metadata),
  `version`, fuld created/updated-audit.
- `grc_links` — navngivne relationer mellem to `grc_items` (fri
  `relationship`-streng, fx allerede brugt til at forbinde krav↔kontrol↔test).
- `grc_test_runs` — testresultater bundet til et test-item, med
  `environment` (kan allerede rumme fx `lab`/`physical_edge`), `result`,
  tidsstempler, `executed_by`.
- `grc_evidence` — provenance/bevis bundet til et item eller en test-run:
  `evidence_type`, `uri`, `sha256`, `content JSONB`, `retention_class`.
- `grc_documents`/`grc_document_revisions`/`grc_document_item_links` —
  genererer versionerede, godkendte dokumenter FRA en mængde `grc_items`
  (indeholder allerede `content_sha256`, `approved_by/at`, `change_summary`).

Dette dækker i praksis alle de felter Peter efterspurgte til et Capability
Register: ID/navn, intent/beskrivelse, status/lifecycle, owner,
struktureret metadata (required behaviour, dependencies, failure
assumptions, security/recovery constraints — alt sammen i `attributes`),
verifikation/tests (`grc_test_runs`), fysisk/runtime-verifikation (samme,
med `environment='physical_edge'`), provenance/beslutning/ADR-reference
(`grc_evidence`, `evidence_type='adr'` eller `'commit'`), og
generering af det faktiske menneskelæsbare register-dokument
(`grc_documents`).

**Anbefaling: udvid det eksisterende GRC-register med `item_type =
'capability'`, i stedet for et nyt parallelt Markdown-dokument.**
`PAKKE_SPOR_REGISTER.md` og `HANDOVER_LOG.md` løser et andet problem
(branch-/pakke-sporing, kronologisk driftslog) og bør forblive som de er;
ADR'er dokumenterer enkeltstående arkitekturbeslutninger, ikke løbende
capability-status. Et capability-item i GRC-registeret kan **linke** til
alle tre via `grc_links`/`grc_evidence` uden at duplikere dem.

## Foreslået skemaændring (minimal)

1. Ny migration `v26_grc_capability_register.sql`:
   ```sql
   ALTER TABLE grc_items DROP CONSTRAINT grc_items_item_type_check;
   ALTER TABLE grc_items ADD CONSTRAINT grc_items_item_type_check
     CHECK (item_type IN ('requirement','control','risk','test','finding','action','capability'));
   ```
2. `headend/api/grc_register_api.py`: tilføj `"capability"` til `ITEM_TYPES`.
3. Ingen ændring nødvendig i `grc_links`/`grc_test_runs`/`grc_evidence` —
   `relationship`/`evidence_type` er allerede frie strenge. Foreslåede,
   dokumenterede konventioner (ikke skema-håndhævet):
   - `relationship`: `implements`, `verifies`, `reference_implementation_for`,
     `superseded_by`, `documented_by_adr`.
   - `evidence_type`: `commit`, `pr`, `adr`, `physical_test`, `known_good_reference`.

## Eksempel — "Local Edge Recovery Terminal" som capability-item

```json
{
  "item_type": "capability",
  "external_id": "CAP-EDGE-RECOVERY-TERMINAL",
  "title": "Local Edge Recovery Terminal",
  "status": "active_with_known_rests",
  "owner": "Peter",
  "description": "Peter/autoriseret tekniker kan få en fuldt anvendelig interaktiv root-shell direkte på en Edge til fejlsøgning og recovery.",
  "attributes": {
    "required_behaviour": [
      "usable_terminal_emulation", "ctrl_c_job_control", "tab_completion",
      "command_history", "cursor_navigation_keys", "resize",
      "reconnect_session_robustness", "logout_expiry_cleanup",
      "local_first_audit", "works_without_headend", "works_without_internet"
    ],
    "current_implementation": {
      "component": "edge/scripts/totp-service.py: mgmt_cli_bash_ws + _cli_page",
      "commit": "<denne PR>"
    },
    "known_good_reference": {
      "commit": "d67ca26d", "date": "2026-08-06", "author": "Peter",
      "note": "Live-tested on TL-C87FF9587CA0, never merged to main"
    },
    "dependencies": ["TOTP session", "iptables whitelist", "BT-PAN/WiFi/Ethernet reachability"],
    "failure_assumptions": ["must keep working with Headend unreachable", "must keep working with no internet"],
    "security_constraints": ["ADR-004: general-purpose root shell accepted for dev/stabilization phase"],
    "known_rests": ["physical acceptance test pending (see test plan)"]
  }
}
```
Links: `verifies` → et `test`-item pr. automatisk kontrakt-test;
`documented_by_adr` → `ADR-004`; `reference_implementation_for` →
et `grc_evidence`-bevis der peger på commit `d67ca26d`.

## Foreslået governance-regel: "Capability equivalence before disposition"

**Forslag til tilføjelse** (§16, additivt — ikke en ændring af det allerede
accepterede §14) til `Dokumentation/SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`:

> En historisk branch/change må ikke klassificeres `absorbed` eller
> `superseded` alene ud fra commits, filer, funktioner, tests eller
> patch-ækvivalens, når den påvirker en registreret user-, operational-,
> recovery-, security- eller anden consequential capability. Den aktuelle
> implementering skal desuden sammenholdes med: (1) capability-intent,
> (2) required behaviour/invariants, (3) et evt. `known_good_reference` i
> Capability Registeret, (4) relevant runtime-/fysisk evidens. Omvendt skal
> en ændring til en registreret capability, før merge, kontrolleres mod dens
> invarianter, så en forbedring ét sted ikke stiltiende degraderer samme
> capability et andet sted (jf. multi-IP-eksemplet ovenfor).

Dette udvider — erstatter ikke — §14's eksisterende pakke-/spor-disciplin.
En branch kan stadig korrekt klassificeres `absorbed` på pakke-niveau, mens
den samtidig flager en `known_good_reference`, der skal tjekkes op mod
Capability Registeret før endelig disposition.

## Omfang — hold registeret kompakt

Peter bad eksplicit om at undgå hundredvis af trivielle UI-features. Forslag
til initial population (consequential capabilities, ikke udtømmende):

- `CAP-EDGE-RECOVERY-TERMINAL` (denne sag)
- `CAP-EDGE-RECOVERY-BREAKGLASS-SSH` (allerede delvist dækket af eksisterende
  break-glass audit-arbejde)
- `CAP-DEPLOYMENT-UPDATE-DELIVERY` (OS/Python offline-bundle-pipeline,
  jf. #297/#292/#271-arbejdet)
- `CAP-CAPTURE-EVIDENCE-INTEGRITY` (capture→PostgreSQL-idempotens, sha256-match)
- `CAP-SECURITY-ACCESS-CONTROL` (TOTP/mTLS/session-model samlet)
- `CAP-HEADEND-EDGE-SYNC` (offline-first sync/audit-forwarding)

Hver af disse kan populeres gradvist, med `known_good_reference` udfyldt kun
hvor der faktisk findes en tidligere, verificerbar god implementering (som i
terminal-sagen) — ikke opfundet retroaktivt.

## Hvad dette forslag IKKE gør

Ingen migration er kørt. Ingen kode i `headend/api/grc_register_api.py` er
ændret. Ingen §16 er tilføjet til SAMARBEJDSMODEL-dokumentet. Dette er et
beslutningsoplæg til Peter, ikke en implementeret ændring.
