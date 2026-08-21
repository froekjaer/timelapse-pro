# src/help/content — genereret indhold (ikke rediger her)

Markdown-filerne i denne mappe er **build-artefakter**, genereret af
`scripts/sync-help-docs.mjs` (kører automatisk via `npm run dev`/`npm run build`
gennem predev/prebuild-hooks).

Kilderne — og eneste sted at redigere — er:

| Genereret fil | Kilde (single source of truth) |
|---|---|
| `faq.md` | `Dokumentation/FAQ_og_fejlsøgning.md` |
| `menuguide-bruger.md` | `Dokumentation/MENUGUIDE_BRUGER_v1.md` |
| `menuguide-admin.md` | `Dokumentation/MENUGUIDE_ADMIN_v1.md` |
| `brugermanual.md` | `Dokumentation/BRUGERMANUAL_v10.md` |
| `adminmanual.md` | `Dokumentation/ADMINISTRATORMANUAL_v10.md` |

Vil du tilføje et nyt dokument til /help-siden: tilføj det i `DOCS`-tabellen i
`scripts/sync-help-docs.mjs` og i `DOCS`-listen i `src/pages/HelpPage.tsx`.
