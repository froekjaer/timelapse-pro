# Mac Headend port migration plan

Dato: 2026-06-05
Status: Forslag til arkitekturbeslutning før live ændring

## Beslutning

TimeLapse Pro skal flyttes væk fra almindelige/co-resident porte på Mac Headend:

- 80
- 443
- 21
- 22
- 8080

Formålet er at undgå konflikt med eksisterende og fremtidige applikationer som fx CrushFTP, Apple/macOS services og kundeinstalleret software.

## Vigtig præcisering

Almindelig DNS kan ikke i sig selv oversætte:

```text
https://timelapse.froekjaer.dk:443 -> origin:18443
```

DNS peger på en host/IP. Port-routing kræver en proxy, tunnel, load balancer, firewall/NAT eller en browser/protokol der respekterer særlige records. Almindelige browserkald til `https://host` bruger port 443, medmindre brugeren skriver en port i URL'en.

Cloudflare kan dog løse problemet med:

1. **Cloudflare Tunnel**
   - Public hostname peger til Cloudflare.
   - `cloudflared` på Mac Headend laver outbound forbindelse.
   - Cloudflare forwarder til lokal service, fx `https://127.0.0.1:18443`.
   - Kræver ingen inbound 80/443 på Mac/router.

2. **Cloudflare Origin Rules**
   - Browser bruger stadig `https://timelapse.froekjaer.dk`.
   - Cloudflare modtager 443.
   - Cloudflare sender request videre til origin på en anden destination port, fx `18443`.
   - Kræver at origin-porten er reachable fra Cloudflare.

## Anbefalet model

Primær anbefaling:

```text
Cloudflare Tunnel -> Mac Headend localhost/private port
```

Begrundelse:

- Ingen inbound public 80/443 på Mac Headend.
- Mindre risiko for portkollision med CrushFTP.
- Mac firewall/router kan holdes lukket for TimeLapse web.
- Public hostname kan stadig være `https://timelapse.froekjaer.dk`.
- Samme model kan bruges til `timelapse.hyldager.net`.
- Kunde-ejede Headends kan selv køre tunnel eller importere samme model.

Fallback:

```text
Cloudflare Origin Rule -> origin port 18443
```

Bruges hvis Tunnel ikke ønskes, eller hvis en kunde/hostingmodel kræver direkte origin.

## Foreslået portmodel

TimeLapse Pro skal bruge et samlet non-standard portområde, så det er let at firewall'e og dokumentere.

| Formål | Ny port | Binding | Kommentar |
|---|---:|---|---|
| TimeLapse public HTTPS origin/nginx | 18443 | `127.0.0.1` med Tunnel, ellers specifik LAN/IP | Erstatter 443 |
| TimeLapse HTTP redirect/ACME | ingen eller 18080 | `127.0.0.1` | Ikke nødvendig ved Tunnel/Cloudflare TLS |
| Headend API intern | 18000 | `127.0.0.1` | Erstatter public 8000 |
| OpenWebUI intern | 18081 | `127.0.0.1` | Erstatter 8080 |
| PostgreSQL | 15432 | `127.0.0.1` | Valgfrit; kan blive 5432 hvis ingen konflikt |
| SIEM/syslog receiver | 15514 | `127.0.0.1` eller privat interface | Erstatter 5514 hvis ønsket |
| SFTP/ingress | 12222 | specifik interface | Må ikke bruge 21/22 |
| Ollama | 11434 | `127.0.0.1` | Kan bevares, da den er lokal og standard for Ollama |

Princip:

- Public 80/443 ejes ikke af TimeLapse på Mac’en.
- TimeLapse nginx ejes stadig af TimeLapse, men lytter på `127.0.0.1:18443`.
- Cloudflare bliver public edge.
- CrushFTP og anden co-resident software må ikke ændres af TimeLapse.

## Hostname routing

### `timelapse.froekjaer.dk`

Cloudflare route:

```text
https://timelapse.froekjaer.dk -> https://127.0.0.1:18443
```

Hvis Tunnel:

```yaml
ingress:
  - hostname: timelapse.froekjaer.dk
    service: https://127.0.0.1:18443
  - hostname: openwebui.froekjaer.dk
    service: https://127.0.0.1:18443
```

Hvis Origin Rule:

```text
hostname == timelapse.froekjaer.dk
destination port override = 18443
```

### `timelapse.hyldager.net`

Samme model:

```text
https://timelapse.hyldager.net -> https://127.0.0.1:18443
```

Hvis begge domæner peger på samme Headend, skal nginx have begge `server_name` værdier og certifikat/TLS-modellen skal være afklaret.

## TLS-model

Anbefaling ved Cloudflare Tunnel:

- Cloudflare håndterer public TLS.
- Origin kan bruge lokal TLS eller HTTP på localhost.
- Hvis origin bruger HTTPS, skal certifikatnavn/SNI være dokumenteret.

Anbefaling ved Origin Rule:

- Origin-port 18443 skal bruge valid TLS.
- Cloudflare skal validere origin certifikat, helst Cloudflare Origin Certificate eller offentligt certifikat.
- Origin firewall bør kun tillade Cloudflare IP-ranges til 18443.

## Migration uden nedetid

1. Klassificer alle ukendte porte på Mac Headend.
2. Beslut Tunnel vs Origin Rule.
3. Tilføj ny nginx listener på `18443` uden at fjerne `80/443`.
4. Test lokalt:

```bash
curl -k https://127.0.0.1:18443/
curl -k https://127.0.0.1:18443/api/auth/me
```

5. Konfigurer Cloudflare route til ny origin port.
6. Test udefra med `timelapse.froekjaer.dk`.
7. Opdater Headend `base_url` hvis nødvendigt.
8. Opdater Edge config/policy hvis hostnames ændres.
9. Når alt virker: fjern TimeLapse nginx fra `80/443`.
10. Reservér `80/443` til anden app eller lad dem være ubrugte.

## Pre-flight gate

En release eller platformændring må ikke ændre TimeLapse portmodel uden:

- dokumenteret port ownership
- LAB-test med samme portmodel
- Cloudflare route test
- rollback-plan
- change ticket

Hvis TimeLapse opdager at `80`, `443`, `21`, `22` eller `8080` bruges af TimeLapse i production, skal deployment markeres som non-compliant, medmindre der findes en eksplicit godkendt exception.

## Åbne beslutninger

1. Skal vi vælge Cloudflare Tunnel som standard for alle Mac Headends?
2. Skal kunde-ejede Headends kunne vælge Origin Rule i stedet?
3. Skal TimeLapse Headend overhovedet have lokal HTTPS, eller er HTTP på `127.0.0.1:18080` nok bag Tunnel?
4. Skal SFTP/ingress flyttes fra `22222` til `12222` nu eller senere?
5. Skal PostgreSQL blive på `5432` lokalt, eller flyttes til `15432` for ensartethed?
