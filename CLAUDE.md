# CLAUDE.md — Claude Code guide to TimeLapse Pro

TimeLapse Pro is a Danish timelapse-camera SaaS: edge agents on camera nodes
(Orange Pi + Nikon) upload images to a central headend (FastAPI + PostgreSQL),
which handles CMDB, AI tagging, customer/user administration, RBAC, OTA
updates, and a React-based admin UI. **Status: LAB/pre-production** — not yet
cleared for full internet exposure (see `Dokumentation/GO_LIVE_CHECKLIST_v10.md`
and `Dokumentation/RISK_ASSESSMENT_v10.md`).

This file has two parts: **Part 1** is a mandatory operational procedure —
read and apply it before any substantive work. **Part 2** is reference
material on the codebase itself (structure, workflows, conventions).

---

## Part 1 — Mission Framework operational loader (mandatory)

TimeLapse Pro is a Mission Framework reference mission
(`github.com/froekjaer/mission-framework`, Apache-2.0). Before substantive
work in this repository:

1. Read `Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md`
   in full — a vendored, verbatim copy of the canonical procedure. Apply it:
   classify the task, verify identifiers, recover existing context, check
   architectural consistency, search before creating, assess dependencies,
   execute, then verify the outcome.
2. This repo's authoritative sources — check these before assuming or
   reconstructing from memory:
   - `Dokumentation/HANDOVER_LOG.md` — session-to-session handover, newest
     entries at the top of `## Log`.
   - The GRC register (`grc_items` table in production Postgres —
     `psql "$DATABASE_URL" -c "SELECT external_id, item_type, title, status
     FROM grc_items WHERE ..."`) — findings, actions, risks, controls with a
     status field. Check for an existing open item before treating something
     as new. This is the status source of truth, not the markdown docs under
     `Dokumentation/` (those are runbooks, closures narratives, and migration
     sources — see `Dokumentation/00_START_HER.md` §1).
   - `Dokumentation/` — topic docs (`SEC-NNN_*.md` security closures, feature
     docs, risk assessments). Start at `Dokumentation/00_START_HER.md`, the
     master index.
   - `tests/architecture_baseline.json` + `tests/test_architecture_ratchet.py`
     — a hard, checked-in ratchet on `headend/main.py` size and route count.
     Never raise the baseline to make a change fit; shrink or extract instead.
   - Open PRs and recent commits (`git log`, GitHub PR list) — Claude, Codex,
     ChatGPT, Kimi and Gemini all work on this repo, sometimes concurrently.
     Do not assume you are the only active session.
3. **Never operate from memory when one of the above is available and
   unchecked.** This repo has repeatedly rebuilt, half-built, or forgotten the
   same capability across sessions (see `HANDOVER_LOG.md`, 2026-08-16/17, for
   concrete, named examples: a security finding closed three separate times
   without its replacement ever being verified working; a break-glass account
   built without its key-delivery mechanism; a manifest that silently dropped
   required files). Search before you build — the thing you're about to
   create may already exist, half-finished, somewhere in this repo's history
   or open PRs.
4. After a change: verify the outcome. Read back what you wrote. Run the
   relevant tests. For anything touching a security or trust boundary,
   identify what depended on the thing you changed and confirm it still
   works — not just that your change itself compiles.
5. For substantive work, give a compact preamble status (task classified /
   sources checked / existing context recovered / dependencies assessed /
   ready to execute). Skip this for routine conversation that doesn't touch
   canonical state.

Framework Findings (ambiguity, contradiction, or gap discovered in the
framework itself while working here) get recorded and, where material,
returned upstream per `docs/FRAMEWORK_FINDINGS.md` in the mission-framework
repo.

Other AI agents working on this repo read their own loader files with the
same intent: `AGENTS.md` (Codex CLI and Kimi Code), `GEMINI.md` (Gemini CLI),
`Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md` (ChatGPT, pasted manually —
no auto-load convention exists for it). Keep this file consistent with them
if you update the shared procedure.

---

## Part 2 — Codebase reference

### 2.1 Repository structure

