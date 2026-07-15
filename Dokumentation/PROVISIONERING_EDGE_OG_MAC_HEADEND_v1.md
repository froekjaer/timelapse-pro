# TimeLapse Pro - provisionering af Edge og Mac Headend v1

Dato: 2026-07-16

## Konklusion

Edge-imagebyggeren har nu en strengere releasekontrakt, men kræver fortsat en fysisk boot-/capture-/update-test på Orange Pi 4 Pro før anvendelse på en ny site. Mac Headend kan preflightes og stages fra en signeret, fastlåst Git-tag uden at ændre den eksisterende Mac. Automatisk apply er bevidst blokeret, indtil nginx er isoleret fra Homebrews globale konfiguration.

## Ny Edge

Imagebuildet skal:

- komme fra en ren commit for alle Edge-buildinputs,
- være GPG-signeret; hash-only fallback er ikke tilladt,
- indeholde OpenCV QA, gphoto2, autossh, GPS og Bluetooth runtime,
- indeholde de signerede Edge-, PAN-, BT-agent-, captive- og TOTP-units,
- fjerne lokale tokens, bootstrap-konfiguration, site-config og keys fra build context,
- registrere fuld commit, branch og Dockerfile SHA-256 i manifestet,
- hente senere ændringer gennem det signerede Headend update-flow.

Før første rigtige deployment skal et frisk `.img.gz` bestå:

1. Hash- og GPG-verifikation.
2. Boot fra SD og migration til NVMe efter Orange Pi-proceduren.
3. Ingen fabrikscredential eller R&D-sitekonfiguration i image.
4. Engangs-bootstrap og korrekt CMDB-enrollment.
5. Nikon Z30 detection, preview og full capture.
6. QA/OpenCV, thumbnail og upload.
7. Reboot-persistens for alle services.
8. Signeret test-update fra Headend med backup, receipt og rollback-test.
9. Netværksbootstrap via Ethernet/WiFi og lokal technician-adgang.

Afledte `.img.gz`/`.rootfs.tar.gz` kan slettes fra Backup > Edge ISO af super-admin. Manifest og audit-evidens bevares.

## Ny Mac Headend

Script: `deploy/install/bootstrap_headend_macos.sh`

### Preflight

Preflight er read-only og registrerer:

- macOS-version og arkitektur,
- alle lyttende TCP-services,
- eksisterende LaunchDaemons,
- installerede Homebrew-formler og versioner,
- om den valgte TimeLapse-port er ledig,
- at 21, 22, 80 og 443 forbliver urørte.

```bash
deploy/install/bootstrap_headend_macos.sh \
  --mode preflight \
  --config deploy/install/example-staging.conf \
  --report ~/Desktop/timelapse-imac-preflight.json
```

### Verificeret staging

Staging kræver en signeret Git-tag og den forventede fulde 40-tegns commit. Scriptet fetcher kun den konkrete tag, verificerer GPG-signaturen, sammenligner commit og checker detached/clean. Derefter køres den eksisterende installer kun som dry-run.

```bash
deploy/install/bootstrap_headend_macos.sh \
  --mode stage \
  --config deploy/install/example-staging.conf \
  --repo-url git@github.com:OWNER/timelapse-pro.git \
  --release-tag vX.Y.Z-staging.1 \
  --expected-commit FULL_40_CHARACTER_SHA \
  --destination /opt/timelapse/releases/FULL_40_CHARACTER_SHA
```

Scriptet udfører ikke `brew install`, `brew upgrade`, `softwareupdate`, databasemigration eller serviceændringer.

## Coexistence-krav

- TimeLapse må kun eje egne LaunchDaemons, mapper, database/schema og valgte porte.
- Eksisterende apps og OS-pakker inventariseres, men ændres ikke automatisk.
- CrushFTP og andre apps på 21/22/80/443 må ikke ændres.
- TimeLapse-nginx skal køre med egen config, prefix, pid, logs og LaunchDaemon. Den må ikke overskrive `/opt/homebrew/etc/nginx/nginx.conf`.
- Homebrew- og macOS-opdateringer skal efter bootstrap behandles som CMDB/change/update-emner; ingen ukritisk global opgradering.
- Staging og production skal have separate secrets, GPG-identitet, database, domæne og dataområder.
- Kundebilleder kopieres ikke til staging uden et godkendt, minimeret og eventuelt anonymiseret testdatasæt.

## Åben blocker

`deploy/install/install_headend.sh` skriver fortsat den globale Homebrew nginx-konfiguration. Den må derfor ikke køres med apply på iMac eller production, før nginx-delen er flyttet til en dedikeret TimeLapse-instans. Preflight/stage-scriptet håndhæver dry-run indtil dette er løst.

Når den blocker er lukket, skal apply-flowet tilføje:

1. Dedikeret service account og filrettigheder.
2. Dedikeret nginx-prefix/LaunchDaemon på den valgte port.
3. PostgreSQL-database uden at ændre andre databaser/clusters.
4. Migration backup, migration, healthcheck og rollback.
5. CMDB enrollment af Headend og initial SBOM/licensrapport.
6. Første signerede update-test gennem UI.
