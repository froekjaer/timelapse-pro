# 04 — UI-gennemgang: menuer, ensartethed, mangler, brugervenlighed

Grundlag: `timelapse-ui/src` — 31 pages, `Navbar.tsx` (2 sektioner: 8 alm. punkter + 13 admin-punkter), `App.tsx`-routes. Statisk gennemgang (kode + struktur); adfærdstest på kørende UI er ikke udført her (jf. metode i 00).

## TPA-20 · **Mellem** · Menustruktur: 21 punkter i én flad liste er over kognitiv grænse

**Evidens:** `Navbar.tsx:30-53` — 8 + 13 punkter uden gruppering ud over admin-skellet.

**Vurdering:** For den daglige drift bruges realistisk 4-6 punkter (Enheder, Drift, Backup, Opdateringer, Tags, Indstillinger); resten er sjældne ekspertflader (SIEM, CMDB, Change tickets, Nøgler, Retention…). 21 sideordnede punkter gør de vigtige svære at finde og de farlige for lette at finde.

**Anbefaling:** Gruppér i 4 sektioner med overskrifter: **Drift** (Enheder, Drift, Opdateringer, Backup), **Indhold** (Tag søgning, Post-processing, Import, Timelapse video), **Sikkerhed & Compliance** (Compliance, SIEM, GDPR Sløring, Retention, Nøgler, SSH Tunnels), **Administration** (Brugere, System Admin, CMDB, Change tickets, Global Config, AI Styring, Open WebUI). Rollestyret synlighed findes allerede (`adminOnly`) og kan genbruges pr. sektion.

## TPA-21 · **Mellem** · Sprog-inkonsistens i navigationen

**Evidens:** Dansk og engelsk blandet i samme menu: "Enheder", "Brugere", "Opdateringer", "Indstillinger", "Tag søgning", "GDPR Sløring" vs. "Backup", "Global Config", "Change tickets", "Post-processing", "Retention", "Compliance", "SIEM", "Open WebUI", "System Admin". Også inkonsekvent kapitalisering ("Post-processing" vs "Change tickets") og da/en-blanding i tooltips ("Bildemanipulation" — stavefejl, norsk/dansk-hybrid, `Navbar.tsx:47`).

**Anbefaling:** Beslut ét UI-sprog pr. målgruppe (forslag: dansk til alt, behold fagakronymer SIEM/CMDB/GDPR) og indfør i18n-nøgler nu, mens UI'et er lille — kunde-UI'et får brug for det alligevel. Ret "Bildemanipulation" → "Billedbehandling".

## TPA-22 · **Mellem** · Navigations-arkitektur: routes uden menupunkt og navne-drift

**Evidens:** `App.tsx` har `/notifications`-route, men intet Navbar-punkt (kun klokke-ikon? ikke verificeret) — og pages som `CameraPage`, `CustomerPage`, `SitePage`, `DevicePage`, `LabPage`, `TimelapseVideoPage`, `DriftPage` nås kontekstuelt. Menupunktet "Drift" peger på `/observability` (navnedrift mellem route, page-navn `DriftPage` og label). `TagCleanupTab.tsx` ligger i `pages/` men er en tab.

**Anbefaling:** Lav en kort sitemap-doc (route → page → menuindgang → rolle) som canonical reference; omdøb så route/page/label matcher (`/drift` ⇄ DriftPage ⇄ "Drift"); flyt tab-komponenter til `components/`. Sitemappen afslører også forældreløse sider ved fremtidige ændringer.

## TPA-23 · **Lav** · Tooltips som primær hjælp

**Evidens:** Gode, informative tooltips på alle menupunkter (`Navbar.tsx`) — men tooltips er usynlige på touch og svære at opdage.

**Anbefaling:** Genbrug tooltip-teksterne som beskrivelser i sektionsoverskrifter/side-headers, så hjælpen også findes inde på siden.

## TPA-24 · **Mellem** · Brugervenlighed for de personaer der nu kommer til (staging/prod)

**Vurdering:** UI'et er bygget indefra-og-ud (operatørens værktøjskasse). Før første kunde-site: (1) Kunde-/site-manager-flow skal kunne gennemføres uden at se admin-begreber (RBAC-filtreringen findes — verificér at *alle* admin-sider håndhæver den server-side, ikke kun i menuen; hænger sammen med TPA-01-sweepen). (2) Enheder-siden er de-facto forside — giv den "alt er OK / X kræver handling"-status øverst, så dagligt tilsyn er ét blik. (3) Farlige handlinger (restore, retention-ændring, nøgle-tilbagekald, debug-mode) bør have ensartet confirm-mønster med konsekvenstekst — stikprøver tyder på at det varierer pr. side.

## Positivt

Konsekvent ikonbrug (lucide), rollestyring i navigationen, tooltips overalt, React 19 + TypeScript + Vite er tidssvarende, lint-gate med ratchet findes (`npm run lint:gate`). Strukturen pages/components er ren, og 31 sider uden router-rod er pænt for et system af denne bredde.
