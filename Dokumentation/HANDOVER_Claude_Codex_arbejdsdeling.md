# Handover — sådan deler Claude og Codex opgaver

**Formål:** en fast, enkel rytme for samarbejdet, så vi ikke dobbeltarbejder, modsiger
hinanden eller overskriver hinandens ting. Læses sammen med
`SERVICES_OG_DRIFT_kilde_til_sandhed.md`. Sidst rørt: 2026-07-03.

> Vi to assistenter taler ikke direkte sammen. **Vores "kommunikation" er filer i
> `Dokumentation/` + Peter der relayer.** Derfor: skriv tingene ned, hold dem ét sted.

---

## 1. Hvem kan hvad (kort)

| | Claude | Codex |
|---|---|---|
| Kode, AI/prompt, scripts, analyse, diagnose | ✅ | ✅ |
| Nå selve Mac'en (launchd, psql, sudo, disk/volumen, netværk) | ❌ (sandbox) | ✅ |
| Taste i Terminal / køre kommandoer | ❌ (skriver dem) | ✅ |
| Godkende, eksekvere, prioritere | — | — → **Peter** |

Tommelfingerregel: **Claude skriver kommandoen/koden → Codex eller Peter kører den.**

---

## 2. Hvem tager hvad

- **Til Claude:** ny kode, AI-/prompt-/vokabular-arbejde, dataanalyse (ud fra log/DB-output
  Peter indsætter), scripts/værktøjer, designnotater, fejlsøgning på applikationsniveau.
- **Til Codex:** alt OS-/driftslag — genstart af services, volumen-/diskfix, sudo, launchd,
  netværk/nginx, ting der kræver fysisk/system-adgang til Mac'en.
- **Gråzone (aftal hvem):** databasemigrationer (Claude skriver, Codex/Peter kører),
  deploy/rebuild, performance på maskinen.

---

## 3. Rytmen for en opgave

1. **Peter** beskriver opgaven for den assistent der passer bedst (eller begge).
2. Assistenten **løser sin del** og efterlader en **handover-note** (skabelon nedenfor)
   i `Dokumentation/HANDOVER_LOG.md`, hvis den anden part skal videre.
3. Hvis opgaven krydser grænsen (fx "kode er klar, men kræver genstart + sudo"):
   - Claude skriver **præcise kommandoer** + hvad der forventes som output.
   - Codex/Peter kører dem og **indsætter outputtet tilbage**.
   - Claude **tolker outputtet** og siger næste skridt.
4. Når noget om services/porte/stier/genstart ændres → **opdatér
   `SERVICES_OG_DRIFT_kilde_til_sandhed.md`** (ikke et privat dokument).

---

## 4. Handover-note (kopiér og udfyld)

```
### Handover [dato] — fra <Claude|Codex> til <Codex|Claude|Peter>
- Hvad er gjort:
- Hvad mangler / næste skridt:
- Kommandoer der skal køres (med forventet output):
- Filer rørt:
- Risici / pas på:
```

Læg den i `Dokumentation/HANDOVER_LOG.md` og link eventuelt til det relevante emnedokument.
Ikke kun i en chat - så har den anden part den, selv uden at have set samtalen.

## 4b. Codex' ekstra regler

- Hvis opgaven kræver Mac/Orange Pi/sudo/launchd/psql, tager Codex udførelsen og skriver kort
  hvad der faktisk skete.
- Hvis der er mange ændringer i repoet, laver Codex kun commits med konkrete filer eller separat
  Git-index, så Claude/Peters arbejde ikke utilsigtet ryger med.
- Hvis Codex ændrer services, stier, porte, login-flow, backup eller diskworkaround, opdateres
  `SERVICES_OG_DRIFT_kilde_til_sandhed.md` samme dag.
- Hvis Codex deployer til edge/headend, noteres testkommandoer og resultat i handover-loggen.

---

## 5. Når vi er uenige

