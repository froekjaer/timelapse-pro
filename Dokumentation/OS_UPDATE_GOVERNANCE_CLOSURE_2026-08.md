# OS Update Governance Closure — 2026-08

Status: Proposed implementation evidence.

This change separates **observation** from **deployment authority** for Edge OS updates.

- Edge/CMDB inventory may observe that apt packages are available.
- That observation is recorded as `blocked`, not as deployable `pending` work.
- Repeated CMDB observations cannot silently preserve or promote an approved/pending deployment state; the observation path forces its own row back to `blocked`.
- The automatic offline OS bundle builder requires explicit lab build-plan evidence via the existing plan reference before it will build an artifact.
- Artifact signing, approval, scope/environment authority and Edge installation remain separate gates.

This closes the update-flow governance bypass where telemetry could previously create deployable OS update work without the intended lab/catalog/build-plan transition.
