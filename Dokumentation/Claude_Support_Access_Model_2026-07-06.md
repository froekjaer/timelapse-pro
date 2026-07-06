# TimeLapse Pro — Kontrolleret Support-adgang til Staging/Prod (Break-Glass-model)

**Forfatter:** Claude · **Dato:** 2026-07-06 · **Status:** Design-notat til godkendelse, INGEN kode skrevet
**Beslægtet:** `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §5 (agent-adgangspolitik),
`GO_LIVE_CHECKLIST_v10.md` §M, `RISK_ASSESSMENT_v10.md` R19,
`Claude_Intern_CA_mTLS_Design_2026-07-05.md` (device-CA, samme kryptografiske familie af
løsninger, men en BEVIDST ADSKILT tillidskæde — se §4).

> **Dette er et design-/beslutningsoplæg, ikke en implementering.** Ingen kode, script eller
> CA-nøgle er oprettet i denne omgang. Formålet er at få den tekniske model og de politiske
> principper på plads, generisk dokumenteret, før noget bygges — jf. projektets faste
> "dobbelttjekker før du udfører"-praksis, særligt vigtigt her fordi emnet er adgangskontrol til
> systemer med reelt kundedata.

---

## 1. Baggrund og formål

Peter besluttede 2026-07-05 en permanent politik: "Hverken Codex eller dig har eller vil få
adgang til staging og Prod. Kun vores R&D udviklingssystem" (dokumenteret i
`MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §5, `GO_LIVE_CHECKLIST_v10.md` M-02, `RISK_ASSESSMENT_v10.md`
R19). Det er stadig **standardtilstanden**.

2026-07-06 uddybede Peter dette: "Jeg tænker vi (trods min tidligere udtalelse) skal have en
kontrolleret og logget adgangsmulighed for dig (Codex) til support adgang, som kan anvendes i
forbindelse med installation og fejlsøgning/fejlretning. Det skal selvfølgelig være dokumenteret
generisk, så alle kan forholde sig til det."

**Dette er ikke en modsigelse af den permanente politik — det er en modning af den.** SABSA og
IEC 62443 anbefaler netop dette mønster for administrativ fjernadgang til driftskritiske/
kundedata-bærende systemer: i stedet for et binært "ingen adgang nogensinde" (som i praksis
tvinger Peter til at være eneste fejlretter, uden mulighed for hjælp, selv i en krisesituation)
går man til **default-deny med en kontrolleret, tidsbegrænset, logget undtagelsesvej**
("break-glass access") — en anerkendt kontrolform under ISO 27001 A.9 (adgangsstyring) og IEC
62443 SR 2.1 (authorization enforcement)/SR 2.11 (audit).

Peters designvalg (afklaret 2026-07-06, se §3-5):

1. **Gælder for begge agenter** (Claude og Codex), ikke kun Codex.
2. **Teknisk mekanisme:** tidsbegrænset SSH-nøgle/konto.
3. **Livscyklus:** aktiveres manuelt af Peter pr. session, respekterer en eventuel kunde-specifik
   accept/afvisning (implicit eller per-case), udløb fastsættes som en del af selve aktiveringen,
   og hver aktivering genererer et **signeret ticket**, logget til audit.

---

## 2. SABSA-forankring (kort)

