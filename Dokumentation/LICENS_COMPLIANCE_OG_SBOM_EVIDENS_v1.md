# TimeLapse Pro - Licens-compliance og SBOM-evidens v1

Dato: 2026-07-16  
Status: Engineering review - ikke juridisk rådgivning

## Konklusion

Der er ikke fundet komponenter, som den automatiske policy klassificerer som direkte blokerede. Systemet kan dog ikke endnu erklæres endeligt licens-compliant ved redistribution, fordi konkrete notice-, source-offer-, copyleft- og codec-forpligtelser skal lukkes i releaseprocessen.

Aktuel status er derfor `REVIEW_REQUIRED`, ikke `NON_COMPLIANT` og ikke ubetinget `COMPLIANT`.

| Miljø | Komponenter | Permissive | Forpligtelser | Manuel review | Ukendt | Blokeret |
|---|---:|---:|---:|---:|---:|---:|
| Headend (Mac) | 479 | 415 | 41 | 22 | 1 | 0 |
| Edge TL-C87FF9587CA0 | 2187 | 508 | 708 | 634 | 337 | 0 |

Edge-tallene omfatter installerede Debian/Ubuntu-pakker. Mange Debian copyright-filer er ikke maskinlæsbare, hvilket forklarer de mange `unknown`/`review`-resultater; det er et evidensgab, ikke i sig selv et bevis på ulovlig anvendelse.

## Væsentlige fund

1. Headendens FFmpeg 8.1.1 er bygget med `--enable-gpl`, `libx264` og `libx265`. Den konkrete binær skal derfor behandles som GPL-build ved redistribution. TimeLapse Pro kalder FFmpeg som separat proces; det gør ikke automatisk TimeLapse Pro til GPL, men distribution af FFmpeg-binæren udløser selvstændige forpligtelser.
2. `--enable-nonfree` er ikke observeret. Der er derfor ikke fundet et FFmpeg-build, som FFmpeg selv markerer ikke-redistribuerbart.
3. Edgeens `gphoto2` oplyser selv GPL i versionsoutput; `libgphoto2` er separat LGPL. Begge kræver korrekt attribution og distributionshåndtering, hvis de leveres som del af Edge-imaget.
4. OpenCV 4.5+ er Apache-2.0 og kan anvendes kommercielt med de relevante notice-/license-forpligtelser.
5. Python- og npm-komponenter er dokumenteret fra det faktisk installerede metadata eller den committed lockfil. Installerede licens-/notice-filer hashes, så evidensen kan efterprøves.
6. H.264/H.265/HEVC kan have patent-/codecforpligtelser, som er adskilt fra open source-licensen. En ren open source-licensvurdering er derfor ikke tilstrækkelig til kommerciel distribution.

## Evidensmodel

Generator: `headend/tools/generate_license_compliance_report.py`

Den registrerer:

- komponentnavn, version, økosystem og Package URL (purl),
- deklareret/observeret licens,
- SHA-256 på installerede `LICENSE`, `COPYING`, `NOTICE` og copyright-filer,
- npm-integrity fra `package-lock.json`,
- Homebrew metadata fra den installerede formel,
- Debian package/version/architecture og `/usr/share/doc/<package>/copyright`,
- faktisk versions- og build-output fra FFmpeg, gphoto2, nginx, Ollama og PostgreSQL,
- policyklassifikation: `permissive`, `obligations`, `review`, `unknown`, `blocked`.

Fuld evidens ligger i:

- `Dokumentation/evidence/licenses/license-compliance-report.json`
- `Dokumentation/evidence/licenses/license-compliance-report.md`
- `Dokumentation/evidence/licenses/edge-TL-C87FF9587CA0/`

## Releasekrav

Før en release kan markeres licensgodkendt, skal følgende være automatiseret:

1. Generér licensrapport fra samme artifact/image, som skal signeres.
2. Stop promotion ved `blocked` eller `unknown` production dependencies.
3. Kræv dokumenteret disposition for alle `review`-fund.
4. Generér samlet Third Party Notices-fil med copyright og licenstekster.
5. Gem rapportens SHA-256 i artifactmanifest og change ticket.
6. Skeln mellem build/dev dependencies, runtime dependencies og eksterne services.
7. Arkivér korresponderende source code/source offer for distribuerede GPL/LGPL-komponenter, hvor licensen kræver det.
8. Udfør særskilt codec-/patentreview for distributionslande og kommerciel anvendelse.

## Autoritative kilder

- FFmpeg legal/licens: https://www.ffmpeg.org/legal.html
- OpenCV licens: https://opencv.org/license/
- SPDX 3.0.1 og SPDX Lite: https://spdx.dev/specifications/ og https://spdx.dev/learn/areas-of-interest/lite/
- CycloneDX Authoritative Guide: https://www.cyclonedx.org/guides/OWASP_CycloneDX-Authoritative-Guide-to-SBOM-en.pdf
- libgphoto2 upstream: https://github.com/gphoto/libgphoto2

## Begrænsning

Rapporten dokumenterer observerede tekniske fakta og en konservativ policyvurdering. Den må ikke bruges som en garanti for juridisk compliance uden, at organisationens ansvarlige for legal/IP har godkendt de åbne obligations-, codec- og distributionsspørgsmål.
