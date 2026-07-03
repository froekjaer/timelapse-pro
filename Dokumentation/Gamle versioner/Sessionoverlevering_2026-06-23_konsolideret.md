# TimeLapse Pro - konsolideret sessionoverlevering 2026-06-23

Dette dokument samler to overleveringer:

- Codex-overlevering fra seneste session.
- Indsat overlevering i `/Users/peter/.codex/attachments/23c50c07-015b-4d99-9e63-7d0e640d36d5/pasted-text.txt`.

Formålet er at kunne starte en ny session uden at miste status, beslutninger eller kendte risici.

## Projektkontekst

- Repo: `/Users/peter/projects/timelapse-pro`
- `/Users/peter/projects` er symlink til `/Volumes/data-fast/peter-home/projects`.
- Headend: Mac mini, FastAPI, React/Vite UI, PostgreSQL.
- Edge: Orange Pi 4 Pro. Aktiv R&D/test-edge: `TL-C87FF9587CA0`.
- Ekstern disk: `/Volumes/data-fast`.
- Strategisk styring: Headend er update-authority. Edge må ikke hente updates direkte fra internet, GitHub eller apt repositories.
- Governance-ramme: SABSA, ISO 27001/27000, IEC 62443, CRA, NIS2, GDPR.

## Aktuel Git- og CI-status

Seneste commits på `main`:

```text
79581ac feat(edge): persist and list disk image artifacts
38beca3 fix(ci): clean macos icon metadata before deploy git ops
ae1c135 fix(ci): restart mac headend launch agent
3dd7d4d fix(ui): export thumbnail generation helper
7405e9f feat: vis danske tag-navne i kundevendt UI (thumbnails, lightbox, tag-søgning)
```

GitHub Actions status efter seneste commit:

```text
27987179806 completed success feat(edge): persist and list disk image artifacts
27986362176 completed success fix(ci): clean macos icon metadata before deploy git ops
27986158362 completed success fix(ci): restart mac headend launch agent
```

Pipeline er grøn:

- Python Syntax Check: OK.
- Web UI Build Check: OK.
- Signal Deploy: OK.
- Deploy to Mac mini Headend: OK.

Worktree er stadig dirty med mange lokale ændringer fra igangværende arbejde. Fortsæt med kirurgisk staging af relevante hunks. Revert ikke brede ændringer uden eksplicit aftale.

## Uoverensstemmelser mellem overleveringer

### 1. GitHub Actions

Status i indsat overlevering:

- "GitHub Actions CI fejler på alle builds".
- "Nævnt af bruger men IKKE undersøgt".

Aktuel status:

- Dette er forældet.
- Buildfejlen blev identificeret som manglende eksport af `requestThumbnailGeneration`.
- Fix blev committet som `3dd7d4d`.
- Derudover blev Mac deploy-runner rettet i `ae1c135` og `38beca3`.
- Seneste tre GitHub Actions runs er grønne.

Konklusion:

- CI er ikke længere en åben blocker.
- Node.js 20 deprecation annotations vises stadig, men de stopper ikke buildet.

### 2. Headend LaunchAgent og repo-plist

Status i indsat overlevering:

- Aktiv Headend kører som user LaunchAgent med venv i `~/.venvs/timelapse-headend`.
- Repo-plist i `deploy/launchd/dk.froekjaer.timelapse-headend.plist` er forældet.

Aktuel status:

- Bekræftet korrekt.
- Aktiv plist ligger i:

```text
/Users/peter/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```

- Aktiv service kører med:

```text
gui/<uid>/dk.froekjaer.timelapse-headend
/Users/peter/.venvs/timelapse-headend/bin/uvicorn
```

- Repo-plisten peger stadig på gammel venv under repoet og `HOME=/var/root`.

Konklusion:

- Repo-plisten bør opdateres til en secret-fri template for user LaunchAgent.
- Den aktive plist indeholder secrets og må ikke committes.

### 3. `slowapi` dependency

Status i indsat overlevering:

- `slowapi` mangler i requirements.

