# Acceptance Gate And Roadmap

## What should not merge/deploy yet

Do not deploy a full Edge artifact to existing Edges until:

- signed current-main Edge artifact exists and verifies;
- rollback artifact exists and verifies;
- F-001/F-005-style security gates are green on current main;
- Edge 2 host identity is verified through authenticated Edge report;
- no deployment path overwrites device ID, GPIO mapping, capture DB/images, site assignment or existing working credentials.

Do not enable browser terminal for TL-043EB9E72EFD until:

- authenticated Edge report confirms host key fingerprint;
- known_hosts rotation is documented as controlled trust rotation, not bypass;
- capability/MFA/grant/timeout/audit path remains enforced.

Do not treat local technician access as complete until:

- `edge/technician_auth.py` confirmation SQL is fixed and tested;
- live EdgeServiceGrant revoke/expiry can be observed through TechnicianAuth to ServicePlatform cleanup;
- break-glass is either completed end-to-end or explicitly marked unavailable.

Do not claim production compliance until:

- DPIA/site surveillance controls are done;
- restore rehearsal is complete;
- supplier/update/vulnerability process is formalized;
- licensed control catalogs are imported where certification-style claims are needed.

## What should be implemented first

### 1. Fix the technician auth SQL regression

Small PR. Add test. This removes an avoidable P1.

### 2. Finish Edge 2 read-only trust unblocker

Deliver authenticated SSH host public-key fingerprint evidence via Edge->Headend channel. Compare old trusted fingerprint and unauthenticated keyscan. Do not update known_hosts automatically.

### 3. Generate signed deployable Edge application artifact

No source/worktree deployment. Artifact must include:

- version;
- source commit;
- SHA-256;
- signature;
- manifest;
- compatibility metadata;
- rollback target.

### 4. Prove rollback/recovery before Edge deployment

For Edge 2, deployment should remain blocked unless rollback can be performed without physical access and without destructive credential replacement.

### 5. Controlled canary Edge convergence

Upgrade only one Edge, verify:

- agent/service health;
- heartbeat/API auth;
- capture scheduler one attempt per scheduled slot;
- upload;
- camera diagnostics even if actual camera failure remains;
- storage/network/modem;
- certificate/trust status;
- reboot/reconnect.

### 6. Close live technician key / break-glass delta

Provision live devices with the new technician user/authorized key path and complete break-glass or formally de-scope it for RC1.

### 7. Restore rehearsal

Run and document Headend DB + capture-store restore. This is a Mission Framework continuity gate.

### 8. Compliance readiness pack

Create a practical customer-facing assurance pack:

- DPIA template;
- site surveillance checklist;
- data processing role matrix;
- retention/disposition policy;
- vulnerability disclosure and update SLA;
- SBOM/release evidence procedure.

## RC1 acceptance recommendation

RC1 can be considered when:

- no P0 open;
- all P1s fixed, risk-accepted, or explicitly de-scoped by Product Owner;
- current main deploys deterministically;
- at least one existing Edge is non-destructively converged from legacy state;
- backup/restore rehearsal is green;
- compliance claims are worded as readiness/evidence, not certification.

