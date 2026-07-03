# Thumbnail-galleri: 503-storm (analyse + handlingsplan til Codex)

**Forfatter:** Claude · **Dato:** 2026-06-30 · **Til:** Codex (infra/OS) · **Prioritet:** Høj
**Symptom-kilde:** Peters browser-konsol på Frøkjær-galleriet (testkamera, ~144 billeder/døgn, 24/7)

---

## 1. Symptom

Frøkjær-galleriet fylder browser-konsollen med **hundredevis af `HTTP 503 Service
Temporarily Unavailable`** — på BÅDE thumbnail-filer (`/api/thumbnails/{device}/{file}`)
OG repair-kaldet (`/api/thumbnails/{device}/{file}/generate`). Mange rammer er tomme.
Ved klik på en ramme vises billedet fint (fuld-billede-endpointet virker).

## 2. Bekræftet: det er IKKE et manglende-fil-problem

- Filsystem-survey: 36.474 kilde-billeder, 32.503 thumbnails, **0 korrupte**.
- De manglende thumbnails lå ALLE i Travbyen (`_dup`-forældreløse importfiler uden
  DB-rækker) og er nu backfillet/karantænet. Se `backfill_thumbnails.py`.
- **Frøkjær: 15/15 nyeste captures har både fil OG thumbnail** (edge sender en thumbnail
  med hvert billede). Så Frøkjærs thumbnails FINDES.

→ 503 ≠ 404. Problemet er **levering under belastning**, ikke filerne.

## 3. Rod-årsag: thundering herd + selvforstærkning → uvicorn/nginx-mætning

1. Frøkjær-galleriet er TÆT. `TagSearchPage` henter op til 5000 resultater og renderer
   `CaptureThumbnailCard` for hver → browseren beder om rigtig mange `/api/thumbnails/…`
   på kort tid (lazy-loading dæmper, men en tæt side + scroll giver stadig 100+ samtidige).
2. Thumbnail-GET er et **sync** FastAPI-endpoint → kører i Starlettes trådpulje
   (default ~40 tråde). Hver request laver: auth (`require_role` +
   `_ensure_capture_file_access` = DB-query) + `_find_image` (lru-cachet) +
   `_find_existing_thumbnail` (op til 8 stat-kald på data-fast) + `FileResponse` (streamer
   filen fra data-fast). Under flod mætter trådpuljen, requests køer.
3. **Selvforstærkningen (den dræbende del):** hver fejlet thumbnail (503) udløser
   `<img onError>` → `requestRepair()` → POST `/generate` → ENDNU en tung request (auth +
   find + evt. fuld-billede-læs til generering). Det FORDOBLER request-volumen netop når
   serveren er mest presset → positiv feedback-løkke → serveren kommer aldrig op igen.
   Derfor ses både thumbnail- og `generate`-503 i samme storm.
4. 503 kommer fra **nginx**. To mulige kilder (Codex bekræfter, se §5):
   a) `limit_req`/`limit_conn` på `/api/` sprænges af bursten (nginx svarer 503 default), eller
   b) upstream (uvicorn) backlog/timeout → nginx 503.

`_find_image` er allerede `@lru_cache(maxsize=100_000)`, så stien er ikke flaskehalsen —
det er trådpulje-mætning + den selvforstærkende repair-storm + evt. nginx rate-limit.

## 4. Allerede bygget af Claude (på disk) — BEGGE lag, jf. Peters ønske

> **OPDATERING 2026-06-30:** Claude har nu bygget BÅDE frontend-mitigeringen OG
> backend-X-Accel-siden (flag-gated, default FRA). Codex mangler kun nginx-blokken +
> env-flag (§5.2b). `tsc -b` og `py_compile` grønne.

**Lag 1 — frontend (giver lindring NU, ingen genstart):**
- `CaptureThumbnailCard.tsx`: (a) ved fejl genforsøges den EKSISTERENDE thumbnail med
  jittered backoff (4×) FØR `/generate` → ingen repair-storm. (b) NY **samtidigheds-gate**
  (`src/lib/imageLoadGate.ts`, maks 6 ad gangen) + IntersectionObserver-lazyload → galleriet
  fyrer aldrig mere end 6 thumbnail-requests samtidig, uanset scroll. Det fjerner selve
  bursten der udløser 503. Deploy: `cd timelapse-ui && npm run build` (+ hård reload).