| Path | Contents |
|---|---|
| `headend/` | FastAPI backend (Python). API, CMDB, AI tagging, updates, auth/RBAC. PostgreSQL in production; can run against SQLite locally via `DATABASE_URL` for dev/test. |
| `headend/main.py` | Legacy monolith entrypoint — **under a hard architecture ratchet** (§2.3). Historically where most routes lived; new work must not grow it. |
| `headend/api/` | Domain `APIRouter` modules for newer endpoints (capture access, customer risk, edge lifecycle, edge local PKI, GRC register, headend generator, service access, site-look config, SSH tunnel terminal, storage, trust service). |
| `headend/services/` | Business-logic modules kept separate from route handlers (artifact trust, bootstrap security, capture deletion, CMDB baseline drift, edge lifecycle/local PKI, exposure ramping, FAIR risk, local service security, OS builder security, path security, site-look config, SSH host trust migration, technician auth security, timelapse render, update authority/supersession). |
| `headend/database.py` | SQLAlchemy 2.0 models + engine setup. Has a fail-closed guard: pytest refuses to run against the operational `timelapse_db` unless `TIMELAPSE_ALLOW_PYTEST_PRODUCTION_DB=I_UNDERSTAND_DATA_WILL_BE_DESTROYED` is set explicitly. |
| `headend/tests/` | Headend-specific contract tests (co-located with the code they test). |
| `headend/ai/`, `headend/config/`, `headend/deploy/`, `headend/migrations/`, `headend/tools/`, `headend/trust/` | AI-tagging integration, runtime config, deploy helpers, SQL migrations, one-off/admin tooling, trust/PKI helpers. |
| `edge/` | Edge agent (Python) for camera nodes — capture, upload, HAL, CMDB reporting, HMAC signing, self-update. Pure Python; no Node dependency. Subdirs: `ai/`, `camera/`, `capture/`, `cmdb/`, `config/`, `diagnostics/`, `hal/`, `npu_viplite/`, `scripts/`, `tools/`, `training/`, `tunnel/`, `update/`, `upload/`, `utils/`. |
| `edge/agent.py` | Edge agent main loop / heartbeat entrypoint. |
| `timelapse-ui/` | Admin/customer UI — React 19 + TypeScript + Vite + Tailwind v4. |
| `node-agent/` | Lightweight monitoring/health agent (collectors for inventory + security) for node/service observability. |
| `website/`, `www/` | Static public info site. |
| `deploy/`, `deployment/` | LaunchAgent/LaunchDaemon manifests and deployment scripts for Mac mini (headend) and Orange Pi (edge). |
| `tests/` | Repo-level integration/API/edge-QA tests (pytest) — the primary CI test suite. |
| `Dokumentation/` | Authoritative documentation: SABSA/ISO 27001/IEC 62443/CRA/GDPR-relevant material, ADRs, handover log, GRC-adjacent runbooks. See §2.6. |
| `sprint_c/`, `tools/`, `z.ai/`, `docs/` | Older sprint artifacts, root-level scripts, a z.ai-era working area, and ~20 code-adjacent developer notes whose permanent location is still undecided (check this folder when touching drift-mode, site-look, or edge architecture features it documents). |
| `PRIORITIZED_BACKLOG.md` | Actively used priority backlog — sessions use this in practice for "what's next." |
| `ISSUES.md` | **Stale** (last updated 2026-06-14); lists findings as open that are closed. Use the GRC register instead. |

### 2.2 Architecture

- **Platform/payload split (ADR-001, accepted 2026-07-16,
  `Dokumentation/ADR/ADR-001-platform-payload-split.md`):** the
  non-functional core (identity, config, OTA, telemetry, remote access, HAL,
  security, storage) is a reusable *platform*; the functional part (today:
  camera/timelapse capture) is a swappable *payload*, connected through a
  versioned `PayloadDriver` contract + capability manifest with real process
  isolation, control/data-plane separation, fail-closed privileges, and
  JIT conduits. See also `Dokumentation/Arkitektur/Modularisering_Platform_Payload_Plan.md`
  and `Dokumentation/ADR/ADR-0007-Evolution-from-Product-to-Platform.md`.
- **New endpoints do not go in `headend/main.py`.** Add an `APIRouter` under
  `headend/api/` with logic in `headend/services/`, and mount it from
  `main.py` as a thin wrapper. This is enforced mechanically (§2.3), not just
  by convention.
- **Additive, flag-guarded changes.** No schema breaks before live
  verification. **Never hard-delete** data — use quarantine or a reversible
  move instead (this has bitten the project before: see
  `Dokumentation/INCIDENT_2026-07-15_TEST_DATABASE_OVERWRITE.md`).
- **Don't silently touch another agent's uncommitted work.** Multiple AI
  sessions (and Peter) work on this repo concurrently; check `git status`/
  `git log`/open PRs before assuming a clean slate.

### 2.3 The `headend/main.py` architecture ratchet

`tests/test_architecture_ratchet.py` enforces two hard ceilings from
`tests/architecture_baseline.json`:

