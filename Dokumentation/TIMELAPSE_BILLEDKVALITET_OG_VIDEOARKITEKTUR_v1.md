# TimeLapse Pro - billedkvalitet og videoarkitektur v1

Dato: 2026-07-16  
Status: Målarkitektur med implementeret første sikkerhedstrin

## Målsætning

TimeLapse Pro skal producere stabile, fotografisk konsistente videoer fra lange forløb uden at ændre eller slette originalbilleder. Automatisk kamerastyring skal være konservativ, sporbar og reversibel. Efterbehandling skal ske på kopier og kunne reproduceres fra et rendermanifest.

## Fotofaglige principper

1. **Stabil geometri før kosmetik.** Kamera, brændvidde, fokus og beskæring låses. Små mekaniske forskydninger registreres før deflicker og skarphed.
2. **Eksponering er en tidsserie.** Ét mørkt eller lyst billede må ikke ændre kameraet. Ændringer kræver vedvarende afvigelse, hysterese, begrænset EV-hastighed og særskilt håndtering af dag, tusmørke og nat.
3. **Højlys beskyttes.** Middellysstyrke alene er utilstrækkelig. Histogrampercentiler og klippede højlys vægtes, især ved direkte sol og refleksioner.
4. **Hvidbalance må ikke jage.** Automatisk hvidbalance kan give farveflimmer. Fast profil eller kontrolleret tidsudjævning foretrækkes; autonome WB-ændringer kræver eksplicit policy.
5. **Fokus behandles separat.** Lav skarphed kan skyldes motivbevægelse, regn, tåge, snavs, vibration eller forkert fokus. EV må ikke bruges som svar på fokusfejl.
6. **Originaler er immutable.** Denoise, stabilisering, deflicker, skarphed, farvestyring og overlays udføres kun i renderpipelinen.
7. **Master før leverance.** Der bør kunne genereres en høj-kvalitets master og separate web-/kundeprofiler uden at genbehandle billederne forskelligt.

## Edge QA og automatisk kontrol

### Implementeret

- skarphed globalt, centralt, perifert og i 3x3-zoner,
- middelværdi, percentiler, dynamikområde og klippede skygger/højlys,
- farvestik, saturation, direkte sol/refleksion og mulig linseobstruktion,
- QA-sidecar pr. billede,
- alarmgrundlag ved dårlig kvalitet,
- policybegrænset eksponeringskompensation,
- fail-closed kontrol: fokus, WB, sol/refleksion, vedligehold og schedule-fund kan ikke falde tilbage til en simpel én-billed EV-regel.

### Næste kontroltrin

1. Gem en tidsserie pr. kamera med histogrampercentiler, EV, ISO, blænde, lukkertid, WB, fokusmålinger og vejrtype.
2. Kræv mindst tre konsistente, høj-konfidens observationer før EV ændres.
3. Begræns både EV pr. trin og EV pr. time; implementér anti-windup ved min/max.
4. Gem controller-state atomisk på Edge, så genstart ikke nulstiller eller duplikerer en korrektion.
5. Sammenlign med samme lokale soltid fra tidligere dage for at skelne vejromslag fra kameradrift.
6. Udfør daglig fokus-test i et konfigureret lav-risiko-vindue. Fokus shift må ikke køre under normal capture uden recovery-plan.
7. Kræv menneskelig godkendelse af en ny fokusposition, indtil Edge-AI er valideret mod et mærket datasæt.

Nikon Z30 understøtter fokus shift med op til 300 billeder. Nikon anbefaler lille step width (højst 5), eksponeringslås ved stabile forhold og passende blænde. Funktionen skal derfor modelleres som et kontrolleret testjob, ikke som et almindeligt enkeltbillede.

## Headend renderpipeline

### Implementeret i dette trin

- frame-ID'er valideres mod valgt device og brugerens adgang,
- filnavn kan ikke foretage path traversal,
- fps, codec, opløsning, beskæring og øvrige valg valideres fail-closed,
- valgte FFmpeg-filtre kontrolleres mod den installerede binær før jobbet startes,
- valgfri let/kraftig stabilisering med `deshake`,
- valgfri let/kraftig temporal støjreduktion med `nlmeans`,
- valgfri let/kraftig skarphed med `unsharp`,
- filterrækkefølge: stabilisering, deflicker, denoise, skarphed,
- UI-valg for de nye behandlinger,
- “Dato/tid” bliver ikke længere tavst erstattet af forløbet videotid.

Standardprofilen udfører ingen tabspræget kosmetisk behandling. Det gør output reproducerbart og undgår overbehandling.

