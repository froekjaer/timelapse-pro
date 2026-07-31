# Architecture Decision Records (ADR)

Korte, nummererede beslutningsnotater. Én ADR = én arkitekturbeslutning, der er dyr at omgøre eller som binder flere spor/personer/AI-sessioner sammen.

**Hvorfor:** TimeLapse Pro udvikles af Peter + Claude + Codex på skift. Uden et fælles beslutningsspor risikerer vi at gen-diskutere eller stiltiende omgøre hinandens arkitektur. En ADR fastlægger *hvad* der blev besluttet og *hvorfor*, så alle — mennesker og AI — arbejder ud fra samme kontrakt.

## Regler

- **Bindende ved status `Accepted`.** En accepteret ADR er en arbejdsregel på linje med `CLAUDE.md`. Afvig ikke uden en ny ADR der superseder den.
- **Additiv historik.** ADR'er slettes ikke. En beslutning der ændres, får en ny ADR der `Supersedes` den gamle; den gamle sættes til `Superseded by ADR-XXX`.
- **Kort.** En ADR er en beslutning, ikke en plan. Detaljerede planer/roadmaps ligger i `Dokumentation/Arkitektur/` og refereres.
- **Reference i PR.** Arkitekturændringer bør referere den ADR de udmønter.

## Status-værdier

`Proposed` → `Accepted` → (`Superseded by ADR-XXX` | `Deprecated`). `Rejected` for forslag der ikke vedtages (bevares for historikken).

## Skabelon

```md
# ADR-XXX: <kort titel>

- **Status:** Proposed
- **Dato:** YYYY-MM-DD
- **Beslutningstagere:** Peter, Claude, Codex
- **Kontekst-referencer:** <links til risk/plan/handover>

## Kontekst
<Hvilket problem/kraft tvinger en beslutning frem?>

## Beslutning
<Hvad besluttes — præcist og normativt.>

## Alternativer overvejet
<Hvad blev fravalgt, og hvorfor.>

## Konsekvenser
<Positive / negative / neutrale følger. Hvad bliver lettere, hvad bliver sværere.>

## Standardmapping
<SABSA / IEC 62443 / CRA / NIS2 / GDPR hvor relevant.>

## Afgrænsning
<Hvad denne ADR IKKE beslutter (henvis til fremtidige ADR'er).>
```

## Register

| ADR | Titel | Status |
|-----|-------|--------|
| [ADR-0007](ADR-0007-Evolution-from-Product-to-Platform.md) | Evolution from Product to Platform | **Proposed 2026-07-22** |
| [ADR-001](ADR-001-platform-payload-split.md) | Platform/Payload-snit for edge-arkitekturen | **Accepted 2026-07-16** |

## Kandidater under owner-review

`../Arkitektur/TimeLapse_Core_Design_Principles_v1.md` er et **Proposed**
arkitekturgrundlag, ikke en ADR. Dokumentets følgende beslutningsemner er store nok
til at blive egne ADR'er, når Peter vælger at bringe dem til beslutning. De er ikke
bindende og må ikke implementeres som accepterede beslutninger endnu.

| Foreslået ADR | Afgrænsning |
|---|---|
| Local Service Gateway | Fælles platformgateway for lokal service frem for payload-specifik Bluetooth-service |
| Physical Presence Requirement | Fysisk aktivering før pairing og privilegeret lokal service |
| Bluetooth as Bootstrap Transport | BLE til discovery/bootstrap; krypteret lokal IP til dataintensiv service |
| Capability-based Service Authorization | Versioneret capability/rolle/policy-håndhævelse for serviceoperationer |
| No General-purpose Shell | Ingen vilkårlig shell eller command execution i normal service-mode |
| Retain until Explicit Disposition | Projektdata-lifecycle og eksplicit disposition; kræver afstemning med eksisterende retention/circular-buffer-policy |
