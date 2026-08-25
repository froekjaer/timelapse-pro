# AI System Inventory And AI Act Readiness

**Status:** Arbejdsregister for AI Act-readiness  
**Caveat:** AI Act-klassifikation afhænger af konkret anvendelse, kunde, autonomy og effekt på personer.

## 1. AI principle

TimeLapse Pro AI må som baseline være:

- observerende;
- klassificerende;
- anbefalende;
- under menneskelig kontrol.

AI må ikke uden separat godkendt design:

- træffe irreversible beslutninger om personer;
- ændre desired configuration automatisk;
- beslutte adgang, disciplinære forhold eller ansættelses-/arbejdspladsforhold;
- skjule billedmateriale uden audit og menneskelig mulighed for review.

## 2. AI system register

| System | Formål | Input | Output | Provider/runtime | Risk note | Status |
|---|---|---|---|---|---|---|
| Image quality diagnostics | Skarphed/lys/eksponering | Capture image/metadata | Quality score/deviation | Local code/model | Lav, teknisk drift | Aktiv/verify |
| AI tagging/search | Scene-/objekt-tags | Capture image | Tags/fritekst | Local Ollama eller cloud provider | Kan indeholde persondata | Conditional |
| Commissioning diagnostics | PASS/deviation/fail støtte | Service operation outputs | CommissioningReport | Local rules/logic | Ikke autonom juridisk beslutning | Aktiv |
| Future AI Service Assistant | Teknisk hjælp | Logs/status/config | Forslag/diagnose | TBD | Må ikke udføre hardware uden Service Operations/capabilities | Ikke aktiv |

## 3. Human oversight

Minimum controls:

- AI-output skal markeres som anbefaling/diagnostik hvor det kan påvirke teknikerbeslutning;
- tekniker/admin skal kunne se underliggende evidence;
- kritiske handlinger går gennem Service Operations, PDP, capability og audit;
- AI må ikke bypass'e session, grant, timeout eller hardware leases;
- fejl/deviation kan eskaleres til menneskelig review.

## 4. Data governance

| Kontrol | Status | Note |
|---|---|---|
| AI input documented | Delvist | Billeder, metadata, logs |
| AI output documented | Delvist | Tags/quality/report |
| Provider/region documented | Mangler pr. deployment | Særligt cloud-AI |
| Retention documented | Delvist | Skal følge billede/metadata policy |
| Prompt/model versioning | Delvist | Skal bindes til release evidence hvor relevant |
| Bias/quality monitoring | Mangler | Relevant ved person-/arbejdspladskontekst |

## 5. Classification gate

Før AI-funktion aktiveres for en kunde/site:

- beskriv formål og output;
- bekræft at output ikke bruges til højrisiko-formål uden separat vurdering;
- dokumenter provider/runtime og region;
- dokumenter retention;
- dokumenter menneskelig kontrol;
- dokumenter om kunden skal informere brugere/registrerede.

