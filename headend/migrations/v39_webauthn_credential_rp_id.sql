-- TimeLapse Pro - v39 WebAuthn credential RP ID
-- Peter (2026-09-25): passkey login still hung in Safari 27/macOS 27 after v38.
-- login-begin sent every credential for the user to both domains, although a
-- passkey only works for the RP ID it was registered under
-- (timelapse-pro.dk vs. timelapse.froekjaer.dk). Storing rp_id lets
-- login-begin/register-begin offer only credentials valid for the current RP.
-- Existing rows stay NULL (still offered) and are bound on first successful login.
-- See Dokumentation/HANDOVER_LOG.md, 2026-09-25 entry.

ALTER TABLE webauthn_credentials ADD COLUMN IF NOT EXISTS rp_id VARCHAR(255);