- `headend_main_max_lines` — current ceiling, checked against `wc -l`-style
  line count of `headend/main.py`.
- `headend_main_max_direct_routes` — count of `@app.<verb>(...)` /
  `@_legacy_app.<verb>(...)` route decorators directly in that file.

**Never raise these values to make a change fit.** If you need to add a
route, put it in a new/existing `APIRouter` under `headend/api/` with logic
in `headend/services/`, mounted from `main.py`. The baseline may only be
*lowered*, after extracting code out of `main.py` — see
`Dokumentation/TENKNISK_GÆLD_ANALYSE_headend_main_py_2026-07-06.md` and
`Dokumentation/P2-01_Refaktoreringsplan_main_py.md` for the ongoing
refactor plan. Recent sessions have landed exactly on the line ceiling more
than once (zero slack) — expect to need real extraction, not just careful
formatting, when adding non-trivial functionality.

### 2.4 Tech stack

- **Headend:** Python 3.12, FastAPI 0.136, SQLAlchemy 2.0, Uvicorn.
  PostgreSQL in production (`timelapse_db`); SQLite for local dev/tests via
  `DATABASE_URL`. Auth: `python-jose`, `bcrypt`, `webauthn`, `pyotp`
  (TOTP/MFA). `paramiko` for SSH/tunnel management. AI tagging via
  `google-genai` (Gemini 2.5 Flash over Vertex, `europe-west1`, plus the
  Gemini Batch API) and a local Ollama instance for text/translation.
  Rate limiting via `slowapi`.
- **Edge:** Python, no Node dependency — HAL for camera control (Nikon Z30 +
  Orange Pi 4 Pro), capture/upload pipeline, HMAC-signed reporting, local
  NPU (VIPLite) inference for QA scoring, self-update client.
- **Admin UI (`timelapse-ui/`):** React 19 + TypeScript 5.9 + Vite 8 +
  Tailwind CSS v4, `react-router-dom` 7, `recharts` for charts, `@xterm/xterm`
  for the in-browser SSH terminal, `@simplewebauthn/browser` for WebAuthn.
- **Lint/format/type-check** (`pyproject.toml`): Black (line-length 119, py312/py313),
  Ruff (`E,W,F,I,B,C4,UP,ARG,SIM`, line-length 119), MyPy (python 3.12,
  `warn_return_any`). ESLint + `tsc --noEmit` for the UI.

### 2.5 Development workflow

**Headend (API):**
```bash
cd headend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:////tmp/timelapse_dev.db"   # prod uses PostgreSQL
uvicorn main:app --reload --port 8000
```
See `Dokumentation/Installationsguide_v10.md` (Part A) for full production
setup (PostgreSQL, nginx, LaunchDaemons, secrets).

**Admin UI:**
```bash
cd timelapse-ui
npm install
npm run dev        # dev server with HMR
npm run build       # tsc -b && vite build
npm run lint:gate   # ESLint ratchet gate — fails only on more issues than baseline
```

**Edge agent:** see `Dokumentation/Installationsguide_v10.md` (Parts B/C)
for provisioning a physical Orange Pi + Nikon node. Pure Python
(`edge/requirements.txt`), no npm/Node needed.

### 2.6 Testing

```bash
# Repo-level integration/API tests
pytest tests/

# Headend contract tests (needs fastapi/sqlalchemy/slowapi/python-jose/bcrypt/
# passlib/python-multipart/python-dotenv/pytest in a venv — runs against a
# temporary SQLite DB, no live Postgres required)
cd headend && pytest tests/ -v

# Edge AI tests
pytest edge/ai/tests/

# Frontend
cd timelapse-ui && npm run lint:gate && npx tsc --noEmit
```

Notes:
- Test discovery config, markers (`integration`, `smoke`, `unit`, `security`,
  `gdpr`, `retention`, etc.) and default `addopts` live in `pyproject.toml`.
  Markers are `--strict-markers` — declare new ones there before use.
- **Database isolation is enforced, not just conventional.**
  `headend/database.py` raises at import time if pytest is running against a
  `DATABASE_URL` ending in `/timelapse_db` (the operational DB), unless
  `TIMELAPSE_ALLOW_PYTEST_PRODUCTION_DB=I_UNDERSTAND_DATA_WILL_BE_DESTROYED`
  is explicitly set. `tests/conftest.py` sets `DATABASE_URL` to
  `TIMELAPSE_TEST_DATABASE_URL` (defaulting to a separate `timelapse_test`
  DB) before any Headend module is imported.
