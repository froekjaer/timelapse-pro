# Mac Headend asset og portregister

Dato: 2026-06-05
Host: Mac Mini Headend
Status: Første inventory efter nginx-genopretning og CrushFTP-konfliktobservation.

Relateret portmigrationsplan:

- `Dokumentation/Mac_Headend_Port_Migration_Plan_2026-06-05.md`

## Formål

Dette register adskiller TimeLapse Pro-komponenter fra platformkomponenter og co-resident software.

TimeLapse Pro må ikke kritikløst opdatere software på Mac Headend, som ikke er del af TimeLapse Pro eller en eksplicit platformdependency.

## Klassifikation

| Klasse | Betydning |
|---|---|
| `TLP-managed` | TimeLapse Pro ejer konfiguration, release og drift |
| `TLP-platform` | TimeLapse Pro afhænger af komponenten, men den er platformsoftware |
| `Host/platform` | macOS/host-administration, ikke TimeLapse-owned |
| `Co-resident/foreign` | Anden software på samme host, fx CrushFTP |
| `Unknown` | Skal klassificeres før production-hardening |

## Kendte services

| Service | Klasse | Status | Kommentar |
|---|---|---|---|
| TimeLapse Headend API / uvicorn | `TLP-managed` | Kører | Port 8000 |
| TimeLapse UI static via nginx | `TLP-managed` | Kører | Public HTTPS via nginx |
| nginx | `TLP-managed/TLP-platform` | Kører | Ejer public 80/443 i nuværende model |
| PostgreSQL 17 | `TLP-platform` | Kører | Lokal DB på 127.0.0.1:5432 |
| node-agent | `TLP-managed` | Kører | Headend/node telemetry |
| syslog receiver | `TLP-managed` | Kører | 127.0.0.1:5514 |
| Ollama | `TLP-platform` | Kører | 127.0.0.1:11434 |
| OpenWebUI | `TLP-platform` | Periodisk/aktiv hvis process kører | Bør være bag nginx |
| SSH | `Host/platform` | Kører | Port 22 |
| macOS Screen Sharing/VNC | `Host/platform` | Kører | Port 5900 |
| CrushFTP 11 Enterprise 1 | `Co-resident/foreign` | Installeret ifølge driftobservation | Skal port- og owner-registreres |

## Aktuelle lytteporte observeret

| Port | Binding | Foreløbig owner | Handling |
|---:|---|---|---|
| 80 | `*` | `TLP-managed nginx` | OK |
| 443 | `*` | `TLP-managed nginx` | OK |
| 8000 | `*` | `TLP-managed Headend API` | OK |
| 5432 | `127.0.0.1`/`::1` | `TLP-platform PostgreSQL` | OK |
| 5514 | `127.0.0.1` | `TLP-managed syslog receiver` | OK |
| 22222 | `*` | `TLP-managed/platform SFTP ingress` | OK, bekræft service owner |
| 11434 | `127.0.0.1` | `TLP-platform Ollama` | OK |
| 22 | `*` | `Host/platform SSH` | OK |
| 5900 | `*` | `Host/platform VNC` | OK, vurder exposure |
| 88 | `*` | `Host/platform Kerberos/system` | OK, dokumenter hvis production |
| 2201 | `*` | `Unknown` | Klassificer før production |
| 5000 | `*` | `Unknown` | Klassificer før production |
| 7000 | `*` | `Unknown` | Klassificer før production |
| 3283 | `*` | `Host/platform Apple Remote Desktop?` | Bekræft |
| 49359 | `*` | `Host/platform/unknown` | Bekræft |
| 50416/50417 | `*` | `Host/platform/unknown` | Bekræft |

## CrushFTP beslutningspunkt

CrushFTP er co-resident software og må ikke opdateres af TimeLapse Pro update flow.

Før production skal vi beslutte:

1. Skal CrushFTP blive på samme Mac som TimeLapse Headend?
2. Hvilke porte bruger CrushFTP faktisk?
3. Skal CrushFTP publiceres via samme nginx reverse proxy, egen port, eller flyttes til anden host?
4. Hvem ejer CrushFTP patching og security advisories?
5. Skal CrushFTP indgå som external dependency i TimeLapse risk register?

Foreløbig anbefaling:

- TimeLapse nginx ejer `80/443`.
- CrushFTP må ikke binde direkte til `80/443` på samme host.
- Hvis CrushFTP skal eksponeres eksternt, bør den ligge bag en eksplicit reverse proxy vhost eller på separat host.
- CrushFTP updates skal være kundens/host ownerens change, men TimeLapse pre-flight skal stoppe deployment hvis port/cert/storage konflikt opstår.

## Pre-flight kommandoer

```bash
netstat -na | grep -i listen
brew services list
launchctl list | egrep -i 'timelapse|nginx|postgres|crush|ftp|ollama|openwebui|fail2ban|sftp'
ps aux | egrep -i 'timelapse|nginx|postgres|crush|ftp|ollama|open-webui|fail2ban|sftp|uvicorn|syslog'
```

## Production gate

En Mac Headend må ikke godkendes til production, før:

- alle `Unknown` porte er klassificeret
- CrushFTP owner/ports/update policy er dokumenteret
- TimeLapse-owned porte er reserveret
- nginx/reverse proxy ownership er besluttet
- co-resident software er registreret som external dependency eller flyttet væk
- TimeLapse Pro er flyttet væk fra `80`, `443`, `21`, `22` og `8080`, medmindre der findes en eksplicit godkendt exception
