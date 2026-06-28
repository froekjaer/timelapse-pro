# TimeLapse Pro — FAQ & fejlsøgning (selvbetjening)

**Til Peter** (når du selv vil løse noget) **og til Claude/Codex** (så vi giver samme svar på
tværs af sessioner). Symptom → hurtig diagnose → løsning. Detaljer i
`SERVICES_OG_DRIFT_kilde_til_sandhed.md`. Sidst rørt: 2026-06-28.

> **Fælles regel:** dette er kanonisk i `Dokumentation/` (git-sporet, begge assistenter
> opdaterer her). En **nød-kopi** ligger på boot-drevet (`~/Claude/Projects/Timelaps/`),
> så den kan læses selv når `data-fast` er nede.

> **Når noget ændres:** opdatér først den kanoniske fil i repoet. Kopiér derefter FAQ'en til
> nød-kopien på boot-drevet:
> ```bash
> cp Dokumentation/FAQ_og_fejlsøgning.md ~/Claude/Projects/Timelaps/FAQ_og_fejlsøgning_NØDKOPI.md
> ```

---

## "Jeg kan ikke logge ind"

**Hurtig diagnose — kør:**
```bash
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```

- **`health: 200`** → backend kører. Så er det login-stien, ikke systemet:
  - Brugte du **Touch ID-knappen**? Den fejler hvis du ikke har en registreret passkey
    (`webauthn-begin` → 404). **Brug i stedet den blå "Log ind"** med brugernavn + adgangskode.
  - Får du afvist adgangskoden (401)? Tjek brugernavn/adgangskode. Se rigtige brugere:
    ```bash
    psql -U timelapse timelapse_db -c "SELECT username, role, is_active FROM users ORDER BY id;"
    ```
- **`health: 000` eller `502`** → backend er **nede**. Gå til afsnittet "UI/headend svarer ikke".

---

## "UI'et / headenden svarer ikke" (health 000/502)

```bash
# Genstart (foretrukket):
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend
sleep 25
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```

- **Bliver 200** → oppe igen.
- **`Bootstrap failed: 5: Input/output error`** eller bliver hængende → det er
  **data-fast-volumenet** (se nederst). Codex/Peter kører workaround'en, derefter genstart.

---

## "Tags på billederne ser dårlige ud"

Tjek i rækkefølge — det er som regel billedet, ikke modellen:

1. **Er billedet faktisk fint?** Åbn det i galleriet. Hvis det er gråt/blankt/korrupt →
   det er capture-/disk-problem (ofte data-fast I/O), ikke AI. `unusable_image` er så korrekt.
2. **Kører den nye kode?** Headenden skal være **genstartet** efter kodeændringer
   (CLI-scripts kræver det ikke, men den løbende worker/UI-batch gør).
3. **Sparsomme tags (kun vejr)?** Var symptomet før billedopløsning + scene-prompt blev rettet.
   Re-tag billedet og se: `backfill.py --ids <id> --force --strategy cloud_only`.
4. **Falsk `unusable_image` på et fint billede?** Var en for aggressiv regel — nu strammet.
   Re-tag for at bekræfte.

---

## "Hvordan genstarter jeg / efter kodeændringer?"

```bash
# Efter FRONTEND-ændringer: byg UI først
cd ~/projects/timelapse-pro/timelapse-ui && npm run build && cd ..
# Genstart headend (indlæser ny backend-kode)
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend
sleep 25
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8000/api/health
```
CLI-scripts (`backfill.py`, `camera_profile.py`, `compare_ollama_gemini.py`,
`normalize_existing_tags.py`) bruger altid koden på disken — de kræver **ikke** genstart.

---

## "Hvordan re-tagger jeg billeder?"

- **Få billeder / test (synkron, frisk kode):**
  ```bash
  SFTP_BASE=$(psql -U timelapse timelapse_db -tA -c "SELECT COALESCE((SELECT value FROM settings WHERE key='sftp_base'),'/Volumes/data')") \
  ~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/backfill.py --limit 10 --force --strategy cloud_only
  ```
- **Alle (~26.000), billigst:** via UI → **AI-batch** med `force` (kræver headend på ny kode).
- **Specifikke id'er:** `backfill.py --ids 26406,26410 --force --strategy cloud_only`.
- **Spredt over perioden + resultatfil:** `--site "..." --limit 50 --spread --out <fil>.json`.

---

## "Hvordan opdaterer jeg de selvlærende baselines?"

```bash
~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all          # dry-run
~/.venvs/timelapse-headend/bin/python ~/projects/timelapse-pro/headend/ai/camera_profile.py --all --apply  # gem
```
Bedst kørt **efter** en ren re-tag. Kan sættes på natligt skema.

---

## "Ollama vs Gemini — hvad bruger jeg hvornår?"

- `cloud_only` (Gemini): bedst kvalitet. `local_only` (Ollama): privacy/pris, billeder forlader
  ikke huset. `local_then_cloud`: Ollama tager de nemme, eskalerer de svære til Gemini.
- Sammenlign selv: `compare_ollama_gemini.py --sites "..." --per-site 5 --out <fil>`.

---

## Data-fast volumen-problemet (rod til login/genstart/korrupte billeder)

**Symptom:** `Bootstrap failed: 5: Input/output error`, login der fejler, grå/blanke frames.
**Workaround (Codex/Peter, sudo):**
```bash
sudo xattr -rd com.apple.quarantine ~/projects/timelapse-pro ~/.venvs/timelapse-headend
sudo mdutil -i off /Volumes/data-fast
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```
**Ægte fix (udestår):** `diskutil verifyVolume /Volumes/data-fast` + tjek Console for I/O-fejl;
overvej at flytte venv/home væk fra volumenet hvis disken er flaky.

---

## Hvor ligger tingene (hurtig reference)

| Hvad | Hvor |
|---|---|
| Repo / kode | `~/projects/timelapse-pro` |
| Python venv | `~/.venvs/timelapse-headend` |
| Headend-log | `~/Library/Logs/timelapse-headend.log` |
| Billeder (sftp_base) | `/Volumes/data-fast/timelapse-incoming/canonical-images` |
| DB | `psql -U timelapse timelapse_db` |
| Headend | `127.0.0.1:8000` · Ollama `127.0.0.1:11434` · Postgres `5432` |

---

## "Claude og Codex siger noget forskelligt"

Brug denne rækkefølge:

1. Tjek `SERVICES_OG_DRIFT_kilde_til_sandhed.md` for services, porte, stier og genstart.
2. Tjek `HANDOVER_LOG.md` for seneste faktiske handlinger/testoutput.
3. Hvis dokumenterne ikke dækker situationen: kør en lille diagnose/dry-run og opdatér dokumentet
   med resultatet bagefter.

Regel: empiri og dokumenteret output vinder over hukommelse fra chat.
