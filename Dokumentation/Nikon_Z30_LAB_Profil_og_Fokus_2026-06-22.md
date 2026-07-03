# Nikon Z30 LAB profil og fokusstyring

Dato: 2026-06-22

## Beslutning

TimeLapse Pro skal skelne mellem:

- Generiske TimeLapse-intents, fx `ISO`, `whitebalance`, `aperture`, `focus`.
- Kameratype-profiler, fx `Nikon Z30`, der oversaetter intent til konkrete gphoto2 paths og vaerdier.

Det betyder, at global/kunde/site/kamera config kan sige "ISO=200", men driveren maa kun anvende det hvis den aktive kameraprofil har en gyldig mapping.

## Implementeret

### Nikon Z30 profil

`edge/camera/drivers/gphoto2_driver.py` har en `Nikon Z30` profil med:

- autofocus
- remote focus
- liveview
- movie capability flag
- profil-specifik mapping for ISO, shutter, aperture, whitebalance, colorspace og imageformat
- action paths for autofocus, manual focus, viewfinder og movie

### LAB UI

LAB viser nu:

- Aktiv kamera-profil
- Generiske metadata-stier
- Profil-specifik mapping, markeret med profilnavn
- Remote focus panel
- Autofocus test
- Focus slice test
- Edge focus quality test

Dropdowns for focus bruger kameraets faktiske gphoto2 choices. `Unknown` choices filtreres fra UI.

### Edge analyse

Foerste Edge-analyse er deterministisk og lokal:

- blur score via Laplacian variance
- brightness mean
- quality flag

Det er bevidst valgt som foerste trin, fordi fokusjustering ikke boer bero paa en generativ model alene.

## Flow

1. Admin starter LAB mode.
2. Edge holder kamera-relay aktivt og forbinder til kamera.
3. Admin henter kamera-parametre.
4. Edge sender parametre og aktiv profil til headend.
5. LAB UI viser remote focus muligheder ud fra kameraets egne choices.
6. Admin kan koere:
   - step focus
   - autofocus test
   - focus slice
   - Edge focus test
7. Edge poster resultat til headend som `lab_result`.

## Video-streaming

Eksisterende reverse SSH tunnel kunne kun forwarde een port, typisk SSH:

- `remote_port -> localhost:22`

Tunnel-manageren understotter nu `extra_forwards`, fx:

```yaml
ssh_tunnel:
  enabled: true
  remote_port: 2201
  local_port: 22
  extra_forwards:
    - name: lab_video
      remote_port: 2301
      local_port: 8090
```

Naeste skridt er at starte en lokal LAB video/MJPEG service paa Edge, fx `127.0.0.1:8090`, og proxy den gennem headend/UI.

## Naeste arbejde

- Implementere Edge LAB video service.
- Tilfoeje UI stream-status: tunnel aktiv, remote video port, stream aktiv.
- Lave scheduler for daglig auto-focus test.
- Gemme fokus-test historik i CMDB, saa drift kan se trend over tid.
- Vurdere let lokal AI model paa Orange Pi 4 Pro som supplement til OpenCV-metrikker.

