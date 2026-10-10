# TimeLapse Pro — Peter Product Intent Notes

**Dato:** 2026-09-16  
**Status:** Provenance supplement to Requirements & Intent Archaeology  
**Kildeprincip:** Kun eksplicitte eller tydeligt dokumenterede Peter-afklaringer/ønsker fra projektets handover-/decision-history. Ikke et selvstændigt autoritativt kravregister.

Formålet er at bevare de små, konkrete produktintentioner der ofte forsvinder mellem feature-dokumenter og kravregistre.

## 1. Brug systemet som et menneske

### “Tryk på alt” acceptance — CURRENT

Peter ønskede en praktisk, fælles gennemgang af alle menuer, undermenuer og klikbare flows. Det førte til `UI_USECASE_CATALOG_2026-08-26.md`.

Intent:
- funktionalitet skal prøves i den faktiske UI;
- read-only navigation, CRUD, updates, backup, retention, credentials, terminal og technician flows skal vurderes som brugeroplevelse;
- automatiserede tests erstatter ikke denne UAT.

### Kontrolleret destruktiv UAT — CURRENT

Peter accepterede at hele data-lifecycle-flowet testes med 1–3 velvalgte gamle/testbilleder, når før/efter-state, audit og scope er klart.

Intent: vi skal ikke undlade at teste sletning/retention/redaction fordi testen er destruktiv; den skal udføres kontrolleret.

### Kontekstuel hjælp overalt — CURRENT

Peter ønskede at alle ikke-selvforklarende UI-parametre på sider/menuer/submenuer får relevant, kort hover-hjælp. Dette førte til `InfoTooltip`-arbejdet og senere `/help`.

Intent: UI skal kunne forstås uden at kende implementationen eller læse kildekode.

### Hjælp skal være tæt på konteksten — CURRENT

Den første flydende hjælpeknap blev senere flyttet til navbar/topområdet efter Peters ønske. Hjælp er URL-/kontekstdrevet og dokumentationen er source of truth.

## 2. Funktionalitet må ikke ofres for en kontrol der gør den ubrugelig

### Terminal skal faktisk fungere — CURRENT

Da break-glass transcript-løsningen gjorde terminalen praktisk ubrugelig, var Peters krav ikke “vælg hurtig fix eller mere debugging”, men at der skulle findes en løsning der faktisk virker.

Dette blev senere generaliseret i Direct-Edge terminalarbejdet:
- Ctrl-C;
- Tab completion;
- history arrows;
- Home/End;
- resize;
- reconnect;
- logout/expiry;
- brug uden Headend/internet.

Intent: sikkerhedskontroller er ikke succes, hvis den vigtigste recovery-capability reelt er ødelagt.

### Root/general-purpose shell i development — CURRENT

Peter korrigerede senere den foreslåede “No General-purpose Shell”-retning: i development/stabilization skal fuld login/debug/recovery-adgang bevares. Hardening må være additivt og må ikke skabe lockout eller central dependency.

## 3. Lokal management skal være recovery, ikke kun Bluetooth-feature

### Path-independent reachability — CURRENT

Peter præciserede, at Edge-management ikke er BT-PAN-only. Edge-hosted management/recovery skal kunne eksponeres gennem:
- BT-PAN;
- lokal WiFi/Ethernet/LAN;
- routed/customer networks hvor deployment-policy tillader det.

Authentication/authorization må ikke afhænge af netværksvejen.

### Samme værktøj, samme handling — CURRENT DESIGN INTENT

Ved TOTP-sync-hændelsen spurgte Peter, om `bootstrap_cli.py` og UI'en ikke skulle bruge de samme værktøjer. Undersøgelsen fandt tre parallelle implementationer af samme operation og samlede dem om én shared function.

Intent: samme logiske recovery/service-operation bør have én implementation/contract og flere UI/CLI-indgange — ikke flere divergerende kopier.

### Manuel nødventil — CURRENT PRINCIPLE

Peter bad konkret om en manuel TOTP-sync fra `bootstrap_cli.py`, selv om den permanente auto-sync blev rettet.

Intent: automatisering må gerne gøre nødvejen sjældent nødvendig, men må ikke fjerne en enkel lokal recoveryvej for samme failure class.

## 4. Updates: automatisering skal følge modenheden

### Ikke “stor samlet automation” før vi er modne — CURRENT/CONTEXTUAL

I september afviste Peter en stor samlet automatisering af update-processen og bad i stedet om et færdigt, brugbart, håndholdt flow og guide.

Intent:
- automatisér det der er dokumenteret og stabilt;
- behold menneskelig kontrol hvor flowet stadig modnes;
- lad ikke ønsket om en flot one-click pipeline skjule manglende artifact, migration, rollback eller health-evidence.

Dette er ikke et permanent forbud mod automation. Det er et modenheds-/evidensprincip.

