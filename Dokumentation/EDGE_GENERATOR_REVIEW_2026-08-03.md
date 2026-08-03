# Edge Generator Review - 2026-08-03

## Status

Den fysiske generator for `orangepi4pro` er gennemgået og testet som ARM64-container.
Den flashbare pipeline afviser fortsat korrekt et dirty eller usigneret release-worktree.
Det er en nødvendig release-kontrol; en endelig `.img.gz` skal derfor bygges fra et
rent, QA-godkendt og GPG-signeret release-tag.

### Evidens

- Dockerfile-forhåndskontrol: godkendt.
- ARM64 runtime-image: bygget som `timelapse-edge:generator-qa`.
- Runtime-Python: `agent.py`, `bootstrap_agent.py`, `totp-service.py` og
  `bootstrap_cli.py` kompilerer i ARM64-imaget.
- Målrettede generator-/releasekontrakter: 40 bestået.
- UI-build: godkendt.

## Med i et flashbart Orange Pi 4 Pro-image

- Ubuntu Jammy leverandør-base-image med hardware-specifik bootloader/kernel.
- TimeLapse Edge-agent, capture-buffer, upload, CMDB/inventory, diagnostik,
  kamera-HAL og gphoto2-drivere for Nikon og Canon.
- Lokal HTTPS-serviceportal på port 8443. Den lytter på alle interfaces:
  Bluetooth PAN, WiFi og Ethernet.
- En unik, kamera-bundet lokal nødadgang (TOTP), genereret ved flashable build.
  Ingen delt fabrikshemmelighed kan anvendes.
- I Kamera-visningen kan en autoriseret administrator eller on-site-tekniker se
  QR-koden og vælge **Tilføj i authenticator**. Handlingen åbner den samme
  standardiserede `otpauth`-registrering på mobiltelefonen; TOTP-hemmeligheden
  vises ikke som almindelig tekst.
- Bluetooth PAN, pairing-agent, captive firewall og TOTP-service som aktive
  systemd-enheder fra første boot.
- Lokalt netværksværktøj, WiFi-opsætning, GPS/gpsd, camera-tooling,
  reverse-tunnel-klient og bootstrap CLI.
- Python runtime med de nødvendige afhængigheder for Edge QA og billedanalyse.
- Bootstrap-token, kun når det eksplicit vælges ved build.
- WiFi-konfiguration, kun når den eksplicit vælges ved build.
- Device SSH-nøgle, tunnelport og Headend public key, kun når et forberedt
  kamera vælges ved build.
- Manifest, SHA-256, SBOM og GPG-signatur for den endelige artifact.

## Ikke med i image

- API-tokens, tidligere bootstrapfiler, tidligere Edge-konfiguration, keys,
  caches og journal-cursors fra udviklingsarbejdsmappen.
- Python bytecode, testcaches og macOS `Icon`-filer.
- AI-testpakker, træningskode og trænings-manifester.
- NPU C++-kilde og leverandørkilde. En kompileret, valideret NPU-komponent skal
  leveres som et separat signeret artifact, når den er moden.
- Offline authoring-/dataset-værktøjer. Kun `bootstrap_cli.py`, der anvendes af
  den lokale serviceportal, bevares.
- Historiske billeder, kundedata og brugeradgangskoder.
- Ingen direkte internetbaseret apt-, pip- eller GitHub-opdatering på Edge.

## Lokal serviceadgang

- Buildformularen har et eksplicit R&D-valg for interaktiv lokal terminal,
  som er markeret for den første testenhed.
- Headend kan efter enrollment slå terminalen til eller fra under
  `Systemadministration -> Lokal serviceadgang`.
- Terminalen er beskyttet af den lokale HTTPS-session og indeholder OpenSSH
  klienten. En fremtidig destinationsliste skal være Headend-styret og bruge
  pinned host keys; vilkårlige værter må ikke åbnes.
- Brugerstyring har nu capability `On-site idriftsættelse og service`, adskilt
  fra primær RBAC-rolle og kundeafgrænsning. Capability kontrolleres i
  Headendens eksisterende technician-auth bekræftelse.

## Resterende før første endelige flash

1. Færdiggør QR/MFA-bro i den eksisterende lokale HTTPS-portal, så en tekniker
   logger ind med sin normale Headend-konto og capability. Lokal TOTP bevares
   som auditeret offline nødadgang.
2. Kør flashable build fra rent, signeret tag med valgt bootstrap-token og den
   korrekte kamera-binding.
3. Flash fysisk testmedie, boot, og verificer Bluetooth, WiFi, Ethernet,
   enrollment, lokal portal, kamera, reverse tunnel og offline update-pull.
4. Godkend testresultatet før samme artifact eller release fremmes til staging
   eller produktion.