- **Integration tests require explicit opt-in.** There is no
  localhost/port default for `TIMELAPSE_TEST_BASE_URL` — it must be set
  explicitly, and `TIMELAPSE_TEST_TARGET_ACK=I_UNDERSTAND_THIS_IS_A_TEST_TARGET`
  must also be set, so pytest can never accidentally discover and exercise a
  developer's locally running Headend.
- CI runs `pytest tests headend/tests edge/ai/tests --import-mode=importlib
  -m "not integration"` — integration-marked tests are excluded from CI by
  design (they need a live target).

### 2.7 CI/CD (`.github/workflows/ci.yml`)

- **`python-check`** — `py_compile` on every tracked `.py` file, `bash -n` on
  every tracked `.sh` file, then the pytest suite above (SQLite,
  non-integration).
- **`ui-check`** — `npx tsc --noEmit`, `npm run lint:gate` (the ESLint
  ratchet — fails only on *new* issues beyond baseline, referenced as gate
  "H-02"), `npm run build`.
- **`deploy-macmini`** (self-hosted runner, `main` pushes only) — checks out
  the exact workflow SHA (fails closed on any local tracked changes or SHA
  mismatch), builds the UI for that revision, restarts the headend
  LaunchDaemon, and health-checks `/api/health` with automatic rollback to
  the previous SHA (including UI rebuild) if the new revision fails health
  checks. Edge devices are **not** updated by this workflow — edge OTA goes
  through signed Headend artifacts/change tickets and the update-governance
  flow, not git-pull.

### 2.8 Documentation map

- **Start here:** `Dokumentation/00_START_HER.md` — master index, points to
  the latest authoritative version of every doc (`*_v10.md` etc.), the living
  working documents, and raw source material.
- **Status source of truth:** the GRC register (`grc_items` in production
  Postgres, surfaced in the UI under Compliance → GRC register) — not
  markdown. Markdown test/risk documents are migration sources, runbooks, or
  generated reports.
- **`Dokumentation/HANDOVER_LOG.md`** — the running session-to-session log.
  Newest entries at the top of `## Log`, using the template near the top of
  the file (`### Handover YYYY-MM-DD HH:MM — fra <X> til <Y>` with
  hvad-er-gjort / hvad-mangler / kommandoer / output / filer-rørt /
  risici sections). Entries before 2026-07-08 were rotated out to
  `HANDOVER_LOG_ARKIV_2026-06-28_til_2026-07-07.md`. **Read the newest few
  entries before substantive work** — this is where cross-session gotchas,
  in-flight designs, and "don't repeat this mistake" notes live.
- **ADRs:** `Dokumentation/ADR/` — binding accepted architecture decisions.
- **Security closures:** `Dokumentation/SEC-NNN_*.md` — one file per named
  security finding/closure, referenced by ID (e.g. `SEC-016`) in commits,
  GRC rows, and handover entries.
- Most documentation is written in **Danish**; code and code comments are
  mostly English with some Danish mixed in (variable/table names,
  domain terms). Expect both in this repo.

### 2.9 Security & compliance posture

The project is built around SABSA methodology and is deliberately aware of
ISO 27001, IEC 62443, CRA, GDPR, NIS2, and the EU AI Act — see
`Dokumentation/RISK_ASSESSMENT_v10.md`, `Dokumentation/TimeLapse_Security_Compliance_v10.md`,
and `Dokumentation/SABSA_Architecture_v10.md`. In practice this shows up as:

- Fail-closed defaults on anything touching auth/trust (e.g. pytest refusing
  the production DB, TOTP secrets never falling back to a shared/demo value,
  edge SSH private keys never being escrowed/exported by the headend — see
  the SEC-016 and SEC-ZAI-05/15 closures in `Dokumentation/`).
- Security findings and their closures are tracked as GRC rows with a
  `status`, cross-referenced from a `Dokumentation/SEC-NNN_*.md` file — check
  the register before assuming something is unfixed *or* assuming a past
  closure is still valid (this repo has re-broken closed findings before).
- Don't report security holes in public channels; use the same
  Handover-log/GRC coordination the rest of the team uses.

### 2.10 Multi-agent collaboration

Claude, Codex, ChatGPT, Kimi, and Gemini sessions all work on this repo,
sometimes concurrently, alongside Peter (product/ops owner and decision
maker). Before starting substantive work: check `git status`, `git log`,
and open PRs — don't assume you're the only active session, and don't
silently overwrite uncommitted work that isn't yours. Coordination rules
live in `Dokumentation/SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`.
