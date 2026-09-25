-- TimeLapse Pro - v39 WebAuthn credential RP ID
-- Peter (2026-09-25): passkey login still hung in Safari 27/macOS 27 after v38.
-- login-begin sent every credential for the user to both domains, although a
-- passkey only works for the RP ID it was registered under
-- (timelapse-pro.dk vs. timelapse.froekjaer.dk). Storing rp_id lets
-- login-begin/register-begin offer only credentials valid for the current RP.
-- See Dokumentation/HANDOVER_LOG.md, 2026-09-25 entry.

ALTER TABLE webauthn_credentials ADD COLUMN IF NOT EXISTS rp_id VARCHAR(255);

-- One-time backfill of existing rows for this Headend, derived from the nginx
-- access log (every successful POST /api/auth/webauthn/register-complete, all
-- users, 2026-05-28 .. 2026-09-25):
--   2026-05-28 04:09, 05-28 07:51, 06-01 19:31, 07-16 13:01  -> timelapse.froekjaer.dk
--   2026-09-07 00:00, 09-11 22:06, 09-24 21:27 (+02:00)      -> backend.timelapse-pro.dk:8443
-- The timelapse-pro.dk RP only exists since 2026-09-06 (per-origin RP selection),
-- and no registration succeeded between 07-16 and 09-07, so 2026-08-01 is an
-- unambiguous split independent of how created_at's timezone was stored.
-- Rows created after this migration get rp_id at registration time; any row
-- still NULL is offered on every RP and bound on its first successful login.
UPDATE webauthn_credentials SET rp_id = 'timelapse.froekjaer.dk'
 WHERE rp_id IS NULL AND created_at < '2026-08-01';
UPDATE webauthn_credentials SET rp_id = 'timelapse-pro.dk'
 WHERE rp_id IS NULL AND created_at >= '2026-08-01' AND created_at < '2026-09-25 12:00';
