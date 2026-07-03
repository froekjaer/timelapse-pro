# Codex - TimeLapse Pro brugermanual

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Maalgruppe:** Kunde, site manager, projektleder og almindelig bruger.

## 1. Login

1. Gaa til TimeLapse Pro login.
2. Indtast brugernavn/e-mail og adgangskode.
3. Brug MFA/WebAuthn hvis det er aktiveret.
4. Efter login vises de kunder, sites og kameraer, din rolle giver adgang til.

Public website `www.timelapse-pro.dk` skal kun vaere informationssite. Selve produktet tilgaas via `backend.timelapse-pro.dk`.

## 2. Dashboard

Dashboardet giver overblik over:

- aktive kameraer
- seneste billeder
- online/offline/stale status
- uploadstatus
- billedkvalitet
- alarmer
- relevante tags og seneste haendelser

Hvis et kamera staar som stale/offline, har Headend ikke faaet frisk heartbeat fra Edge.

## 3. Billeder og galleri

1. Vaelg kunde/site/kamera.
2. Se thumbnails i galleriet.
3. Klik paa et billede for fuld visning.
4. Filtrer paa dato, tags, kvalitet eller lysforhold.

Thumbnails skal normalt vaere forudgenereret. Hvis der mangler thumbnails, kan administrator starte postprocessing.

## 4. Tags og soegning

Backend gemmer canonical tags paa engelsk. UI viser danske labels via oversaettelsestabel.

Eksempler paa soegning:

- dagtimer
- klart sollys
- ingen direkte sol i linsen
- hoej skarphed
- regn eller daarligt lys
- brugbare billeder til timelapse-video

AI-tags er hjaelpemetadata. Kritiske rapporter boer verificeres manuelt.

## 5. Billedkvalitet

Systemet kan vise:

- blur/fokus-score
- lys/eksponering
- mulige kameraafvigelser
- uploadstatus
- analyse-/tagstatus

Gentagne kvalitetsproblemer skal sendes til administrator, der kan bruge LAB-funktionen.

## 6. Timelapse-video

Planlagt brugerflow:

1. Vaelg kamera.
2. Vaelg datointerval.
3. Filtrer paa tags, kvalitet og lysforhold.
4. Generer video.
5. Download resultat.

Status pr. 2026-06-23: krav kendt, men ikke fuldt production-klar.

## 7. Rapporter

Paa sigt skal kunder kunne faa rapporter for:

- SABSA
- ISO 27001
- IEC 62443
- NIS2
- CRA
- GDPR

Rapporter kraever frisk evidence fra CMDB, updates, backup, adgangslogs og site-konfiguration.

## 8. Fejl og support

Kontakt administrator hvis:

- du ikke kan logge ind
- du ser forkerte kundedata
- et kamera er offline/stale
- der mangler billeder
- thumbnails ikke vises
- tags virker aabenlyst forkerte
- billedkvaliteten er faldet

Forkert adgang til kundedata skal behandles som sikkerhedshaendelse.