- **Empiri vinder over mening:** kør en lille test (fx side-om-side, et dry-run) og lad
  tallene afgøre. Vi byggede allerede værktøjer til netop det (`compare_*`, `--dry-run`).
- **Rør ikke den andens arbejde stiltiende.** Skal noget den anden har lavet ændres,
  så notér hvorfor i handover-noten — overskriv ikke uden spor.
- **Peter har sidste ord** ved prioritering og ved valg der koster penge eller er
  irreversible (fx bulk-Gemini-kørsler, sletninger, diskoperationer).

---

## 6. Navngivning og kilder

- Personlige analyser/udkast: `Claude_*` / `Codex_*` (som i dag).
- Fælles sandhed (én version, begge vedligeholder): `SERVICES_OG_DRIFT_kilde_til_sandhed.md`
  og dette dokument.
- Et samlet, merged dokument konsoliderer begge sæt når det giver mening
  (fx `*_full_documentation_v1.md`).

---

## 7. Lige nu — åbne tråde (hold denne liste kort og opdateret)

- [ ] **Data-fast volumen-helbred** (Codex/Peter): den ægte fix udestår — den vælter
  login, genstart og batch når den slår til. Se driftsdokumentet §3.
- [x] **Mac Mini autostart/drift efter crash** (Codex, 2026-07-03): strøm-/freeze-restart slået
  til, sleep/disk sleep slået fra, og headend/PostgreSQL/nginx/UI flyttet til system-LaunchDaemons.
  Begrænsning: FileVault er stadig On og kan kræve manuel unlock efter strømudfald.
- [ ] **Bulk re-tag** af ~26.000 billeder: headend kører nu ny kode → UI-batch med `force`
  er klar (eller CLI-backfill). Peter vælger.
- [ ] **Selvlærende baseline** køres igen EFTER en ren re-tag (`camera_profile.py --all --apply`).
- [ ] **`exifread`** mangler i venv (harmløs advarsel) — `pip install exifread`.
- [ ] **Edge AI/NPU QA** (Codex): Orange Pi NPU er verificeret, men rigtig TimeLapse QA `.nb`
  model + VIPLite-wrapper mangler. Se `Codex_Edge_AI_NPU_Modes_2026-06-28.md`.
- [ ] **Driftsovervågning + Edge QA signaler** (Claude + Codex): Claude bygger
  drifts-/observability-systemet i headenden. Codex leverer Edge QA/NPU-kontrakt, modeldata,
  sidecar-format og driftsfelter, så Claudes system kan vise kamera-/billedkvalitet uden at
  kopiere heuristikken.
- [ ] **Tag-oversættelse i UI** (Claude, queued): tags vises på engelsk i "AI Styring" og
  "Tag søgning". Danske labels findes i `ai_tag_vocabulary.display_name_da` (+ `PREDEFINED_DA_LABELS`
  / Geminis `new_tags_da`), men `/api/ai/tags/all` returnerer kun det engelske token. Fix:
  (1) endpoint `GET /api/ai/tags/translations` (genbrug `TagRepository.get_tag_translations()`),
  (2) render `da || en` i begge sider (engelsk token bevares som søgeværdi),
  (3) tjek dækning + backfill manglende `display_name_da` for nye tags efter bulk-re-tag.
  Tages som fokuseret opgave på egen `claude/`-branch efter ITIM/baseline-batchen.
- [ ] **ITIM/baseline-batch** (Claude→Codex): ITIM-hærdning (data-fast probe), natlig
  baseline-tråd, static/dynamic-fix, adaptivt vindue + `min_samples`-knap — alt på disk, py_compile
  grøn. Skal på `claude/`-branch + bevidst genstart. Åbent valg: `min_samples`-default 150 vs 80.
