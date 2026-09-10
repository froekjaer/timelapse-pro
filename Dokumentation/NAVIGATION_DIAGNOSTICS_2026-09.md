# Navigationsdiagnostik — 10. september 2026

Status: klargjort og isoleret testet på `codex/navigation-diagnostics-20260910`, base `e7ec9fb3`. Ikke installeret på live Headend af denne task. Formål: placér de observerede 4–15 sekunders pauser fra klik til brugbart dashboard/kameraside uden at gætte ud fra serverlog alene.

## Installation gennem eksisterende releaseflow

1. Afstem aktuel main og åbne PR'er; denne ændring berører App, main-entry, API-klient, auth-logout, Dashboard og DevicePage. Bevar Claudes seneste ændringer. Gennemse ændringen og kør nedenstående checks.
2. Byg UI med `npm run build` i et isoleret checkout (prebuild genererer nødvendige hjælpedokumenter). Brug projektets eksisterende deploymentprocedure til den verificerede revision; byg aldrig over en anden agents arbejde. Bevar nødvendige gamle hash-assets under releaseovergang, så åbne faner ikke mister deres lazy chunks.
3. Medtag `headend/services/navigation_timing.py` og middleware-registreringen. For servermålinger sættes `TIMELAPSE_NAV_DIAGNOSTICS=1` i Headend-servicens eksisterende miljøkonfiguration, og servicen genstartes gennem den normale driftsprocedure. Uden flaget virker browserrapporten, men SQL-/app-/loop-tider mangler. Der er ingen DB-migration eller ny endpoint.
4. Kontroller normal login/MFA og adgang før test. Åbn brugerens sædvanlige URL, genindlæs til den nye build, og aktiver målingen som nedenfor. Test på udviklingsmiljø først; denne dokumentation er ikke evidens for live rollout.

## Brug — ingen udviklerværktøjer nødvendige

Som administrator åbnes **Fejlsøg ventetid** under navigationen og **Start måling og genindlæs** vælges. Brug derefter menuer og kameraer normalt. Efter en pause vælges **Vis tidsrapport** eller **Hent tidsrapport**. Rapporten vises som læsbar JSON i siden og kan læses gennem Codex-browserens DOM. Ingen automatisk upload.

Der gemmes højst 300 aktuelle events og tre snapshots af langsomme dashboard-/kameranavigationer (mindst 3 sekunder, fanen synlig ved frame-markøren). Data er begrænset til den aktuelle sideindlæsning; hent rapporten **før en ny genindlæsning**, som starter en ny rapport. Aktivering overlever genindlæsning i samme fane via sessionStorage. Stop/slet-knappen og eksplicit logout sletter måledata og slår målingen fra. Lukning af fanen afslutter den normale sessionStorage-livscyklus. Diagnoseflaget er ikke en adgangsrettighed.

## Hvad rapporten betyder

- `navigation`: klik/browservendt navigation, anonymiseret rutetype og lokalt løbenummer. Link-klik registreres før React håndterer navigationen. Forhindret navigation kan stadig have en klikmarkør; markøren alene beviser ikke, at en rute blev åbnet.
- `bootstrap-start`/`bootstrap-finished`: entry-koden venter blandt andet på eksisterende `bootstrapToken()`/settings-kald. Resource Timing dækker tidligere dokument-/assetindlæsning, hvor browseren stiller det til rådighed.
- `route-module-wait`/`route-module-resolved`: React Suspense-fallbacks levetid; inkluderer scheduling og er ikke en præcis separat downloadmåling.
- `request-dispatch`, `response-headers` (fetch), `response-decoded` (axios): afsendelse og responsmilepæle. `resource` giver requeststart, første/sidste byte, DNS/connect, overførselsstørrelser og eventuelt servermålinger. Forskellige eventtyper markerer forskellige trin og må ikke lægges sammen som separate ventetider.
- `frame-ready`: dobbelte animation frames efter dashboard/kamerasidens loading-state bliver klar. Det er en renderingmulighed, **ikke et bevis på faktisk pixel-paint eller alle thumbnails færdige**. Øvrige sider har route/resource-målinger, men ingen generel data-klar-garanti. Thumbnail-resourcer viser deres afsluttede overførsler.
- `longtask`: browserens rapporterede lange main-thread-opgaver, når API'et understøttes. Manglende events beviser ikke fravær af blokering. Fanens synlighed registreres; baggrundstiming kan være throttlet.
- `app`: serverstart til response headers; inkluderer ikke al body-streaming eller Nginx/browsers kø før ASGI. `sql`: succesfuld SQL cursor execution, inklusive DB-ventetid under den udførelse. **Ekskluderer pool-checkout, resultatfetch, ORM-mapping og fejlede SQL-kald.** `sql_count`: antal målte SQL-udførelser. `loop_lag`: maksimal overskridelse af en 50 ms timer under requesten; kan skyldes arbejde i en anden samtidig request. Det er ikke automatisk root cause.
- `trace`: servergenereret tilfældigt ID fra `Server-Timing`; match med `navdiag trace=...` i eksisterende Headend-log. Serveren accepterer ikke klientens eget trace-ID. Statisk Nginx-medie-/assetlevering har ikke nødvendigvis disse headers.

Rapportens `at` er UTC-observationstid; `ms` og Resource Timing-felter er relative til dokumentets performance time origin. Manglende serverfelter betyder utilgængelige, ikke nul ventetid. Ressourceevents indeholder kun anonymiserede kategorier: ingen rå URL, query, billednavn, device-/kunde-ID, host, token, body, SQL eller fejltekst. Login/adgangskontrol ændres ikke. Eksterne requests får ikke diagnoseheader fra instrumenteringen.

## Verifikation

- `node --test scripts/tests/navigation-diagnostics.test.mjs` fra UI: frakoblet standard, anonymisering, bounded retention, header-bevaring/same-origin, stop/slet og langsomme/stale/skjulte navigationer.
- `DATABASE_URL=sqlite:// TIMELAPSE_ENV=test PYTHONPATH=. <isoleret-python> -m pytest tests/test_navigation_timing.py tests/test_architecture_ratchet.py -q -p no:randomly`: ingen import af hele Headend, ingen drift-DB. Tester middleware frakoblet/umarkeret, SQL i worker, samtidighed, afvisning og blokeret loop. Ratchet uændret.
- TypeScript og fokuseret ESLint på nye moduler/integration; `npm run build` i isoleret checkout.
- Faktisk browser mod loopback-fixture med syntetisk administrator og tomme kundedata: start-knap genindlæste, aktiv indikator og rapportknap virkede. En bevidst 1,2 s asynkron serverventetid gav app=1201,04 ms, resource=1204,5 ms, loop_lag=1,37 ms, SQL=0, og frame-ready ved 1584 ms fra dokumentstart. Det er test af målefunktionen, ikke reproduktion af Peters produktionsproblem.

## Overhead og rollback

Kun aktiverede browserfaner observerer events; sessionStorage-skrivninger samles højst én gang pr. 250 ms. Serveren kræver både miljøflag og `X-TLP-Diagnostics: 1`. SQL-listeneren udfører kun tidsmåling med aktiv request-kontekst. En sampler-task lever kun gennem den målte request og ryddes også ved fejl.

Stop målingen i browseren. Fjern miljøflaget og brug normal servicegenstart for at deaktivere serverdelen helt. Koden kan rulles tilbage som en almindelig revision; ingen data- eller skemamigration kræves. Diagnosticér først en faktisk langsom hændelse; påstå ikke at denne ændring i sig selv retter langsomheden.
