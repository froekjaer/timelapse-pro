# TimeLapse Pro - Global Config og kamera-binding

Dato: 2026-06-22

## Formaal

Konfiguration skal kunne styres ensartet paa fire lag:

1. Global
2. Kunde
3. Site
4. Kamera-lokation

Lavere lag vinder over hoejere lag. Et kamera-lag skal derfor kunne overstyre site, kunde og global, uden at kopiere hele konfigurationen.

## Aktiv model

Edge er fysisk hardware. Kamera-lokation er den logiske installation.

Det betyder:

- `devices` beskriver fysisk Edge/node og dens seneste runtime-status.
- `cameras` beskriver den stabile kamera-lokation, eksempelvis "Kamera 1" paa et site.
- `device_assignments` binder en fysisk Edge til en logisk kamera-lokation.
- Billeder, konfiguration og historik boer forstaas ud fra kamera-lokationen, saa Edge kan udskiftes uden at miste sammenhaeng.

Aktiv Edge pr. 2026-06-22:

- Device: `TL-C87FF9587CA0`
- Kunde: `Froekjaer`
- Site: `Nordre Villavej 17c`
- Kamera-lokation: `Kamera 1`

## Config-resolution

Backend endpoint:

- `GET /api/admin/config-resolution`

Parametre:

- `customer_id`
- `site_id`
- `camera_id`
- `device_id`

Hvis `device_id` angives, finder backend aktiv `device_assignment` og resolver den til kamera-lokationen.

Responsen indeholder:

- `context`: valgt kunde/site/kamera/device
- `layers`: global, customer, site, camera med hvert lags direkte config
- `effective_config`: den endelige merge
- `fields`: felt-for-felt provenance

Hvert felt viser:

- global vaerdi
- kunde override
- site override
- kamera override
- effektiv vaerdi
- hvilket lag der vandt
- om effektiv vaerdi afviger fra global

## Gem af overrides

Backend endpoint:

- `PUT /api/admin/config-overrides/{layer}/{entity_id}`

Lag:

- `global`
- `customer`
- `site`
- `camera`

Payload:

```json
{
  "mode": "merge",
  "config_overrides": {
    "camera": {
      "power_mode": "relay"
    }
  }
}
```

`null` betyder "fjern override og arv igen" i merge-mode.

Eksempel:

```json
{
  "mode": "merge",
  "config_overrides": {
    "camera": {
      "iso": null
    }
  }
}
```

## UI

Global Config UI viser nu:

- valg af kunde/site/kamera-lokation
- hvilket lag der redigeres
- direkte vaerdi pr. lag
- effektiv vaerdi
- farvemarkering:
  - groen: sat paa det aktuelle/vindende lag
  - gul: afviger fra global default
- dynamiske parametre, ogsaa selvom de ikke er navngivet i UI-listen

CameraPage gemmer kamera-konfiguration paa `cameras.config`, ikke paa `devices`.

Hvis en Edge mangler kamera-lokation, kan UI oprette og binde en ny logisk kamera-lokation direkte fra kamera-siden.

## Governance

Denne model passer bedre til SABSA, IEC 62443, CRA og ISO 27001 fordi:

- ansvar og ejerskab kan placeres paa kunde/site/kamera
- Edge-udskiftning ikke aendrer konfigurationsautoritet
- config-overrides er sporbare pr. lag
- fysisk hardware og logisk aktiv adskilles
- laveste noedvendige scope kan anvendes ved aendringer

## Verifikation 2026-06-22

Kontrolleret:

- Headend starter efter aendring.
- Frontend bygger uden TypeScript-fejl.
- `TL-C87FF9587CA0` resolver til alle fire lag.
- `camera.power_mode` arves fra global med vaerdi `relay`.
- `camera.relay_gpio_pin` arves fra global med vaerdi `356`.
- `sftp.remote_base` kommer fra site-laget og peger paa `/Volumes/data-fast/timelapse-incoming/sftp_nvj17c/data`.

