# TimeLapse Pro — Redesign af AI-tag-generering

**Dato:** 2026-06-23
**Forfatter:** Claude (senior gennemgang)
**Status:** Implementeret i kode (afventer review + test på rigtige billeder)
**Relaterer til:** CAP-005 (AI-tags og søgning), R11 (AI-tags hallucinerer), R12/SEC-005/SEC-008 (GDPR/subprocessor)

---

## 1. Problemet

På nogle billeder kom der tags som `ingen_kran`, `ingen_arbejder`, `no_activity`. Det er et symptom på *hvordan* vi spurgte Gemini, ikke på modellen.

### Rodårsag

Den gamle prompt (`gemini_service.build_prompt_text`) rakte modellen **hele vokabularet** kategori for kategori og sagde reelt *"Match ordene fra listen EXACTLY"*. En lang liste af konkrete objekter (tårnkran, arbejder, gravemaskine) virker som en **afkrydsningsliste** — modellen rapporterer så også pligtskyldigt *fraværet*. Tre ting forstærkede det:

1. Vokabularet indeholdt selv fraværs-tags (`no_activity`, `no_change`, `quiet_construction_site`), som modellen imiterede og generaliserede til `no_crane` / `no_worker`. De kom tilbage som `new_tags`.
2. Prompten krævede *"Find between 15 and 35 tags total"* — en kvote, der pressede modellen til at fylde op, og fravær er en nem måde at fylde op på.
3. `temperature=0.1` gjorde modellen meget bogstavelig og listebunden.

### Tre andre begrænsninger ift. målet

- **Ingen kontekst.** Hvert billede fik nøjagtigt den samme prompt. Modellen vidste ikke hvilken kunde/site/kameraposition, hvad klokken var, eller hvad "normalt" er for kameraet. Derfor kunne den i princippet *ikke* fange "en bil i indkørslen den ikke plejer at se", "personer i en baggård der normalt er tom" eller "køretøjer om natten" — det kræver en baseline pr. kamera.
- **Grov vokabular-trunkering.** `integration._limit_vocabulary` tog bare de første N tags på tværs af kategorier (grænse 45-80 ud af ~300+). Hele kategorier kunne forsvinde fra prompten — potentielt netop `anomalies_and_events` og `camera_quality`, dvs. de tags du går mest op i.
- **Change-detection reelt slået fra.** Reference-/ændrings-mekanismen findes (`has_reference`), men live-workeren sendte aldrig et referencebillede.

---

## 2. Den nye tilgang

Vendt om: **hybrid, åbent vokabular med kontekst-bevidsthed.**

1. **Åbent vokabular.** Modellen tagger frit hvad den faktisk ser. Vokabularet er nu *inspiration/kanonisering* — ikke tvang. Ingen kvote.
2. **Fravær forbudt eksplicit.** Prompten siger direkte: *"NEVER tag the ABSENCE of something … if it isn't there, simply don't mention it."* — med `no_crane`/`no_worker` som eksplicitte negativ-eksempler.
3. **Kontekstblok pr. billede.** Kunde/site/kamera + lokal tid (→ dag/nat/årstid) + kameravinkel + **baseline** ("hvad dette kamera normalt viser") + driftsnoter. Det er forudsætningen for novelty-/anomalidetektion. Om natten tilføjes desuden et hint om at personer/køretøjer som udgangspunkt er usædvanlige.
4. **Dedikeret hændelses-/anomaliblok.** Eksplicit liste modellen aktivt skal kigge efter: brand/røg/ild, oversvømmelse, ambulance/brandbil/politi, ulykke, ukendt køretøj, uvedkommende, personer/køretøjer om natten, efterladt udstyr, dyr. Den bruger konteksten til at vurdere hvad der er *usædvanligt for netop dette kamera*.
5. **Selvstændig kvalitetsblok.** Overeksponering, genskin, sol i linsen, linseflare, snavs/kondens på linse, slør, forkert fokus, for mørkt natbillede, kamera flyttet — vurderet uafhængigt af motivet og søgbart som tags.
6. **Vokabularet bruges som normaliserings-lag bagefter**, ikke som inputbegrænsning. Dit eksisterende `canonical_metadata()` + godkendelses-workflow (`get_pending_review`/`approve`/`reject`) passer perfekt: frie tags fanges som `new_tags` med `approved=False` og kan godkendes ind i vokabularet — det vokser stadig, men styrer ikke længere modellens syn.

`temperature` hævet fra 0.1 → 0.35 (nok frihed til dækkende ord, stadig konsistent).

> JSON-skemaet er bevidst **uændret** (`scene`/`tags`/`new_tags`/`quality`/`gdpr`/`change`). Dermed virker `alarm_engine`, sidecar-skrivning og payload uændret videre. Anomalier flyder gennem `tags` (kategorien `anomalies_and_events`), som `alarm_engine` allerede matcher på (fx fire/smoke → critical).

---

## 3. Lokal Ollama — pris og privacy

Strategi-systemet (`ai_strategy.py`) understøtter allerede fire tilstande pr. **kunde/site** — så pris/privacy-valget er en konfig-knap, ikke en omskrivning:

| Strategi | Hvad sker der | Hvornår |
|---|---|---|
| `cloud_only` | Direkte til Gemini | Bedst kvalitet (nuværende default) |
| `local_only` | Kun lokal Ollama | **Billigst + bedst privacy** — billeder forlader aldrig huset |
| `local_then_cloud` | Ollama først, eskalér til Gemini ved usikkerhed/kritiske tags/dårlig kvalitet | Balance: spar penge på de nemme billeder, brug cloud på de svære |
| `technical_only` | Kun OpenCV, ingen AI-tags | Maks privacy / ingen omkostning |