Aktuel status:

- Bekræftet.
- `headend/main.py` importerer `slowapi`.
- `headend/requirements.txt` indeholder ikke `slowapi`.

Konklusion:

- Tilføj `slowapi` til `headend/requirements.txt`.
- Test derefter CI og Mac deploy.

### 4. Base-image cache

Status i indsat overlevering:

- Base image cache nævnes som:

```text
.base_image_cache/orangepi4pro/orangepi4pro-image.img.xz
```

Aktuel status:

Cache-mappen indeholder både:

```text
.base_image_cache/orangepi4pro/Orangepi4pro_1.0.6_ubuntu_jammy_server_linux5.15.147.7z
.base_image_cache/orangepi4pro/orangepi4pro-image.img
.base_image_cache/orangepi4pro/orangepi4pro-image.img.xz
```

Konklusion:

- Ikke en egentlig konflikt, men dokumentation bør nævne at både komprimeret og udpakket base-image kan være til stede.

### 5. Edge image output

Status i ældre/indsat overlevering:

- Fokus var på ISO/Edge image build og manifestet `TL-EDGE-IMG-ORANGEPI4PRO-20260622213902`.

Aktuel status:

- Flashbare `.img.gz` blev efterfølgende flyttet ud af macOS temp til permanent storage:

```text
/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images
```

- UI viser nu færdige images og download-links under Backup -> Edge disk image.
- Commit: `79581ac`.

Konklusion:

- Næste session bør bruge den permanente artifact-mappe som kilde, ikke `/var/folders/.../T/timelapse-edge-images`.

## Gennemførte ændringer i den seneste fase

### Danske tags i kundevendt UI

Committed status:

- `7405e9f feat: vis danske tag-navne i kundevendt UI...`

Funktionel intention:

- Canonical tags holdes på engelsk i backend.
- UI viser danske labels via oversættelsestabel.
- Brugt i thumbnailkort, lightbox/tagvisning og tagsøgning.

Filer nævnt i tidligere overlevering:

- `GET /api/ai/vocabulary/translations`
- `headend/ai/repositories.py`
- `headend/ai/vocabulary_routes.py`
- `timelapse-ui/src/hooks/useTagLabels.ts`
- `CaptureThumbnailCard.tsx`
- `DevicePage.tsx`
- `TagSearchPage.tsx`

### GitHub buildfix

Problem:

```text
src/components/CaptureThumbnailCard.tsx(3,27): error TS2305:
Module '"../api/client"' has no exported member 'requestThumbnailGeneration'.
```

Fix:

- `timelapse-ui/src/api/client.ts` eksporterer nu `requestThumbnailGeneration`.
- Commit: `3dd7d4d`.

### Mac runner og deploy

Problemer:

- macOS `Icon\r` metadatafiler i `.git` gav:

```text
fatal: bad object refs/Icon?
```

- Workflow forsøgte tidligere at genstarte Headend som systemdaemon med `sudo launchctl stop/start`.

Fix:

- Cleanup-script:

```text
/Users/peter/projects/timelapse-pro/tools/cleanup_macos_icon_files.sh
```

- Workflow rydder `Icon\r` før Git operations på self-hosted runner.
- Workflow bruger nu:

```bash
launchctl kickstart -k "gui/${USER_ID}/dk.froekjaer.timelapse-headend"
```

Commits:

```text
ae1c135 fix(ci): restart mac headend launch agent
38beca3 fix(ci): clean macos icon metadata before deploy git ops
```

### Headend LaunchAgent

Aktiv model:

- User LaunchAgent, ikke system LaunchDaemon.
- Kører som bruger `peter`.
- Venv:

```text
/Users/peter/.venvs/timelapse-headend/
```

Service label:

```text
gui/<uid>/dk.froekjaer.timelapse-headend
```

Vigtigt:

- `launchctl kickstart` genstarter service, men genindlæser ikke plist-ændringer.
- Ved plist-ændringer bruges bootout/bootstrap.
- Secrets i aktiv plist må ikke committes eller gentages i chat/dokumenter.

