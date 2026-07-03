# TimeLapse Pro - Edge lokal provisioning

**Dato:** 2026-06-03  
**Scope:** Lokal netværksopsætning før Edge har stabil Headend-forbindelse.

## Princip

Edge må kun konfigureres lokalt for de minimumsparametre der kræves for at skabe kontakt til Headend:

- Headend API URL
- bootstrap token
- WiFi
- Ethernet
- 4G USB modem
- connectivity preference

Al rigtig driftskonfiguration, kameraopsætning, RBAC, kunde/site binding, capture schedule og update-policy skal fortsat komme fra Headend.

## CLI

På Edge:

```bash
cd /opt/timelapse
sudo edge/tools/bootstrap_cli.py
```

Status uden interaktiv menu:

```bash
sudo edge/tools/bootstrap_cli.py --status
sudo edge/tools/bootstrap_cli.py --test-headend
```

CLI'en skriver kun til:

- `/opt/timelapse/edge/bootstrap.yaml`
- `/opt/timelapse/edge/local_network.yaml`
- NetworkManager profiler via `nmcli`

WiFi-password gemmes ikke i TimeLapse config. Det gives direkte til NetworkManager.

## Production-sikkerhedsgrænse

- Ingen WiFi-passwords via Headend `lab_command` i production.
- Ingen kamera-, tenant- eller schedule-konfiguration lokalt.
- Ingen lokal brugeradministration.
- Ingen local bypass af RBAC.
- Bootstrap token skal være tidsbegrænset eller engangsbrug når production provisioning-flowet er færdigt.

## Captive portal / AP-mode design

Når Edge ikke har fungerende netværk eller ikke kan nå Headend, kan den i fremtiden starte et midlertidigt provisioning access point.

Anbefalet SSID:

```text
TLP-<device_id>
```

Eksempel:

```text
TLP-TL-C87FF9587CA0
```

Anbefalet lokal webadresse:

```text
http://192.168.77.1/
```

Webfladen må kun tilbyde:

- vis device_id og netværksstatus
- sæt Headend URL
- indtast bootstrap token
- scan/tilslut WiFi
- sæt Ethernet DHCP/static
- sæt 4G APN
- test Headend forbindelse
- stop AP-mode når Headend er nået

## AP-mode sikkerhed

- AP-mode må kun være aktiv når Edge ikke har Headend-forbindelse, eller ved fysisk lokal trigger.
- SSID skal være device-specifikt, ikke kundespecifikt.
- AP-password skal være unikt pr. device og ikke afledt kun af device_id.
- Web UI skal være local-only, uden adgang til capture data, logs med secrets, kamera-liveview eller Headend tokens.
- AP-mode skal auto-timeout'e, fx efter 30 minutter.
- Når Edge bootstrapper korrekt mod Headend, skal AP-mode stoppes.

## Næste implementeringstrin

1. Installer CLI i Edge image/service package.
2. Tilføj systemd unit for provisioning AP-mode.
3. Tilføj minimal lokal webserver der genbruger samme netværksfunktioner som CLI.
4. Generér device-specifikt AP-password under provisioning og registrér kun fingerprint/evidence i Headend.
5. Tilføj Headend evidence: local provisioning started/stopped, network configured, bootstrap succeeded.
