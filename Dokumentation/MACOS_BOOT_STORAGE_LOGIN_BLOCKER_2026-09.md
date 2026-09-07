# macOS Boot Storage/Login Blocker

**Date:** 2026-09-07  
**Status:** Open operational finding; temporary workaround active

## Finding

With macOS auto-login disabled, the Mac Mini reaches the login window before the external USB/APFS volume `data-fast` is usable. The Headend waits for storage and therefore becomes available only after console login makes the volume available.

## Evidence

- Boot at approximately 23:33.
- Console login at approximately 23:35.
- `data-fast` became mounted at approximately 23:35.
- Headend became ready immediately afterward.
- `data-fast` is an unencrypted APFS volume on external USB.
- Headend and node-agent are system LaunchDaemons; the application services themselves do not require an interactive login.
- Earlier mount logs contained an attempted mount of APFS physical-store device `disk6s2` rather than the APFS volume. The current wrapper rejects that device and accepts only a device whose `diskutil info` reports volume name `data-fast`.

## Temporary Decision

macOS auto-login is enabled temporarily to preserve unattended nightly reboot and operation. This is a documented workaround, not closure of the finding, and has the expected physical-access/security trade-off.

## Required Permanent Fix

Implement one authoritative, UUID/device-validated system-boot mount flow that makes `data-fast` available without console login. Prove it over a cold reboot with auto-login disabled before removing this workaround. The acceptance test must verify storage, PostgreSQL, Headend, node-agent and API health before any console login.

## Safety Boundary

No capture data, credentials, GPIO mapping, device identity or Edge state may be changed while resolving this finding.
