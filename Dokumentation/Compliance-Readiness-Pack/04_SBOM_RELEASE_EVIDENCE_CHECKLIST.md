# SBOM And Release Evidence Checklist

**Status:** Release-readiness checkliste  
**Bygger på:** `LICENS_COMPLIANCE_OG_SBOM_EVIDENS_v1.md`, Codex-Audit, signed artifact model.

## 1. Artifact identity

| Felt | Krav | Udfyldt |
|---|---|---|
| Artifact id | Unik og immutabel | |
| Version | Semver/lab/prod label | |
| Source commit | Exact SHA | |
| Build timestamp | UTC | |
| Builder identity | CI/release pipeline | |
| Target | Headend / Edge / OS / mixed | |
| Compatibility metadata | Device class, migration min/max | |
| Rollback target | Artifact id/version | |

## 2. Integrity and signing

| Kontrol | Krav | Udfyldt |
|---|---|---|
| SHA-256 | Manifest hash | |
| Signature | Real configured signer outside LAB/test | |
| Signer identity | Expected production key | |
| Verification test | Edge/Headend rejects missing/invalid signature | |
| No `system-hash` production trust | Must fail closed | |
| Exact deployed revision | Verified artifact equals deployed SHA/version | |

## 3. SBOM/license

| Kontrol | Krav | Udfyldt |
|---|---|---|
| Runtime dependencies | Captured from artifact/image | |
| npm lockfile | Included where UI bundled | |
| Python packages | Versioned | |
| OS packages | Versioned for Edge/Headend OS path | |
| License classification | permissive / obligations / review / unknown / blocked | |
| Third-party notices | Generated or dispositioned | |
| GPL/LGPL source offer | Disposition documented if distributed | |
| Codec/patent review | FFmpeg/H.264/H.265 disposition | |

## 4. Change governance

| Kontrol | Krav | Udfyldt |
|---|---|---|
| Change ticket | Linked | |
| Risk classification | low/medium/high/security | |
| Affected customers/sites | Listed | |
| Migration impact | Documented | |
| Rollback impact | Documented | |
| Test results | Linked | |
| Approval | Named approver and timestamp | |

## 5. Edge-specific no-regression controls

For existing Edges, release must explicitly preserve:

- device id;
- lifecycle state;
- API credential;
- SSH/TLS private keys unless explicit rotation path approved;
- GPIO/relay mapping;
- capture DB and local images;
- site/camera assignment;
- modem/network configuration;
- legacy migration adapters until replacement path is verified active.

## 6. Evidence bundle output

Store or link:

- artifact manifest;
- signature;
- SHA-256;
- SBOM/license report;
- test run ids;
- migration logs;
- rollout approval;
- post-deploy health verification;
- rollback rehearsal or rollback verification.