### “Tag det hele undervejs” for dependencies — CURRENT

Da Python `venv_packages` blev synlige i CMDB/SBOM, bad Peter om at dependency reconciliation blev bygget som et fuldt governance-spor i stedet for blot at vise data.

Intent: inventar uden handlings-/governance-flow er utilstrækkeligt.

### Live outcome efter update — CURRENT LEARNING

Flere forløb bekræftede, at Peter ønsker at følge updatekæden i faktisk drift, ikke stoppe ved grønne tests eller `deployed` i DB. Det gælder OS bundles, Python dependencies, Ollama-runtime og Edge services.

## 5. Billed-/video-output skal svare til virkeligheden

### Dato/tid-overlay skal bruge rigtig capture-tid — CURRENT

Peter bad om at få “Dato/tid” færdig i timelapse-video. Løsningen måtte bruge det enkelte billedes reelle `captured_at`, ikke videoens elapsed PTS, fordi billeder kan mangle/komme uregelmæssigt.

Intent: output skal repræsentere den historiske virkelighed, ikke blot en teknisk videoklokke.

### Visuelt verificér når output er visuelt — CURRENT

Datetime-overlay blev ikke kun unit-testet; ægte frames blev renderet og visuelt inspiceret. Samme tanke bør gælde look matching, stabilization, redaction og andre visuelle capabilities.

## 6. Dokumentation og beslutningsarbejde

### Samme reviewpakke til alle — CURRENT GOVERNANCE INTENT

Ved governance-reviewet bad Peter om samme reviewmateriale til alle deltagere før endelig beslutning.

Intent: uafhængig review må ikke skabes ved at give forskellige skjulte præmisser, medmindre det er en bevidst testmetode.

### Alt der venter på Peter skal kunne ses — CURRENT

Peter har flere gange bedt om en prioriteret liste over GRC-/arkitekturpunkter der reelt kræver hans beslutning.

Intent: teknisk arbejde og ejerbeslutninger skal skilles; Peter skal ikke grave i logs for at finde sine beslutningspunkter.

### Fortsæt autonomt, men test undervejs — CURRENT OPERATING STYLE

I flere modulariseringsforløb bad Peter om at arbejdet fortsatte autonomt mens han var væk, men med test/verifikation undervejs.

Intent: agentautonomi er ønskelig når mandat og stop-gates er klare; det er ikke det samme som automatisk merge eller ret til consequential decisions.

## 7. Arkitektur og vedligeholdbarhed

### Få mere ud af `main.py` — CURRENT

Peter bad eksplicit om mere modularisering, hvilket førte til auth, tenant scope, camera API, settings, AI batch, edge-image osv. som separate domæner.

Intent: ny funktionalitet bør ikke automatisk gøre monolitten større; domæneejerskab og testbarhed er produktets langsigtede vedligeholdelseskrav.

### Genbrug generisk platform uden at stoppe TimeLapse — CURRENT

ADR-001 fastlægger platform/payload-retningen og den langsigtede mulighed for vandværk/sol/vind/andre edge/OT verticals, men med additiv migration og uden at forsinke TimeLapse Pro production-readiness.

## 8. R&D, staging og prod

### Tre miljøer har forskellige formål — CURRENT

Peter fastlagde:
- `rd`: aktiv udvikling/test;
- `staging`: software-parity med prod;
- `prod`: separat system og kundedata.

“lab mode” er kamera-tuning og må ikke forveksles med systemmiljøet.

### Agentadgang modnes fra absolut nej til kontrolleret undtagelse — CHANGED

2026-07-05: ingen Claude/Codex adgang til staging/prod.  
2026-07-06: default-deny bevares, men Peter ønskede kontrolleret/logget/tidsbegrænset supportadgang til installation/fejlsøgning.

Intent der består: ingen stående agentadgang og Peter/kunde-kontrol over consequential supportaccess.

## 9. “Alt skal hænge sammen” — recurring Peter intent

På tværs af forløbene gentages samme produktønske:

- UI og CLI for samme operation skal dele contract;
- DB-status skal stemme med runtime;
- dokumentation skal stemme med faktisk kode;
- update inventory skal kunne føre til governed handling;
- backup skal kunne restore;
- terminal skal være brugbar;
- capture status skal afspejle faktisk capture;
- published/help docs skal følge authoritative docs;
- capability skal overleve refaktorering, selv om implementationen flytter.

Dette er den praktiske baggrund for det senere godkendte princip om end-to-end traceability og runtime outcome over process completion.

## 10. Brug i Capability Map

Disse noter skal bruges som provenance ved formulering af invariants og acceptance tests. De skal **ikke** automatisk blive separate Golden Capabilities. Især ønsker der var konkrete fixes (fx TOTP sync-knap) skal normalt generaliseres til den bagvedliggende capability: recoverability, shared operation contracts og outcome verification.