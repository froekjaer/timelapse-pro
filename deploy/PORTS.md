# TimeLapse Pro Port Profile

## Production intent

TimeLapse Pro must not assume ownership of ports that are commonly already used
on a production headend.

| Port | Exposure | Owner / purpose |
| --- | --- | --- |
| 22 | Not TimeLapse | Existing admin SSH or customer platform service |
| 80 | Not TimeLapse directly | Existing public web entrypoint / ACME HTTP-01 / redirect layer |
| 443 | Not TimeLapse directly | Existing public HTTPS entrypoint with hostname routing |
| 2222 | Not TimeLapse | Reserved for other production application use |
| 22222 | TimeLapse inbound | Dedicated SFTP upload from Edge to Headend |
| 22022 | TimeLapse inbound | Dedicated reverse-SSH control/management ingress — `timelapse_tunnel@backend.timelapse-pro.dk:22022`, own sshd instance (`deploy/ssh/timelapse-tunnel-sshd.conf`), pubkey-only, remote-forward-only, per-Edge `permitlisten` allowlist, forwards bound to headend loopback |
| 5514 | TimeLapse internal/lab | Optional local SIEM syslog receiver (UDP/TCP). Production external logs should normally arrive via Edge/site collector API forwarding. |
| 8000 | Loopback/internal | Headend FastAPI service behind reverse proxy |
| 8080 | Loopback/internal or changed | Open WebUI only behind authenticated TimeLapse/reverse proxy |

## Security rules

- Edge devices initiate all normal communication to Headend.
- Headend must not require direct inbound access to Edge except during explicit
  manual debug via SSH tunnel.
- `sftp_*` site upload users are only valid on TCP/22222.
- Edge reverse-SSH control connections must use TCP/22022 and the `timelapse_tunnel` service identity (pubkey-only, no shell/PTY, `ForceCommand /usr/bin/false`, remote-forwarding only). The admin sshd on 22/22222 must NOT be the production tunnel ingress.
- Reverse remote ports are per-device and must remain loopback-only on the headend: `TL-C87FF9587CA0` → `127.0.0.1:2201`, `TL-043EB9E72EFD` → `127.0.0.1:2204`. Each Edge's tunnel key may `permitlisten` only its own port.
- Tunnel private keys are per-Edge and must never be shared or reused from API-mTLS keys; the tunnel host key (dedicated instance) is pinned per Edge at cutover.
- `sftp_*` users must not be allowed to authenticate on TCP/22 or TCP/2222.
- Customer/site data isolation is enforced by separate site SFTP users and by
  application-level RBAC for search, thumbnails, tags, AI/Ollama, CMDB and SIEM.
- Open WebUI is an internal tool and must not be exposed directly without
  TimeLapse MFA-authenticated access control.
- External syslog ingress should normally terminate at an Edge/site collector,
  which forwards normalized events to Headend over the authenticated TimeLapse
  SIEM API. Headend enforces batch and per-device rate limits.
- If Headend direct syslog ingress is used for lab or a special deployment, it
  must be restricted to CMDB-known network devices or explicit source allowlists.
  Lab may accept broader sources while testing.
- Prefer UDP/TCP 5514 for TimeLapse syslog ingestion. If a customer requires
  standard UDP/TCP 514, use firewall/NAT or a local relay to forward to 5514 so
  the receiver does not need privileged binding.

## Lab notes

The lab Mac Mini may still have macOS Remote Login on TCP/22 for administration,
but TimeLapse upload users must be denied on that port. The production headend
should use the customer's existing reverse proxy for TCP/80 and TCP/443 and keep
TimeLapse app services bound to loopback/internal ports.

## Hostname routing on shared 80/443

DNS cannot by itself route `ftp.example.net` and `timelapse.example.net` to
different local applications when they share the same public IP and the same
TCP ports. DNS only resolves names to addresses.

Use one of these production patterns:

1. Preferred: one edge reverse proxy owns TCP/80 and TCP/443 and routes by
   hostname/SNI/Host header:
   - `ftp.hyldager.net` -> existing customer-facing file sharing system
   - `timelapse.hyldager.net` -> TimeLapse UI / Headend API
   - optional `openwebui.hyldager.net` -> Open WebUI, protected by TimeLapse MFA
2. Alternative: assign a separate public IP to TimeLapse and point
   `timelapse.hyldager.net` to that IP.
3. Alternative: keep TimeLapse on non-standard public ports. This is not
   preferred for customer-facing HTTPS and complicates compliance, firewall
   policy and user experience.

If the existing file sharing system currently binds directly to TCP/80 and
TCP/443, it should either:

- be moved behind the shared reverse proxy on loopback/internal ports, or
- remain on its own public IP while TimeLapse uses another public IP.

TimeLapse should not require public TCP/8080. Open WebUI must remain loopback or
internal and be exposed only through an authenticated TimeLapse/reverse-proxy
route.