### Edge image artifacts

Ny stabil artifact-mappe:

```text
/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images
```

Kan overrides med env-var:

```bash
TIMELAPSE_EDGE_IMAGE_DIR=/din/stabile/artifact/mappe
```

Eksisterende færdige flashbare images:

```text
/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images/timelapse-edge-orangepi4pro-20260622213008.img.gz
/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images/timelapse-edge-orangepi4pro-20260622213926.img.gz
```

Nyeste:

```text
timelapse-edge-orangepi4pro-20260622213926.img.gz
```

Størrelse:

```text
ca. 952 MB
```

Backend:

- Bygger fremover direkte til stabil artifact-mappe.
- Lister både DB-registrerede artifacts og filesystem artifacts med manifest.
- Download endpoint kan hente både DB artifacts og filesystem artifacts.

UI:

- Backup -> Edge disk image -> Færdige images.
- Viser klar/mangler-fil status.
- Download-knap.
- Tilføj WiFi-knap for flashbare `.img.gz`.

Commit:

```text
79581ac feat(edge): persist and list disk image artifacts
```

## Runtime-status

Headend health blev verificeret:

```text
GET http://127.0.0.1:8000/api/health -> HTTP 200
```

Disk image endpoint uden login:

```text
GET /api/admin/edge-provisioning/disk-images -> HTTP 401
```

Dette er korrekt, fordi endpointet kræver login/RBAC.

## Aktive tekniske risici og åbne opgaver

### Høj prioritet

1. Verificer i UI:

```text
Backup -> Edge disk image -> Færdige images
```

Kontroller at de to `.img.gz` vises og kan downloades efter login.

2. Tilføj `slowapi` til `headend/requirements.txt`.

3. Opdater `deploy/launchd/dk.froekjaer.timelapse-headend.plist` til secret-fri user LaunchAgent template.

4. Beslut om lokale Nikon Z30/LAB ændringer skal samles i en kontrolleret commit og artifact til R&D edge `TL-C87FF9587CA0`.

### Medium prioritet

1. Fortsæt end-to-end update-flow:

- Headend bygger signeret artifact.
- Test/lab godkendelse før prod.
- Edge puller fra Headend.
- UI viser flowstatus: pending, approved, waiting for poll, installing, installed, failed.
- Edge må fortsat ikke bruge direkte internet/GitHub/apt.

2. Fiks thumbnail postprocessing:

- Postprocessing opdager manglende thumbnails, men har tidligere ikke oprettet dem korrekt.
- Admin-job med progress og retry bør prioriteres.

3. Fortsæt Global Config:

- Alle parametre på global/kunde/site/kamera.
- Underliggende lag overskriver arvede værdier.
- UI viser arvet værdi og aktuel værdi.
- Farvemarkering for override i aktuelt lag og ændring ift. global.
- Kamera-lokation og edge/kamera-binding skal være tydelig.

4. CMDB/GRC:

- Vis installeret version og senest tilgængelig version.
- GRC dashboard med kvantitativ risk.
- Rapportering pr. SABSA, IEC 62443, ISO 27001/27000, NIS2, CRA og GDPR.

### Lavere prioritet / driftshygiejne

1. Oprydning nævnt i indsat overlevering:

- Gammel disabled LaunchDaemon:

```text
/Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist.disabled-20260622
```

- Gammel repo-venv:

```text
/Volumes/data-fast/peter-home/projects/timelapse-pro/headend/venv
```

2. Hold macOS `Icon\r` cleanup aktiv i CI.

3. Undgå at bruge macOS temp-foldere som source of truth for artifacts.

## Nikon Z30 og LAB-status

Mål:

- Udnytte Nikon Z30 bedre end Canon EOS 1300/1000.
- Remote focus.
- Focus slice.
- Video streaming.
- Daily autofocus test på edge.
- Edge AI til billedekvalitet og fokus-offset vurdering.
- Kamera-profiler per kameratype.
- Generiske parametre som ISO skal kunne arves globalt, men profil-specifikke parametre skal være tydeligt markeret.

