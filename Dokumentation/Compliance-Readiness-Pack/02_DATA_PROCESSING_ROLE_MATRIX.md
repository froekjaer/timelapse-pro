# Data Processing Role Matrix

**Status:** Arbejdsmatrix til kontrakt, DPA og kundeonboarding  
**Caveat:** Roller afhænger af den konkrete aftale. Dette er teknisk/operationel readiness, ikke juridisk afgørelse.

## 1. Standard rolleantagelse

| Part | Sandsynlig rolle | Begrundelse |
|---|---|---|
| Kunde/site-ejer | Dataansvarlig | Kunden bestemmer hvorfor site fotograferes og hvem der må bruge materialet |
| TimeLapse Pro/Froekjaer | Databehandler | TLP driver systemet og behandler billeder/metadata på kundens vegne |
| Underleverandører | Underdatabehandlere eller tekniske leverandører | Afhænger af adgang til persondata og kontrakt |
| Tekniker | Autoriseret bruger på vegne af TLP | Skal være bundet til principal, grant, capability og audit |

## 2. Datakategorier

| Datatype | Eksempel | Persondata? | Primær kontrol |
|---|---|---|---|
| Capture-billeder | Byggepladsfoto | Ja, hvis personer/køretøjer kan identificeres | RBAC, retention, tenant/site isolation |
| Capture metadata | Tid, kamera, site, uploadstatus | Kan være indirekte | Audit, access control |
| GPS/site | Kameraets placering | Ikke normalt persondata alene | Site access control |
| AI-tags | "kran", "arbejdere", "støv" | Kan være persondata afhængigt af indhold | AI inventory, human review |
| Auditlogs | Bruger, handling, device, tidspunkt | Ja | Retention, integrity, least privilege |
| Technician session | Principal, grant, operations | Ja | EdgeServiceGrant, PDP, audit |
| Diagnostic bundle | Logs, service status, excerpts | Kan indeholde persondata/secrets | Minimization, expiry, secure sharing |

## 3. Subprocessor/service inventory

| Service | Rolle | Dataadgang | Readiness status | Action |
|---|---|---|---|---|
| Headend host | Primær behandling | Billeder, metadata, audit | Aktiv | Asset owner og backup/restore evidence holdes ajour |
| Edge device | Lokal capture/buffer | Billeder, device credentials | Aktiv | Edge convergence og credential lifecycle holdes ajour |
| Kunde-SFTP | Kundemodtagelse | Billeder/metadata for eget site | Delvist | Per-site SFTP profile/RBAC ownership verificeres |
| GitHub | Software/source/release | Ingen kundebilleder forventet | Aktiv | Release evidence og access governance |
| Cloudflare/tunnel | Transport/UI access | Trafik afhænger af TLS-terminering | Skal bekræftes | Dokumenter TLS/termination/cache posture |
| AI cloud provider, hvis aktiveret | Analyse | Billeder/metadata | Conditional | Region, DPA, data retention og opt-in dokumenteres |
| Lokal AI/Ollama | Analyse | Billeder lokalt på Headend | Aktiv/conditional | Model inventory og audit |

## 4. Data subject request workflow

| Trin | Ejer | Output |
|---|---|---|
| Kunde modtager anmodning | Kunde | Request-id, scope, site, periode |
| TLP teknisk søgning | TLP | Relevante captures/metadata eller bekræftet ingen fund |
| Kunde vurderer udlevering/sletning | Kunde | Beslutning og juridisk hjemmel |
| TLP udfører teknisk handling | TLP | Auditlog og completion evidence |
| Kunde svarer registreret | Kunde | Kundens svar |

## 5. Databrud og incident rolleflow

| Situation | TLP handling | Kunde handling |
|---|---|---|
| Mistanke om uautoriseret adgang | Containment, evidence, foreløbig vurdering | Informeres hvis kundedata kan være berørt |
| Bekræftet persondatabrud | Teknisk rapport, berørte sites/data, afhjælpning | Controller-vurdering og evt. anmeldelse |
| Edge tabt/stjålet | Revoke credentials, markér device risk, preserve audit | Vurder site/persondata risiko |
| Forkert SFTP/modtager | Stop upload, preserve evidence, korriger route | Vurder anmeldelse/kommunikation |

## 6. Minimum DPA-indhold

En databehandleraftale bør mindst dække:

- formål og behandlingsinstruks;
- kategorier af persondata og registrerede;
- sikkerhedsforanstaltninger: MFA, RBAC, audit, encryption, update process, backup;
- underdatabehandlere og ændringsvarsel;
- retention og sletning ved aftaleophør;
- incident notification timing og kontaktpunkter;
- audit-/assurance-rettigheder;
- international overførsel/cloud-AI hvis aktiveret;
- supportperiode og patch-SLA.