- `headend/main.py`: global `BoundedSemaphore` (`TIMELAPSE_THUMBNAIL_GEN_CONCURRENCY`,
  default 3) på al thumbnail-generering + generér-ved-miss. Kræver headend-genstart.

**Lag 2 — backend X-Accel-Redirect (loftet væk, flag-gated default FRA):**
- `headend/main.py` `_xaccel_redirect()` brugt i `get_thumbnail` (begge stier) og
  `get_image`. Når slået til returnerer Python en `X-Accel-Redirect`-header i stedet for at
  streame filen → **nginx sender filen, uvicorn-workeren frigøres straks**. Auth +
  `_find_image` bevares i Python. Default FRA → uændret `FileResponse`-adfærd indtil Codex
  tænder den (kan derfor deployes nu uden risiko).

- **CLI (`headend/tools/backfill_thumbnails.py`):** offline backfill (brugt til Travbyen).

## 5. Codex' opgaver (infra) — den ægte fix, prioriteret

### 5.1 Diagnose først (bekræft 503-kilden)
```bash
# Er der en rate-limit på /api/ i nginx?
grep -rnE "limit_req|limit_conn|limit_req_zone|limit_conn_zone" /opt/homebrew/etc/nginx/ 2>/dev/null
# Hvordan startes uvicorn — hvor mange workers/tråde?
grep -rnE "uvicorn|--workers|gunicorn|UvicornWorker" ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist \
  ~/projects/timelapse-pro 2>/dev/null | grep -vi node_modules
# Nginx-fejllog under en galleri-load (kig efter "limiting requests" / "upstream")
tail -n 200 /opt/homebrew/var/log/nginx-timelapse-error.log
```
- "limiting requests" i error-loggen → det er `limit_req` (5.2a).
- "upstream timed out" / "no live upstreams" / "connect() failed" → uvicorn-mætning (5.2c).

### 5.2 Fixes

> **BEKRÆFTET ROD-ÅRSAG 2026-06-30:** nginx `limit_req_zone ... zone=api_general rate=120r/m`
> = **2 requests/sek** (burst 60, nodelay) på `location /api/`. Efter de første 60 thumbnails
> throttles alt til 2/sek og resten afvises med 503. DET er 503'en. Begge fixes nedenfor er nu
> AUTOMATISERET i `deploy/enable_thumbnail_xaccel.sh` (idempotent, backup + `nginx -t` + rollback).

**a) DEN AFGØRENDE FIX — undtag media fra rate-limit.** Dedikerede `^~`-locations for
`/api/thumbnails/` + `/api/images/` UDEN `limit_req` (auth-beskyttet read-only media), indsat før
`location /api/`. `^~` sikrer de ikke arver limit_req. Data-API'et beholder sin grænse.
Scriptet indsætter dem nu automatisk:
```nginx
location ^~ /api/thumbnails/ { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; … }
location ^~ /api/images/     { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; … }
```

**b) BEDST — server filen via nginx (X-Accel-Redirect). PYTHON-SIDEN ER NU FÆRDIG.**
Claude har bygget `_xaccel_redirect()` ind i `get_thumbnail` (begge stier) og `get_image`
i `headend/main.py`. Den er **flag-gated, default FRA**, så intet ændres før Codex tænder den.
For at aktivere mangler KUN nginx-blokken + tre env-variable + genstart:

**1) nginx — tilføj en intern location** (i samme server-blok som `/api`-proxy'en):
```nginx
location /_protected_media/ {
    internal;                                                   # kun via X-Accel-Redirect
    alias /Volumes/data-fast/timelapse-incoming/canonical-images/;
    add_header Cache-Control "public, max-age=604800, immutable";
}
```

**2) env i LaunchAgent** (`dk.froekjaer.timelapse-headend.plist`):
```
TIMELAPSE_THUMBNAIL_XACCEL = on
TIMELAPSE_XACCEL_ROOT      = /Volumes/data-fast/timelapse-incoming/canonical-images
TIMELAPSE_XACCEL_PREFIX    = /_protected_media        # skal matche nginx-location ovenfor
```
(`TIMELAPSE_XACCEL_ROOT` SKAL være lig nginx-`alias`-roden; Python beregner filens sti
relativt til den og sætter `X-Accel-Redirect: /_protected_media/<relativ-sti>`.)