### Næste rendertrin

1. **ECC-registrering:** brug OpenCV `findTransformECC` mod en robust reference/nøgleframes til subpixel-justering af den statiske scene. Begræns transformationen og alarmér ved stort kameraskift.
2. **Scene-aware deflicker:** normalisér en robust luminanskurve, men bevar reelle dag/nat- og vejrovergange. FFmpegs generelle `deflicker` er et tilvalg, ikke den endelige analyse.
3. **Farvestyring:** normalisér dokumenteret inputprofil til Rec.709/sRGB med eksplicit full/limited range og testcharts. Undgå implicitte konverteringer.
4. **Rigtige capture-timestamps:** generér ASS-overlay fra `captured_at`. Det aktuelle FFmpeg-build mangler `drawtext` og `subtitles`; build/provenance skal ændres og licensrapporteres før funktionen aktiveres.
5. **Masterprofil:** ProRes 422 eller FFV1-master vurderes i forhold til lagring, afspilning og licens. H.264 er webprofil; H.265 er effektiv leveranceprofil, men kræver særskilt patent-/codec-review.
6. **Rendermanifest:** gem frame-hashes, capture-tider, filterversioner, parametre, FFmpeg build string og outputhash sammen med videoen.
7. **Persistente jobs:** flyt jobstatus fra RAM til database, begræns samtidige jobs og indfør eksplicit retention for afledte videoer. Originalbilleder må aldrig omfattes.
8. **Preview:** lav et kort lavopløst proof før dyr 4K-render og vis estimeret tid/plads.

Optical-flow frame interpolation (`minterpolate`) anbefales ikke som standard. Nye kraner, mennesker, køretøjer og bygningsdele kan skabe syntetiske artefakter og forfalske dokumentarisk evidens. Funktionen kan senere tilbydes som tydeligt mærket kreativ eksport.

## Renderprofiler

| Profil | Formål | Standardbehandling |
|---|---|---|
| Evidens | Dokumentation/QA | Ingen kosmetisk behandling, hashes og manifest |
| Balanceret | Normal kundevideo | Let ECC, scene-aware deflicker, let denoise/skarphed |
| Web | Browser/portal | Balanceret + H.264, `faststart`, 1080p/4K |
| Master | Efterbehandling/arkiv | Høj bitdybde/intraframe eller lossless efter kapacitetsreview |
| Kreativ | Marketing | Ken Burns/fades og eventuel interpolation, tydeligt deklareret |

## Gratis/open source værktøjer

- **FFmpeg:** encoding, deflicker, denoise, skarphed, farverum og leverance. Det installerede Headend-build er GPL-konfigureret og uden `nonfree`.
- **OpenCV:** QA, histogrammer og ECC-registrering. OpenCV 4.5+ er Apache-2.0.
- **libgphoto2/gphoto2:** kamerakontrol. Bibliotek og CLI har forskellige LGPL/GPL-forpligtelser.
- **ExifTool:** kandidat til robust metadataudtræk; må først tilføjes efter SBOM-, licens- og performance-review.
- **LibRaw/RawTherapee CLI:** kandidater til NEF/RAW-flow; bør kun indføres med fast versionsprofil, sidecar-parametre og reproducerbarhedstest.

## Acceptkriterier

- Ingen autonom ændring på baggrund af ét billede.
- Ingen fokus/WB-ændring uden separat policy og evidens.
- Ingen filteroption må accepteres, hvis den installerede renderer mangler filteret.
- Samme inputmanifest og toolchain skal give funktionelt identisk output.
- Renderen må ikke kunne læse frames fra anden tenant/device.
- Originalbilleder må ikke ændres eller slettes af QA/render.
- 24-timers og 30-dages datasæt skal kontrolleres visuelt for pumping, crop-jitter, farveskift og fokusdrift.
- Før/efter-metrics og repræsentative videoer gemmes som release-evidens.

## Autoritative kilder

- Nikon Z30 fokus shift: https://onlinemanual.nikonimglib.com/z30/en/09-03-33.html
- Nikon Z30 flicker reduction: https://onlinemanual.nikonimglib.com/z30/en/09-03-20.html
- Nikon Z30 video flicker/shutter: https://onlinemanual.nikonimglib.com/z30/en/09-04-17.html
- FFmpeg filterdokumentation: https://www.ffmpeg.org/ffmpeg-filters.html
- FFmpeg legal/licens: https://www.ffmpeg.org/legal.html
- OpenCV ECC: https://docs.opencv.org/master/dc/d6b/group__video__track.html
- OpenCV licens: https://opencv.org/license/