Rapporterede LAB-problemer:

- LAB rapporteres aktiv før edge faktisk skriver det i loggen.
- Live stream viser enkeltbilleder, ikke rigtig video.
- Preview virker.
- Full capture virker, men billede vises ikke i LAB view.
- Nikon/fokus LAB:
  - Focus step fra kameraprofil kan ikke vælges.
  - Step focus gør ikke noget.
  - Autofocus test virker, men uden AI.
  - Focus slice virker ikke.
  - Edge test virker ikke.
  - Parameterændringer falder tilbage efter accept.
  - Focus mode står AF-A; ønsket er manuel.

Status:

- Der ligger lokale ændringer i edge driver/UI relateret til dette, men de er ikke nødvendigvis committet/pushed.
- Næste session bør gennemgå dirty diff før staging.

## AI, tags og thumbnails

Beslutninger og retning:

- Canonical tags i backend holdes på engelsk.
- Dansk UI via oversættelsestabel.
- Oversættelsestabel kan på sigt vedligeholdes med Gemini-integration.
- Ollama kan være nyttig som lokalt tool til CMDB/SIEM/analyse, men billedtags kan muligvis flyttes til cloud.
- Tidligere AI-analyse hallucinerede kraftigt på byggeri-tags ud fra et landskabs-/vejr-billede.

Thumbnail-principper:

- UI bør bruge eksisterende thumbnails, ikke generere tungt on-demand ved visning.
- Edge bør generere de nødvendige thumbnail-størrelser.
- UI må gerne opdage manglende thumbnails og trigge stille baggrundsgenerering.
- Postprocessing-menu skal kunne regenerere thumbnails og AI-tags for eksisterende billeder.

Åben bug:

- Postprocessing opdager manglende thumbnails, men opretter dem ikke konsekvent.

## Sikkerhed og arkitekturprincipper

Update-flow:

- Edge må ikke direkte på internet for updates.
- Edge må ikke bruge direkte GitHub.
- Edge må ikke bruge direkte apt repositories.
- Headend bygger, tester, signerer og publicerer artifacts.
- Edge henter godkendte artifacts fra Headend.

Lab/staging/prod:

- Alt skal installeres og testes i lab før prod.
- R&D/test edge må ikke automatisk gøre ændringer prod-klar.
- På sigt kan der komme flere prod-headends, enten load balancing eller kundekontrollerede headends.

Mac Headend:

- Mac Headend må ikke ukritisk installere OS/software updates.
- Timelapse Pro update-flow skal skelne mellem Timelapse-komponenter og anden software på Mac'en.
- Kendt portkollision: CrushFTP 11 Enterprise 1.
- Ønske: flyt væk fra 80, 443, 21, 22 og 8080 hvor praktisk muligt.

## Secrets og følsomme data

Må ikke vises, gentages eller committes:

- JWT secrets.
- Break-glass encryption key.
- GPG secret key material.
- GCP service account private key.
- WiFi passwords.
- Edge/API tokens.

Specifik note fra indsat overlevering:

- `/Users/peter/projects/timelapse-pro/secrets/gcp-service-account.json` må aldrig vises/gentages.
- Kun `project_id` og `client_email` må omtales.

## Anbefalet start i næste session

1. Læs dette dokument.

2. Kør:

```bash
cd /Users/peter/projects/timelapse-pro
git status --short --branch
git log --oneline -8
```

3. Verificer UI:

```text
https://timelapse.froekjaer.dk/backup
```

4. Tjek at `Færdige images` viser:

```text
timelapse-edge-orangepi4pro-20260622213008.img.gz
timelapse-edge-orangepi4pro-20260622213926.img.gz
```

5. Vælg næste arbejdsspor:

- Stabiliser Edge image download/WiFi-injection.
- Færdiggør Nikon Z30 LAB/focus/video.
- Færdiggør signed update-flow til `TL-C87FF9587CA0`.
- Ryd dependency/plist drift (`slowapi`, LaunchAgent template).
