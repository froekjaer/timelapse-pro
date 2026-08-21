# Architecture And Dataflows

## Aktuel struktur

TimeLapse Pro består nu tydeligt af disse hovedzoner:

```text
Browser / Admin UI
        |
        v
Headend API / UI
        |
        +--> TimeLapse Trust Service boundary
        |       - lifecycle
        |       - credential inventory
        |       - PDP
        |       - EdgeServiceGrant
        |       - SSH host trust evidence
        |
        +--> Application modules
        |       - captures/projects
        |       - CMDB
        |       - compliance/GRC
        |       - updates/artifacts
        |       - technician keys
        |
        +--> Data zone
                - PostgreSQL
                - capture storage
                - audit/evidence

Edge device
        |
        +--> edge agent / sync poll
        +--> capture scheduler / camera driver
        +--> HAL / relay / GPIO
        +--> ServicePlatform / Service Operations
        +--> local technician access
        +--> SFTP upload
```

## Primære dataflows

### 1. Capture/upload

```text
Camera -> Edge capture -> sidecar/hash/quality metadata -> local buffer
     -> SFTP upload per site/customer profile -> Headend storage/import/UI
```

Positive controls:

- known_hosts fail-closed i `edge/upload/sftp.py`;
- sidecar/hash evidence model;
- no automatic destructive project cleanup if state is unknown.

Risici:

- per-site SFTP credential ownership skal fortsat afgrænses mellem site RBAC og Edge lifecycle;
- upload health skal forbindes til credential inventory så manglende known_hosts ikke bliver støj hvert 10. minut uden remediation flow.

### 2. Edge API/sync

```text
Edge agent -> authenticated sync poll -> Headend config/update/heartbeat/SIEM
```

Positive controls:

- API token resolver bruger credential inventory som canonical path og legacy adapter;
- revoked/retired lifecycle state failer closed;
- HMAC/attestation support findes som overgangskontrol.

Risici:

- handover beskriver historisk dobbelte loops/version-hash mismatch; det skal verificeres at current main ikke stadig har uønsket parallel polling i live runtime;
- legacy `devices.api_token` må ikke blive ny creation path.

### 3. Provisioning / WP-4

```text
Generic signed image
    + signed provisioning envelope
    -> first boot
    -> hardware binding
    -> consume one-time bootstrap
    -> Edge generates SSH/TLS private keys
    -> public key + CSR to Trust Service
    -> certificate issuance + credential inventory active
```

Positive controls:

- tests viser private SSH/TLS keys bliver på Edge;
- envelope replay/wrong hardware/expired/revoked cases dækkes i contract tests;
- replacement flow skelner private keys fra logical assignment.

Risici:

- signed deployable Edge app artifact og rollback artifact er stadig en deployment gate;
- live migration skal være one-device-at-a-time og non-destructive.

### 4. Technician service

```text
Headend principal + MFA + PDP
        -> EdgeServiceGrant
        -> Edge TechnicianAuth
        -> ServiceSession
        -> Service Operations
        -> HAL/camera/modem/system handlers
```

Positive controls:

- ServiceSession owns leases;
- revoke/expiry invalidates session and releases LiveView/CameraPowerLease;
- UI/CLI/LAB target samme backend;
- shared status object exists.

Risici:

- `edge/technician_auth.py` confirmation bug kan blokere normal EdgeServiceGrant confirmation;
- retired legacy QR technician UI code remains import-compatible; ensure it never starts unauthenticated in production;
- browser shell skal fortsat være explicit break-glass/engineering capability, not normal service.

### 5. Browser SSH terminal

```text
Admin/engineer with MFA
    -> PDP capability edge.shell.remote
    -> short-lived EdgeServiceGrant
    -> trusted SSH host key registry
    -> reverse tunnel localhost:<port>
    -> audited terminal session
```

Positive controls:

- no `AutoAddPolicy`;
- `RejectPolicy`;
- terminal denied without trusted host key;
- grant revoke watcher closes session.

Risici:

- legacy known_hosts migration observes the current key through the active tunnel and compares to known_hosts. This is a pragmatic bridge, not a substitute for authenticated Edge host-key reporting.
- TL-043EB9E72EFD must remain denied until its host key mismatch is resolved.

## Architecture assessment

Target-modellen er god. Det vigtigste der mangler, er ikke en ny arkitektur, men:

- færre parallelle legacy authorities;
- mere live evidence;
- stronger release artifact discipline;
- closure of ad hoc authorization paths;
- deterministic restoration and rollback rehearsal.