Den nye prompt-filosofi er nu anvendt på **begge** motorer. Ollama-prompten er en bevidst **slankere** variant (samme regler — åbent vokabular, ingen fravær, kontekst, anomali/kvalitet — men kortere og med færre tags), fordi de lokale modeller (fx `llava-phi3`) er små og klarer lange instruktioner dårligere. Kontekstblokken fodres til Ollama på præcis samme måde som til Gemini.

**Privacy-/GDPR-vinkel (relevant for R12, SEC-005, subprocessor-registret):** kører en kunde/site på `local_only`, er Google/Gemini **ikke** databehandler for de billeder. Det kan blive et reelt salgs-/compliance-argument: privacy-følsomme sites (fx hvor personer ofte er i billedet) kan sættes til lokal analyse, mens almindelige byggepladser kører cloud. Anbefaling: gør strategien til en dokumenteret del af DPIA'en pr. site.

**Forudsætning for at Ollama virker i drift:** Ollama skal køre på headend (`:11434`) med en vision-model trukket (`ollama pull llava-phi3` el. lign.), og `local_model` i `ai_config` skal pege på den. `local_then_cloud` kræver desuden gyldige Gemini-credentials til eskalering. Det er værd at køre en LAB-sammenligning af lokal vs. cloud-tag-kvalitet på et repræsentativt udsnit, før en kunde sættes på `local_only`.

---

## 4. Hvad er ændret i koden

| Fil | Ændring |
|---|---|
| `headend/ai/gemini_service.py` | `build_prompt_text` omskrevet (hybrid/åben, ingen fravær, kontekst, anomali, kvalitet). `analyse()` + `build_batch_request_line()` tager nu `context_block`. Temperature 0.1 → 0.35. |
| `headend/ai/ollama_service.py` | `_build_vision_prompt()` omskrevet i slank variant; `analyse()` tager `context_block`. |
| `headend/ai/capture_context.py` | **Nyt modul.** `CaptureContext` + `build_capture_context(db, capture, device)` (resolver kunde/site/kamera + lokal tid/dag-nat/årstid + baseline via aktiv `DeviceAssignment`→`Camera`) + `format_context_block()`. Indeholder aldrig persondata. |
| `headend/ai/integration.py` | `_limit_vocabulary` prioriterer nu vigtige kategorier (anomali/kvalitet/vehicles/workers/weather/light/change/site_condition trunkeres aldrig væk). Workeren bygger kontekst og sender den til både Gemini og Ollama. |
| `headend/database.py` | `Camera`: nye felter `baseline_description`, `context_notes`. |
| `headend/main.py` | DB-migration v10 (idempotent `ALTER`) + `baseline_description`/`context_notes` redigerbare via `PUT /api/admin/cameras/{id}` og synlige i `GET /api/admin/cameras`. |

Alle 6 moduler kompilerer rent. Prompt-rendering verificeret: ingen kvote, ingen "match exactly", fravær forbudt, kontekstblok injiceres, og trunkeringen bevarer anomali-/kvalitets-kategorierne.

---

## 5. Sådan tages baseline i brug

Baseline pr. kamera er den vigtigste nye knap. Eksempel (fra et nat-billede), som det fodres til modellen:

```
## KONTEKST (baggrundsviden — beskriv stadig kun hvad du faktisk ser)
- Lokation: Andersen Byg A/S, Møllevej 12, Kamera Nord
- Tidspunkt: 2026-06-23T02:14, nat, sommer (lokal tid)
- Kameravinkel: high_angle
- Normalbillede for dette kamera: Udsigt over byggegrund med ét tårnkran-
  fundament. Indkørsel til venstre er normalt tom. Ingen aktivitet om natten.
- Driftsnoter: Nabogrund til højre er under byggeri — kran dér er normal.
  Det er NAT her. Personer, køretøjer eller aktivitet er som udgangspunkt
  usædvanligt og bør markeres som en hændelse.
```

Sættes i dag via API:

```bash
curl -X PUT https://backend.timelapse-pro.dk/api/admin/cameras/<camera_id> \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"baseline_description":"...", "context_notes":"..."}'
```

Gode baselines beskriver: synsfeltet, faste/forventede objekter, hvad der er normalt på forskellige tider, og hvad der **ikke** skal udløse falsk anomali (fx trafik på en vej i baggrunden, naboens kran).

---

## 6. Anbefalede næste skridt

1. **UI-felt til baseline** i kamera-redigering (React) — bagenden er klar; mangler kun et tekstfelt der sender `baseline_description`/`context_notes`. (Lille opgave.)
2. **Genaktivér change-detection i drift** — send forrige godkendte billede som referencebillede i workeren (mekanikken findes allerede; den slankede Ollama-variant kører i dag uden reference).
3. **Batch-reprocessering** af eksisterende billeder med den nye prompt via Batch API (≈50 % pris) — så historiske billeder får konsistente, kontekst-tags. Ryd samtidig de gamle `no_*`-tags i `ai_tag_vocabulary` (sæt `rejected=TRUE`).
4. **LAB-evaluering lokal vs. cloud** på et repræsentativt udsnit, før en kunde sættes på `local_only`/`local_then_cloud`.
5. **Overvej en `events`-blok i JSON-skemaet** (type + severity + dansk forklaring) hvis I vil have stærkere strukturerede hændelser end tags-baseret alarmering. Det rører `ImageAnalysisResult` + payload + alarm_engine og er derfor en bevidst, separat ændring — holdt ude af denne omgang for at bevare bagudkompatibilitet.
