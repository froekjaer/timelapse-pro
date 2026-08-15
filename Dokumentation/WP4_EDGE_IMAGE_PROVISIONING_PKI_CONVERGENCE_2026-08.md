# WP-4 — Edge Image, Provisioning & PKI Convergence

Status: implementation baseline for locked architecture.

Authority: `TIMELAPSE_PRO_RELEASE_CONVERGENCE_PLAN_2026-08.md` and `TIMELAPSE_PRO_LOCKED_ARCHITECTURE_DECISIONS_2026-08.md`.

## Target Model

`Generic Signed Edge Image + Signed Device Provisioning Envelope`

Responsibilities are split:

- Release Artifact Builder: builds a reusable, device-neutral signed Edge image manifest.
- Device Provisioning Service: creates a signed, device-bound provisioning envelope.
- TimeLapse Trust Service: verifies envelope, consumes bootstrap, signs CSRs and owns credential lifecycle metadata.
- Edge first boot: generates permanent operational SSH/TLS private keys locally and sends only public key/CSR material.
- Legacy Flash Composer: remains as an explicit migration adapter for existing per-device image paths.

## Delivered Contracts

- Generic release artifact manifest is device-neutral and contains no operational private keys.
- Provisioning envelope is signed, expiring, device/hardware-bound and one-purpose.
- Bootstrap token is consumed, revoked and recorded in `edge_credential_inventory`.
- Replayed/consumed bootstrap envelope fails closed.
- Wrong hardware binding fails closed.
- Revoked/retired devices cannot re-enroll or receive new TLS certificate without explicit recovery flow.
- Edge first boot generates SSH private key and TLS private key locally.
- Trust Service stores SSH public key/fingerprint and TLS certificate metadata only.
- CSR signing validates CSR signature and device binding before issuing certificate.
- SSH/TLS credential inventory integrates with `edge_credential_inventory`.
- Credentialing completion requires both active Edge-owned SSH and local TLS credentials, then advances lifecycle to `credentialed`.
- Replacement hardware can inherit logical assignment without inheriting old private keys.
- Legacy per-device image path remains migration-compatible through an explicit adapter plan.

## Migration Impact

No new database tables are introduced in this slice.

WP-4 uses existing canonical stores:

- `bootstrap_tokens`
- `edge_lifecycle_records`
- `edge_credential_inventory`

Existing Edges continue through compatibility adapters. New WP-4 provisioning should use the envelope/CSR path and must not create new permanent Headend-held Edge SSH/TLS private keys.

## Remaining Legacy Paths

- Existing per-device flash image injection still exists as a migration adapter.
- Existing image-injected local TLS key/certificate can be inventoried and migrated, but new canonical issuance is CSR-based.
- Existing Headend-held support SSH private keys remain legacy recovery material until each Edge rotates to Edge-generated keys.
- Existing bootstrap YAML/token flow remains for migration compatibility, but WP-4 envelopes make new bootstrap credentials one-purpose and consumed after enrollment.

## Rollback

Rollback is code-only for this slice:

- stop using provisioning envelopes for new Edges
- continue existing per-device image/provisioning adapter
- leave `edge_credential_inventory` records as audit/lifecycle metadata
- revoke any issued bootstrap envelope credentials and issue a fresh legacy bootstrap token if required

No destructive migration is required.

## Tests

WP-4 contract tests:

- cloned/replayed envelope rejected
- consumed bootstrap cannot be reused
- wrong hardware/device binding rejected
- private SSH/TLS keys never leave Edge
- valid CSR receives certificate
- revoked device cannot re-enroll without explicit recovery
- replacement Edge can inherit logical project assignment without inheriting old private keys
- old image/provisioning path remains migration-compatible
- full fresh-Edge flow succeeds from blank media to enrolled/credentialed state
- credential revocation and re-enrollment recovery are explicit

## Out Of Scope

- Browser terminal
- New technician service features
- Big-bang migration of existing Edges
- Replacing the Edge Local CA storage model
- Moving Trust Service to a separate physical zone
