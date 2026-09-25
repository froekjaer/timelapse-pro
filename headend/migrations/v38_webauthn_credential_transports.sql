-- TimeLapse Pro - v38 WebAuthn credential transports
-- Peter (2026-09-24): logging in via passkey/Touch ID hung indefinitely from a
-- MacBook while working fine from the Headend's own browser. Root cause:
-- webauthn_credentials never stored which transport (internal platform
-- authenticator vs. cross-device/hybrid vs. USB security key) each credential
-- uses, so login-begin sent every allowCredentials entry with no transport
-- hint. When a device's own platform credential doesn't resolve locally, the
-- browser can fall into an ambiguous cross-device wait instead of failing
-- cleanly. Storing transports at registration lets login-begin scope each
-- credential correctly.
-- See Dokumentation/HANDOVER_LOG.md, 2026-09-24 entry.

ALTER TABLE webauthn_credentials ADD COLUMN IF NOT EXISTS transports TEXT;
