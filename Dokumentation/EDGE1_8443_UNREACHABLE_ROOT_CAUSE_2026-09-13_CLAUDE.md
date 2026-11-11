# Edge1 (`192.168.86.134:8443`) uopnåelig — netværks-evidens

**Forfatter:** Claude Sonnet 5, 2026-09-13
**Metode:** Read-only netværksundersøgelse fra denne sessions sandbox (samme
LAN som Peters Mac, port-scanning/ping/curl/openssl/ssh-keyscan). **Ingen
SSH-nøgleadgang** til nogen Edge findes i denne sandbox — tidligere sessioners
"verificeret via SSH"-arbejde (fx dpkg-undersøgelsen 2026-09-11) er udført fra
et andet miljø med nøgleadgang, ikke herfra. Denne undersøgelse er derfor
netværks-evidens, ikke enhedens egne logs.

## Verificeret

- `192.168.86.134` svarer på ICMP (ping OK, ~10-16 ms, ttl=64) og har SSH
  åben (port 22, `SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.18`).
- Port 8443 på `.134` giver **"Connection refused"** — en aktiv TCP RST, ikke
  timeout. Der lytter intet på 8443 (eller noget rejecter eksplicit), ikke en
  drop/filter-timeout.
- Port 80 på `.134` svarer derimod **HTTP 200 med `Server: lighttpd/1.4.74`
  og indhold der identificerer sig selv som en Pi-hole blocking-page**
  (`<title>● 192.168.86.134</title>`, `/pihole/blockingpage.css`,
  `/admin/img/logo.svg`). **`.134` er i dag en Pi-hole-enhed, ikke en
  TimeLapse Edge.**
- mDNS-navnet `timelapse0101.local` peger (i denne sessions lokale
  mDNS-cache) også på `.134` — men da `.134` beviseligt er Pi-hole lige nu,
  er dette enten en forældet/uigenopfrisket cache-post eller et navn som
  Pi-hole-enheden nu selv svarer på; det er **ikke** bekræftende bevis for at
  Edge1 nogensinde var her, kun at en mDNS-post med det navn engang fandtes.
- Fuld ping-sweep af `192.168.86.0/24` fandt 35 aktive hosts. Alle blev
  tjekket for port 8443. Kun to svarer med en TimeLapse-relateret
  TLS-identitet: `192.168.86.144` (Edge2, cert-SAN `tl-modbaggarddlvc.local`,
  `192.168.42.1`) og `192.168.86.102` (Headend, cert-CN
  `backend.timelapse-pro.dk`, nginx, server timelapse-ui). **Ingen anden
  host i hele /24-nettet svarer med en TimeLapse Edge-identitet på 8443.**
  De øvrige 8443-svar (`.108`, `.116`, `.122`, `.163`) er Apple-enheder
  (`pcsync-https`-banner, AirPlay/Continuity), ikke TimeLapse.

## Konklusion (evidensbaseret, ikke gættet)

Dette er **ikke** en service-, firewall- eller konfigurationsfejl på selve
Edge1 — der er ganske enkelt **ingen enhed med en TimeLapse Edge-identitet
synlig noget sted på dette /24-net lige nu, ud over Edge2**. IP'en `.134`
er tydeligvis blevet genudlejet af DHCP til en Pi-hole-enhed siden Edge1
sidst blev set der (jf. `HANDOVER_LOG.md`-linje der beskriver `.134`s
TimeLapse-certifikat som historisk observation).

**Mest sandsynlige forklaringer, i rækkefølge:**
1. Edge1 er slukket, frakoblet eller ude af drift på dette netværkssegment
   (kan ikke skelnes fra denne vinkel — hverken ping, ARP eller port-scan
   viser et TimeLapse-lignende device andetsteds i /24'et).
2. Edge1 er tilsluttet et andet netværkssegment (fx et separat VLAN, en
   anden Wi-Fi-router, eller kun nået via BT-PAN), som ikke er synligt fra
   denne Mac's `en1`-interface.

**Ikke understøttet af evidensen:** en simpel firewall/iptables- eller
`timelapse-totp.service`-fejl specifikt på Edge1 — sådan en fejl ville typisk
stadig vise enheden med *en eller anden* identificerbar TimeLapse-relateret
respons (fx et TLS-håndtryk der failer på anden vis, eller port 22 der viser
en Edge-relateret banner/nøgle-fingeraftryk); her er der intet TimeLapse-
device at finde overhovedet i det scannede rum.

## Hvad der mangler for en endelig afgørelse

Denne undersøgelse er begrænset til hvad der er synligt fra denne sandbox'
netværksplacering. En endelig afgørelse kræver et af følgende, som Peter må
foretage (ingen af delene kan gøres herfra uden nøgleadgang):
1. Fysisk tjek af Edge1: er den tændt, har den strøm/netværkskabel, hvilken
   IP rapporterer den selv (fx via en tilsluttet skærm/HDMI eller
   `ip addr` over et andet adgangsspor)?
2. Opslag i Headend's egen enhedsstatus/CMDB (fx `device_inventory`-tabellen
   eller `/api/devices`) for sidste kendte heartbeat/IP for Edge1's device-ID
   — Headend kan formentlig svare autoritativt på hvornår enheden sidst var
   online og med hvilken IP, uafhængigt af denne netværkssweep.
3. Hvis Edge1 findes på et andet segment: en tilsvarende port-scan/curl
   derfra.
