# TimeLapse Pro Port Profile

## Production intent

TimeLapse Pro must not assume ownership of ports that are commonly already used
on a production headend.

| Port | Exposure | Owner / purpose |
| --- | --- | --- |
| 22 | Not TimeLapse | Existing admin SSH or customer platform service |
| 80 | Not TimeLapse directly | Existing reverse proxy / ACME HTTP-01 if available |
| 443 | Not TimeLapse directly | Existing reverse proxy vhost for `timelapse.froekjaer.dk` |
| 2222 | Not TimeLapse | Reserved for other production application use |
| 22222 | TimeLapse inbound | Dedicated SFTP upload from Edge to Headend |
| 8000 | Loopback/internal | Headend FastAPI service behind reverse proxy |
| 8080 | Loopback/internal or changed | Open WebUI only behind authenticated TimeLapse/reverse proxy |

## Security rules

- Edge devices initiate all normal communication to Headend.
- Headend must not require direct inbound access to Edge except during explicit
  manual debug via SSH tunnel.
- `sftp_*` site upload users are only valid on TCP/22222.
- `sftp_*` users must not be allowed to authenticate on TCP/22 or TCP/2222.
- Customer/site data isolation is enforced by separate site SFTP users and by
  application-level RBAC for search, thumbnails, tags, AI/Ollama, CMDB and SIEM.
- Open WebUI is an internal tool and must not be exposed directly without
  TimeLapse MFA-authenticated access control.

## Lab notes

The lab Mac Mini may still have macOS Remote Login on TCP/22 for administration,
but TimeLapse upload users must be denied on that port. The production headend
should use the customer's existing reverse proxy for TCP/80 and TCP/443 and keep
TimeLapse app services bound to loopback/internal ports.
