# Forældet device-credential (TL-DCA63234D813) — runbook (v1)

**Dato:** 2026-07-04 (nat) · **Lukker:** R07 i `RISK_ASSESSMENT_v10.md` (stale credentials)
**Status:** Forberedt, IKKE eksekveret — kræver din bekræftelse først.

## Vigtig advarsel før du gør noget

`TL-DCA63234D813` er kun dokumenteret som "stale" (RISK_ASSESSMENT_v10.md linje 34/184)
— jeg fandt **ingen eksplicit beslutning om udfasning** noget sted i `HANDOVER_LOG.md`
eller andre dokumenter. "Stale" betyder her formentlig "ikke set længe", ikke
"bekræftet skrottet enhed". Systemets egen oprydningslogik (`_credential_cleanup_candidates`,
`headend/main.py`) nægter bevidst at auto-revokere en enheds ENESTE/primære credential
af samme grund — den kræver manuel gennemgang (`review_stale_primary`).

**Bekræft FØRST, før du revokerer noget:**
1. Er denne fysiske Orange Pi fysisk destrueret/kasseret, eller kan den dukke op igen?
2. Er den evt. allerede omfordelt til en anden kunde/site under et nyt device-ID?

## Sådan gør du (allerede eksisterende UI — ingen ny kode nødvendig)

Godt nyt: revoke/rotate-funktionaliteten findes allerede live i UI'en —
`timelapse-ui/src/pages/KeyManagementPage.tsx` er en færdig side, ikke kun en plan.

1. Åbn **Nøglehåndtering** i UI'en (kræver `super_admin`).
2. Find `TL-DCA63234D813`s credential(s) under CMDB-binding-fanen.
3. Klik **"Preview oprydning"** (dry-run) først — se hvad systemet selv foreslår,
   uden at ændre noget.
4. Hvis du er sikker på enheden er retired: klik **Revoke** på dens credential(s), angiv
   en tydelig begrundelse (fx "Fysisk enhed kasseret 2026-XX-XX, bekræftet af Peter").
5. Hvis enheden IKKE er retired, men bare har været offline længe: overvej i stedet
   **Rotate** (ny credential, gammel markeres `rotated`) — så mister den ikke adgang
   permanent, men den gamle nøgle kan ikke længere bruges hvis den er kompromitteret.

## Hvorfor jeg ikke gjorde dette selv i nat

Revokering er irreversibel uden en ny udrulning af credentials til den fysiske enhed —
hvis enheden mod forventning stadig er i drift et sted, ville jeg have låst den ude uden
nogen vågen til at opdage/rette det. Det er præcis den slags handling, "dobbelttjekker
før du udfører" (fra projektinstruktionerne) betyder jeg IKKE skal gøre alene, uden dig.
