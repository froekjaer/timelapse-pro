# Handover — sådan deler Claude og Codex opgaver

**Formål:** en fast, enkel rytme for samarbejdet, så vi ikke dobbeltarbejder, modsiger
hinanden eller overskriver hinandens ting. Læses sammen med
`SERVICES_OG_DRIFT_kilde_til_sandhed.md`. Sidst rørt: 2026-06-28.

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
- [ ] **Bulk re-tag** af ~26.000 billeder: headend kører nu ny kode → UI-batch med `force`
  er klar (eller CLI-backfill). Peter vælger.
- [ ] **Selvlærende baseline** køres igen EFTER en ren re-tag (`camera_profile.py --all --apply`).
- [ ] **`exifread`** mangler i venv (harmløs advarsel) — `pip install exifread`.
- [ ] **Edge AI/NPU QA** (Codex): Orange Pi NPU er verificeret, men rigtig TimeLapse QA `.nb`
  model + VIPLite-wrapper mangler. Se `Codex_Edge_AI_NPU_Modes_2026-06-28.md`.