**3) Genindlæs nginx + genstart headend, og verificér:**
```bash
nginx -t && nginx -s reload
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend
# Et thumbnail-svar skal nu komme fra nginx (ingen Python-stream). Bekræft headeren:
curl -sI -b "tl_session=<gyldig>" \
  "https://127.0.0.1/api/thumbnails/TL-C87FF9587CA0/<filnavn>.jpg" | grep -iE "x-thumbnail|cache|server"
```
Mekanik: Python laver stadig auth + `_find_image` (sikkerhed bevaret), men returnerer en tom
200 med `X-Accel-Redirect` → nginx læser den interne location og sender selve filen. Worker
frigøres straks → galleriet kan loade i tusindvis/sek uden at mætte uvicorn. Slå fra igen ved
at fjerne `TIMELAPSE_THUMBNAIL_XACCEL` (falder tilbage til `FileResponse`).

**Sikkerhed:** `internal` gør at `/_protected_media/` IKKE kan tilgås direkte udefra — kun
via Pythons X-Accel-svar efter auth. Så adgangskontrollen er uændret.

**c) Hvis app-serveret beholdes — flere workers/tråde.** Kør uvicorn med flere workers
(fx `--workers 4`) ELLER hæv Starlettes trådpulje
(`anyio.to_thread` default 40 → hæv via `TIMELAPSE_*`/kode). Bemærk: konkurrerer om RAM/IO
med Postgres/Ollama på Mac Mini'en.

### 5.3 Frontend gate (samtidighed + rate) — NU BYGGET (Claude)
Gjort: `src/lib/imageLoadGate.ts` begrænser BÅDE samtidighed (maks 6 in-flight) OG
**rate** (min 55 ms mellem starts ≈ 18/sek) + IntersectionObserver i `CaptureThumbnailCard`.
Rate-grænsen er vigtig: et tæt kamera-grid (`DevicePage` "Billeder (200)") renderer alle 200
kort på én gang → uden rate-loft rammer den hurtige byge nginx' `limit_req` (= 503). Begge
gallerier (Tag-søgning + kamera) bruger samme gatede kort. Deploy: `npm run build` + hård reload.

## 6. Anbefalet rækkefølge

1. **Nu (Peter):** `cd ~/projects/timelapse-pro/timelapse-ui && npm run build` + hård reload
   (Cmd+Shift+R). Frontend-gaten (maks 6 samtidige) + retry-backoff fjerner bursten →
   galleriet bør være brugbart MED DET SAMME, ingen genstart, ingen infra-ændring.
2. **Codex (eftermiddag):** kør §5.1-diagnose. Aktivér så **§5.2b (X-Accel-Redirect)** —
   Python-siden er færdig, der mangler kun nginx-blokken + 3 env-flag + genstart. Det fjerner
   loftet permanent. (§5.2a er en hurtig nginx-only fallback hvis I vil vente med X-Accel.)
3. Genstart headend (samler også backend-semaphore + generér-ved-miss op). Hvis X-Accel
   tændes, sker det i samme genstart.
4. Verificér: load Frøkjær-galleri (hård reload) → ingen 503; tjek at thumbnail-svar har
   X-Accel-header (§5.2b-curl) og at nginx-error-loggen er ren under load.

## 7. Filer rørt (bygget af Claude, på disk)
- `timelapse-ui/src/components/CaptureThumbnailCard.tsx` (retry-backoff + gate-integration)
- `timelapse-ui/src/lib/imageLoadGate.ts` (NY — samtidigheds-gate)
- `headend/main.py` (semaphore + generér-ved-miss + `_xaccel_redirect` i get_thumbnail/get_image)
- `headend/tools/backfill_thumbnails.py` (ny, offline backfill + karantæne)
