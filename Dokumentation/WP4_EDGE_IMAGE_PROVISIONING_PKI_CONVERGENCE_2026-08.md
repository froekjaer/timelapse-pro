# WP-4 — Edge Image, Provisioning & PKI Convergence

Status: WP-4 exit-gate candidate for PR #21.

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
- Generic release artifact verification rejects wrong target/digest before provisioning.
- Provisioning envelope is signed, expiring, device/hardware-bound and one-purpose.
- Bootstrap token is consumed, revoked and recorded in `edge_credential_inventory`.
- Replayed/consumed bootstrap envelope fails closed.
- Revoked and expired provisioning envelopes fail closed.
- Wrong hardware binding fails closed.
- Power loss after envelope validation but before bootstrap consume can retry because consume has not happened yet.
- Power loss after Edge key generation but before enrollment can retry without exporting private keys.
- Enrollment retry is idempotent for the same active SSH public key.
- Duplicate TLS CSR issuance is rejected.
- Revoked/retired devices cannot re-enroll or receive new TLS certificate without explicit recovery flow.
- Edge first boot generates SSH private key and TLS private key locally.
- Trust Service stores SSH public key/fingerprint and TLS certificate metadata only.
- CSR signing validates CSR signature and device binding before issuing certificate.
- SSH/TLS credential inventory integrates with `edge_credential_inventory`.
- Credentialing completion requires both active Edge-owned SSH and local TLS credentials, then advances lifecycle to `credentialed`.
- Replacement hardware can inherit logical assignment without inheriting old private keys.
- Existing Edges can migrate one-at-a-time while preserving capture/upload credentials until successor credentials are active.
- Existing image-injected TLS and Headend-held SSH credentials can be rotated out so they are no longer parallel authorities.
- Legacy per-device image path remains migration-compatible through an explicit read-only adapter plan.

## Migration Impact

No new database tables are introduced in this slice.

WP-4 uses existing canonical stores:

- `bootstrap_tokens`
- `edge_lifecycle_records`
- `edge_credential_inventory`

Existing Edges continue through compatibility adapters. New WP-4 provisioning must use the envelope/CSR path and must not create new permanent Headend-held Edge SSH/TLS private keys.

## Remaining Legacy Paths

After WP-4, legacy secret/private-key paths are compatibility inputs only. They may read and migrate existing state; they must not write new credentials for new Edges.

- Existing per-device flash image injection: migration adapter only; may not create new operational private keys or new canonical credentials.
- Existing image-injected local TLS key/certificate: may be inventoried and rotated out; new canonical issuance is Edge-generated TLS key plus CSR to Trust Service.
- Existing Headend-held support SSH private key (`devices.ssh_private_key` style storage): legacy recovery/migration material only until each Edge rotates to an Edge-generated SSH key.
- Existing Edge file key path `/etc/timelapse/device_keys/id_ed25519`: read/migrate existing Edge-local keys only; new keys are generated on Edge during first boot and registered by public key.
- Existing bootstrap YAML/token flow: migration compatibility only; new bootstrap credentials are signed envelopes with expiry and consumed/revoked state.
- Existing `devices.api_token`: legacy Edge API compatibility only; it is not an enrollment authority for new Edges.
- Existing site SFTP credentials: site RBAC/upload compatibility material; Edge lifecycle may inventory Edge-consumed upload credentials, but SFTP architecture is not widened in WP-4.

Allowed writer after WP-4: the Trust Service WP-4 provisioning path only:

- signed provisioning envelope
- atomic bootstrap consume
- Edge-owned SSH public-key enrollment
- Edge-owned TLS CSR issuance
- lifecycle inventory metadata

## Rollback

Rollback is code-only for this slice:

- stop using provisioning envelopes for new Edges
- continue existing per-device image/provisioning adapter
- leave `edge_credential_inventory` records as audit/lifecycle metadata
- revoke any issued bootstrap envelope credentials and issue a fresh legacy bootstrap token if required

No destructive migration is required.

## Tests

WP-4 contract tests:

- generic image verification is device-neutral
- cloned/replayed envelope rejected
- consumed bootstrap cannot be reused
- wrong hardware/device binding rejected
- expired envelope rejected
- revoked envelope rejected
- power loss after envelope validation but before bootstrap consume can retry
- power loss after key generation but before enrollment can retry
- enrollment retry is idempotent for same SSH public key
- duplicate CSR rejected
- private SSH/TLS keys never leave Edge
- valid CSR receives certificate
- revoked device cannot re-enroll without explicit recovery
- revoked device can receive certificate after explicit recovery transition
- replacement Edge can inherit logical project assignment without inheriting old private keys
- old image/provisioning path remains migration-compatible
- existing legacy Edge migration preserves capture/upload scope without writing new legacy credentials
- image-injected TLS and Headend-held SSH credentials rotate out without leaving parallel authority
- full fresh-Edge flow succeeds from blank media to enrolled/credentialed state
- credential revocation and re-enrollment recovery are explicit

## Out Of Scope

- Browser terminal
- New technician service features
- Big-bang migration of existing Edges
- Replacing the Edge Local CA storage model
- Moving Trust Service to a separate physical zone