- [x] **Thumbnail-galleri 503-storm — HELT LØST 2026-07-01.** ROD-ÅRSAG: nginx
  `limit_req_zone ... zone=api_general rate=120r/m` = **2 req/sek** (burst 60) på `location /api/`
  → et galleri afvises med 503 efter de første 60. Tre lag, alle aktive:
  (1) frontend-gate (samtidighed 6 + rate ~18/sek) via `npm run build`;
  (2) X-Accel-Redirect (nginx serverer filen, uvicorn ude af varm sti);
  (3) **DEN AFGØRENDE:** dedikerede `^~ /api/thumbnails/` + `^~ /api/images/` UDEN limit_req
  (data-API'et beholder sin grænse). Alt automatiseret i `deploy/enable_thumbnail_xaccel.sh`
  (idempotent, backup + `nginx -t` + rollback). NB: scriptet havde en bug (fandt en `.bak`-fil via
  `grep -rl` og redigerede den i stedet for `nginx.conf`) — RETTET: foretrækker nu hovedkonfig +
  ekskluderer `*.bak-*`/`*.new`. Detaljer: `Codex_Thumbnail_503_Analyse_2026-06-30.md`.
  (Codex: intet udestående — kun til orientering. Overvej om `api_general` 120r/m er bevidst lavt.)

## 8. Aftale: Driftsovervågning og Edge QA

**Claude ejer headend-driftsovervågningen:**

- UI/API til samlet driftsstatus.
- Aggregater pr. kunde/site/kamera.
- Alarmer, trends, health cards og operatørvisninger.
- Integration med eksisterende headend-DB, batch-job-status, services og driftshændelser.

**Codex ejer Edge QA/NPU-sporet:**

- Edge runtime, Orange Pi/NPU-probe, VIPLite-wrapper og `.nb` model-deploy.
- QA modelkontrakt og labels: `timelapse.edge_qa.v1`.
- Mining/review/træning af billedkvalitetsmodel.
- Sidecar og capture-felter, der beskriver billedkvalitet og autonom anbefaling.

**Fælles kontrakt mellem sporene:**

Edge/capture skal levere stabile felter, som headend/Claude kan indeksere og visualisere:

- `quality_flag`: `ok`, `blurry`, `underexposed`, `overexposed`, `error`, `hash_mismatch`.
- `quality_passed`: boolean.
- `probable_cause`: fx `direct_sun_reflection`, `snow_or_dirt_on_lens`,
  `underexposure_or_camera_blocked`, `focus_or_lens_issue`.
- `confidence`: 0.0-1.0.
- `quality_dimension`: `overall`, `focus`, `exposure`, `schedule`, `lens_obstruction`,
  `white_balance`, `depth_of_field`.
- `autonomous_optimizer.score.overall` og `grade`.
- `autonomous_optimizer.recommendations[]` med `kind`, `action`, `confidence`, `reason`, `params`.
- `autonomous_optimizer.control_plan.next_capture_ev_delta`.
- `autonomous_optimizer.control_plan.avoid_window_suggestion`.
- `npu.available`, `npu.engine`, `npu.model_path`, `npu.confidence`, `npu.label`.

**Vigtig grænse:** Headend-overvågningen skal ikke selv klassificere billedkvalitet fra pixels som
primær logik. Den må aggregere, vise og alarmere på Edge QA-resultaterne. Hvis Claude finder behov
for nye signaler, skrives de som ønskede kontraktfelter her eller i
`Codex_Edge_AI_NPU_Modes_2026-06-28.md`, og Codex implementerer dem i Edge QA-sporet.

**Praktisk næste snitflade:**

- Codex laver et lille `edge_qa_signal` eksempel/JSON-schema og sikrer, at batchanalyse og sidecars
  følger det.
- Claude kan bygge driftsovervågning mod dette format og markere ukendte/manglende felter som
  `unknown`, ikke som fejl.
- Når rigtig NPU-model er klar, skal Claudes UI kunne skelne mellem `engine=edge_cv_v1`,
  `engine=edge_npu_contract_cpu_fallback` og en rigtig VIPLite/NPU model.