| SABSA-lag | For dette system |
|---|---|
| **Kontekstuelt** (forretning) | Peter skal kunne få agent-hjælp til installation/fejlsøgning på staging/prod uden at opgive den kontrol og det kundetillids-løfte, der lå i den oprindelige "aldrig nogensinde"-politik. |
| **Konceptuelt** (attributter) | *Controlled, Accountable, Time-bound, Revocable, Non-standing* — adgang er undtagelsen, ikke normaltilstanden, og efterlader et uafviseligt spor. |
| **Logisk** | Separat Support-CA (IKKE samme tillidskæde som device-CA'en, §4) udsteder korttidslevende SSH-brugercertifikater; hver udstedelse producerer et signeret ticket i samme mønster som det eksisterende `ChangeTicket`-koncept. |
| **Fysisk** | Support-CA's private nøgle opbevares samme sted/mønster som Root CA'en fra #52-designet (`/etc/timelapse/...`, udenfor Git-repo og udenfor agenters fil-værktøjers rækkevidde) — men i en ADSKILT fil/nøglepar. |
| **Komponent** | `ssh-keygen -s` (SSH-certifikat-udstedelse, indbygget i OpenSSH — ingen ny afhængighed), `sshd_config TrustedUserCAKeys`, samme GPG-signeringsmønster som `ChangeTicket` (`content_sha256`+`signature`+`signed_by`). |
| **Drift** | Peter ejer aktivering/kunde-samtykke-tjek; Claude/Codex ejer kun brugen af den udstedte, tidsbegrænsede adgang inden for dens gyldighedsperiode. |

**Standard-kroge:** ISO 27001 A.9.2 (bruger-adgangsstyring)/A.9.4 (privilegeret adgang); IEC 62443
SR 2.1/2.5/2.11 (autorisation, session-lock, audit); GDPR art. 32 (passende tekniske
foranstaltninger) — særligt relevant fordi staging/prod kan bære reelt kundedata (Kirkbi A/S i
dag, flere kunder senere).

---

## 3. Princip: default-deny + kontrolleret undtagelse

- **Standardtilstand er uændret: INGEN stående adgang.** Der findes ingen permanent SSH-nøgle,
  konto eller token for Claude/Codex på staging/prod, hverken før eller efter denne model er
  bygget. Dette er den vigtigste invariant — break-glass-modellen erstatter ikke default-deny,
  den tilføjer en kontrolleret undtagelsesvej OVENPÅ den.
- **Kun Peter kan aktivere adgang.** Hverken Claude eller Codex kan selv anmode om eller udstede
  et adgangscertifikat — det er en handling Peter udfører, typisk i sin egen terminal, på
  opfordring fra en konkret installations-/fejlsøgningssituation.
- **Enhver aktivering er tidsbegrænset fra oprettelsen** (ikke et efterfølgende, separat
  "husk at lukke den igen"-trin) — se §5 for den tekniske håndhævelse.
- **Enhver aktivering er sporbar til en konkret grund, en konkret agent og en konkret maskine** —
  ingen anonyme eller generiske "support-konti".

---

## 4. Hvorfor en SEPARAT Support-CA (ikke device-CA'en fra #52)

`Claude_Intern_CA_mTLS_Design_2026-07-05.md` beskriver en Root/Issuing-CA-hierarki til at udstede
**device**-klientcertifikater (Orange Pi-enheder). Det er fristende at genbruge samme CA til også
at udstede **admin/support**-SSH-certifikater — men det anbefales bevidst IKKE:

- **Separation of duties/trust domains (IEC 62443 zone-tænkning anvendt på PKI selv):** en
  kompromitteret device-signeringsnøgle bør aldrig kunne bruges til at udstede en
  administrator-adgang til Headend-værten, og omvendt. De to CA'er beskytter fundamentalt
  forskellige ting (device-identitet vs. menneske/agent-administrativ adgang til selve
  serveren) og bør derfor have adskilte nøgler, adskilte udstedelsesprocedurer og adskilte
  kompromitteringskonsekvenser.
- **Forskellig levetidsprofil:** device-certifikater er nu besluttet til 10 års default-levetid
  (§4.3 i CA/mTLS-designet) — det modsatte af, hvad en support-adgangsmekanisme skal have (timer,
  ikke år). At blande de to i samme CA-hierarki ville gøre det nemt utilsigtet at anvende en
  "lang levetid er normalt her"-tankegang det forkerte sted.
- **Enkel at bygge parallelt:** en Support-CA er teknisk set blot endnu et
  `ssh-keygen -t ed25519 -f support-ca-key`-nøglepar, samme mønster og samme opbevaringssted-
  konvention (`/etc/timelapse/ca/support/`) som Root CA'en — ingen ny infrastruktur, kun endnu et
  nøglepar med sit eget, snævre formål.

---

## 5. Teknisk mekanisme — SSH-certifikater med indbygget, kryptografisk udløb

**Hvorfor SSH-certifikater (ikke blot en midlertidig konto/nøgle med et manuelt slettet gyldighed):**
OpenSSH understøtter native, korttidslevende brugercertifikater (`ssh-keygen -s <CA-nøgle> -I
<ticket-id> -n <principal> -V <start>:<slut> id_agent.pub`). Gyldighedsvinduet er indlejret i selve
certifikatet og håndhæves af `sshd` ved hvert forsøg på forbindelse — der er intet cron-job, ingen
"husk at deaktivere kontoen bagefter"-risiko, og ingen mulighed for at glemme at lukke adgangen
igen. Dette matcher direkte Peters krav om at "udløb markeres som en del af aktiveringen".

**Foreslået flow (skitse, kode IKKE skrevet):**

1. **Behov opstår** — Peter skal have agent-hjælp til installation eller fejlsøgning på en
   konkret staging-/prod-maskine.
2. **Kunde-samtykke-tjek (manuelt, af Peter, før aktivering):** Peter bekræfter hvilke(n)
   kunde(r) har data på den pågældende maskine, og om agent-support-adgang under denne session er
   dækket af kundens eksisterende databehandleraftale (implicit, hvis DPA'en allerede generelt
   tillader denne slags support-adgang for underleverandører/udviklere) eller kræver et separat,
   eksplicit "ja" for netop denne session. Dette svarer til den sondring, der allerede er etableret
   for Kirkbi A/S (DPA vs. eksplicit udviklings-tilladelse, se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`
   §4) — men her for LIVE support-adgang, ikke udviklingsbrug af billeddata. Resultatet af dette
   tjek (hvilken kunde, hvilken hjemmel, ja/nej) skal stå i selve ticketen (§6), ikke kun huskes.
3. **Peter kører et lokalt script** (fx `grant_support_access.sh <maskine> <agent> <varighed>
   <formål>`), som han selv udfører — hverken Claude eller Codex kan starte dette:
   - Genererer et nyt, engangs SSH-keypar TIL SESSIONEN (agenten har ALDRIG en forudeksisterende
     privatnøgle på denne maskine).
   - Signerer den offentlige nøgle med Support-CA'en: `ssh-keygen -s support-ca-key -I <ticket-id>
     -n <agent-principal> -V <start>:<slut> agent-session.pub`.
   - Skriver et **signeret ticket** (§6) til en append-only audit-log.
   - Udleverer privatnøglen til agenten via den kanal, Peter allerede bruger til at kommunikere
     med agenten (dvs. Peter forbliver i kontrol af selve overdragelsen — der er ingen automatisk
     "agenten henter selv sin nøgle"-mekanisme).
4. **Agenten bruger certifikatet** til at forbinde via SSH i sessionens levetid.
5. **Ved udløb** afviser `sshd` automatisk yderligere forbindelsesforsøg med det pågældende
   certifikat — ingen manuel oprydning nødvendig. `sshd_config` på staging/prod skal have
   `TrustedUserCAKeys /etc/timelapse/ca/support/support-ca-key.pub` konfigureret.
6. **Tidlig tilbagekaldelse** (før udløb, fx hvis sessionen afsluttes tidligere end planlagt):
   Peter kan bruge en SSH Key Revocation List (`ssh-keygen -k`, `sshd_config
   RevokedKeys`) uden at skulle rotere hele Support-CA'en — anbefales tilføjet til designet, selv
   om det ikke var eksplicit efterspurgt, fordi "udløb markeret ved aktivering" og "mulighed for at
   lukke tidligere" er to forskellige, begge ønskværdige egenskaber.

---

## 6. Signeret ticket og audit-log

Genbruger **mønsteret** fra det allerede eksisterende `ChangeTicket`-koncept
(`headend/database.py:345` — signeret, menneske- og maskinlæsbart, `content_sha256`+`signature`+
`signed_by`) — men IKKE selve tabellen, da `ChangeTicket` er tæt koblet til software-
opdateringsflowet (`pending_update_id`, `artifact_id`, `sbom_ref`, `rollback_plan` osv., som ikke
giver mening for en adgangstildeling). Anbefaling: et nyt, parallelt "AccessTicket"-koncept med
samme signerings-disciplin, minimum indeholdende:

| Felt | Indhold |
|---|---|
| `ticket_id` | Unik, matcher SSH-certifikatets `-I`-identitet |
| `agent` | `claude` eller `codex` |
| `machine` | `staging` eller `prod-<navn>` |
| `purpose` | Fritekst: installation, fejlsøgning, andet |
| `customer_scope` | Hvilke(n) kunde(r) har data på maskinen |
| `customer_consent_basis` | `implicit_dpa` / `explicit_per_case` / `no_customer_data` + evt. reference |
| `valid_from` / `valid_until` | Matcher SSH-certifikatets gyldighedsvindue |
| `granted_by` | Altid Peter (kun han kan udstede) |
| `content_sha256` + `signature` + `signed_by` | Samme GPG-signeringsmønster som `ChangeTicket` |

**Om implementering:** dette kan enten blive en helt ny tabel (`access_tickets`), eller en
`ticket_type`-diskriminator-kolonne på den eksisterende `change_tickets`-tabel, der lader UI'ens
eksisterende ChangeTickets-side (`ChangeTicketsPage.tsx`) også vise adgangstildelinger.

**Rådgivende anbefaling (periodisk tjek #80, Claude — baseret på faktisk kodelæsning af
`headend/database.py:345-434` og `ChangeTicketsPage.tsx`, ikke kun abstrakt afvejning):
separat `access_tickets`-tabel, IKKE en diskriminator på `change_tickets`.** Tre konkrete fund
understøtter dette:

1. **Feltmisforhold i begge retninger.** `ChangeTicket` har 8 deployment-specifikke felter
   (`pending_update_id`, `update_type`, `artifact_id`, `sbom_ref`, `test_evidence_ref`,
   `rollback_plan`, `reboot_required`, `maintenance_window`) der alle ville stå `NULL` for en
   adgangstildeling. Omvendt mangler `ChangeTicket` alle §6-adgangsfelterne (`agent`, `machine`,
   `customer_scope`, `customer_consent_basis`, `valid_from`/`valid_until`) — de skulle tilføjes
   som nullable kolonner, der kun giver mening for den ene `ticket_type`. Resultatet er en tabel
   hvor ca. halvdelen af kolonnerne altid er tomme afhængig af rækkens type — et klassisk
   "sparse/polymorphic table"-antimønster, ikke bare smag.
2. **Status-vokabularet er inkompatibelt, ikke bare et navnevalg.** `ChangeTicket.status` er
   hårdkodet til deployment-livscyklussen (`draft|ready|pending_approval|approved|rejected|
   deployed|rolled_back|cancelled`) — og `ChangeTicketsPage.tsx` (linje ~58-60, 268-273) har
   UI-farvekoder og knap-logik der antager netop disse værdier (`disabled={selected.status ===
   'approved'}` osv.). Et AccessTicket har en helt anden livscyklus (`active`/`expired`/
   `revoked` — tid-baseret, ikke godkendelses-baseret). At presse begge ind i samme `status`-felt
   kræver enten at overbelaste den eksisterende enum (risiko: en fremtidig deployment-specifik
   statustjek matcher ved et uheld en adgangs-status, eller omvendt) eller et andet felt ved siden
   af — hvilket reelt er det samme som en separat tabel, bare mere indirekte.
3. **Konsistent med §4's eget separations-princip.** §4 begrunder allerede en SEPARAT Support-CA
   (ikke device-CA'en) med separation-of-duties/trust-domains. Samme argument gælder her: et
   AccessTicket dækker levende, menneskestyret SSH-adgang til produktionsdata; et ChangeTicket
   dækker godkendt softwareudrulning. At blande dem i én tabel/UI-side betyder at RBAC/visning
   ("hvem må se support-adgangs-historik vs. deployment-historik") skal styres pr. række i stedet
   for pr. tabel/endpoint — mere kompleks adgangskontrol-logik for en marginal kode-besparelse.

`ticket_id`-navnerummet og GPG-signeringsmønsteret (`content_sha256`+`signature`+`signed_by`) bør
stadig genbruges på tværs af begge tabeller — kun selve tabelstrukturen bør holdes adskilt. Dette
er en anbefaling til beslutningsstøtte, ikke en implementeret ændring; ingen kode eller migration
er skrevet.

**Audit-log:** hver aktivering (ticket-oprettelse) OG hver faktiske SSH-login/logout i
gyldighedsvinduet bør ende i den eksisterende SIEM/syslog-modtager (`dk.froekjaer.timelapse-syslog`,
allerede dokumenteret i `SERVICES_OG_DRIFT_kilde_til_sandhed.md`), så adgangshistorik er synlig i
UI'ens SIEM-side sammen med anden sikkerhedstelemetri — ikke en isoleret logfil kun Peter kan se.

---

## 7. Forhold til den eksisterende permanente politik

Denne model ÆNDRER teksten i tre eksisterende dokumenter fra "aldrig, ingen undtagelser" til
"default-deny, med en kontrolleret, logget, tidsbegrænset undtagelsesproces" — selve
standardtilstanden (ingen stående adgang) er uændret:

- `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §5 — opdateret til at henvise til denne model (se
  ændringen foretaget i samme runde som dette dokument).
- `GO_LIVE_CHECKLIST_v10.md` M-02 — status opdateret til at reflektere break-glass-undtagelsen.
- `RISK_ASSESSMENT_v10.md` R19 — scoren revurderes ikke i denne omgang (ingen kode er skrevet
  endnu, så den faktiske risikoreduktion/-øgning kan først vurderes, når mekanismen er bygget og
  testet) — men beskrivelsen opdateres til at nævne den planlagte kontrol.

---

## 8. Hvad der IKKE er besluttet/bygget endnu

- **Ingen kode, script eller CA-nøgle er oprettet.** Dette er udelukkende et design-/
  principoplæg, jf. den samme forsigtighed som `Claude_Intern_CA_mTLS_Design_2026-07-05.md`
  (auth-/adgangs-nær kode fortjener sin egen, fokuserede runde).
- **AccessTicket-skema** (ny tabel vs. udvidelse af `ChangeTicket`) — **rådgivende anbefaling
  givet 2026-07-06 (periodisk tjek #80):** separat `access_tickets`-tabel, se §6 for begrundelse
  (feltmisforhold, inkompatibelt status-vokabular, UI-kobling). Stadig Peters/Codex' endelige valg
  at træffe — intet kodet.
- **Hvem implementerer `grant_support_access.sh`** — Codex eller Claude — er ikke afklaret; da
  scriptet kun køres AF Peter, og aldrig af en agent, er der ingen "hvem har adgang til at skrive
  det"-konflikt, men det bør skrives og gennemgås grundigt før første brug, givet emnet.
- **Hvordan "kunde-samtykke implicit vs. eksplicit"-tjekket konkret dokumenteres pr. kunde** —
  i dag er dette kun formaliseret for Kirkbi A/S (DPA + eksplicit dev-tilladelse). Der findes
  endnu ingen generel, gentagelig proces for at slå en kundes samtykke-status op systematisk
  (fx et felt i CMDB/Customer-modellen) — det er i dag et manuelt Peter-tjek. Værd at rejse som en
  fremtidig forbedring, ikke en blocker for selve adgangsmodellen.
- **Relation til Codex' `AgentPrincipal`/service-principal-forslag** — det forslag handlede om
  teknisk håndhævelse af nul-adgang (defense-in-depth mod fejlkonfiguration). Denne model er det
  modsatte formål (en kontrolleret VEJ til midlertidig adgang) — de to bør designes til at
  koeksistere, ikke erstatte hinanden; `AgentPrincipal`-modellen kan fortsat fungere som en
  teknisk bagstopper der forhindrer ALT ANDET end netop denne break-glass-vej.
- **Netværks-rækkevidde for agent-SSH-forbindelsen er ikke verificeret (fundet periodisk tjek #78,
  Claude):** §5 trin 4 antager at agenten selv kan etablere en udgående SSH-forbindelse til
  staging-/prod-maskinen med det udstedte certifikat. For Claude specifikt kører alt shell-
  værktøj i et isoleret, sandboxed Linux-miljø med kun allowlistet netværksadgang — der er intet i
  den nuværende infrastruktur, der bekræfter at dette sandbox-miljø faktisk kan nå fx en privat IP
  på Peters hjemmenetværk (staging-iMac/prod-Mac Mini) over SSH, medmindre maskinen har en
  offentligt routbar adresse/portforward dedikeret til formålet. **Anbefaling, før Support-CA'en/
  `grant_support_access.sh` bygges:** verificér empirisk (fx et simpelt testforsøg fra agentens
  faktiske eksekveringsmiljø) om SSH-forbindelsen overhovedet kan etableres. Hvis ikke, skal §5
  udvides med enten (a) en offentligt tilgængelig, IP-allowlistet SSH-endpoint dedikeret til dette
  formål, eller (b) en anden overdragelsesmekanisme (fx Peter selv kører kommandoer dikteret af
  agenten, i stedet for at agenten selv forbinder). Begrænsningen gælder muligvis ikke Codex, hvis
  Codex' eksekveringsmiljø har bredere netværksadgang — bør afklares pr. agent, ikke antages fælles.

---

## 9. Dokumenthistorik

| Dato | Ændring |
|---|---|
| 2026-07-06 | Claude: Første version — design-notat for kontrolleret support-adgang, svar på Peters anmodning om at blødgøre den permanente nul-adgang-politik med en kontrolleret, logget undtagelsesvej. Ingen kode rørt. |
| 2026-07-06 (periodisk tjek #78) | Claude: tilføjet §8-punkt om uverificeret netværks-rækkevidde for agent-SSH-forbindelsen (sandbox-miljø vs. staging/prod-maskinernes private netværk) — ny observation, ingen tidligere runde havde tjekket dette. |
| 2026-07-06 (periodisk tjek #80) | Claude: besvarede §6/§8's åbne AccessTicket-skema-spørgsmål med en kodebaseret anbefaling (separat `access_tickets`-tabel) efter faktisk læsning af `headend/database.py` (`ChangeTicket`-model) og `ChangeTicketsPage.tsx` (status-UI-logik) — tre konkrete tekniske fund (feltmisforhold, inkompatibelt status-vokabular, UI/RBAC-kobling), ikke kun abstrakt afvejning. Rådgivning, ikke beslutning — ingen kode/migration skrevet. |
