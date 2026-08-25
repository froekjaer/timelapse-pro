# 01 — Sikkerhedsfund

Commit: `eed9e3c8`. Evidens angivet som fil:linje. Severity jf. 00_README.

## TPA-00 · **KRITISK** · Kendt fabriksstandard-TOTP-secret som fail-open fallback (SEC-016 — stadig åben)

**Evidens:** `headend/main.py:4075`, `:5187` (kommentar), `:5270`; `headend/database.py:333`; `edge/scripts/totp-service.py:123`. Den hardkodede secret `JBSWY3DPEHPK3PXP` er pyotp's offentligt kendte demo-secret. Logikken bruger den eksplicit som fallback når ingen enrolled secret findes (`… else {"secret": "JBSWY3DPEHPK3PXP", "sid": "factory-default"}`), og DB-kommentaren fastslår `NULL = fabriksstandard`. Dette blev identificeret som SEC-016 i handover-loggen 2026-07-15 med henvisning til Codex for fix — og er **stadig til stede** på HEAD (`eed9e3c8`).

**Risiko:** En BT PAN TOTP-secret der er kendt af hele verden = enhver kan generere gyldige TOTP-koder for enhver ikke-enrolled enhed. Fail-**open**: manglende secret giver adgang i stedet for at nægte. Direkte i strid med **CRA Annex I** (forbud mod kendte/default-credentials) og **IEC 62443-4-2 CR 1.5**. Dette er en go-live-blocker for enhver Internet-eksponering og især for "ny edge ude i den virkelige verden".

**Anbefaling (fail-closed):** (1) Generér en unik secret pr. enhed ved provisionering, gem i CMDB/DB. (2) Fjern den hardkodede fallback fuldstændigt — uden enrolled secret skal BT PAN-funktionen **nægte** (fail closed), ikke falde tilbage på en default. (3) Tilføj en CI-gate der fejler ved forekomst af kendte demo-secrets i kildekoden. (4) Roter/afvis alle enheder der pt. kører på factory-default før prod. Bør registreres i GRC som Kritisk med det samme.

## TPA-01 · **Lav** (nedgraderet 2026-07-31 efter Codex-evidens) · Route-auth-canary kaster KeyError i under-provisioneret miljø

> **KORREKTION 2026-07-31:** Dette fund var oprindeligt klassificeret **Høj** ("K1-gaten er rød på HEAD / ude af drift"). Det var **forkert**. Codex kørte suiten i fuldt CI-miljø (`agent/headend-generator-verification`, handover 2026-07-31): **39 passed**. Ruten `/api/settings/config` findes faktisk (`headend/ai/settings_api.py:231`, settings-routerens `/config` under prefix `/api/settings`). Årsagen til min oprindelige `KeyError` var et **sandkasse-dependency-gap**: uden den fulde requirements-liste mountes 6 af 8 high-risk-routere ikke (settings, import, review, ai/vocabulary), så deres ruter var fraværende. Per autoritetsrangordenen (verificeret runtime-evidens > sandkasse) står Codex' resultat: **gaten er IKKE rød i CI.**

**Reelt (lille) problem:** den gamle test indekserede `route_by_path[path]` direkte og kastede en kryptisk `KeyError` frem for en klar fejl, hvis en rute var fraværende (fx pga. manglende dependency eller omdøbt rute).

**Rettet (branch `feature/tpa-00-commissioner-auth`, commit `d266eb1`):** high-risk-sti-listen bevaret, men indekseringen erstattet af en tydelig assertion ("route ikke registreret — sørg for at alle dependencies er installeret") FØR auth-tjekket. Består i fuld CI; fejler højlydt og forståeligt i under-provisioneret miljø.

**Anbefaling (uændret, stadig relevant):** aktivér branch protection på `main` med krav om grøn CI (fuld dependency-liste) før push/merge — det er den reelle beskyttelse mod at en ægte auth-mangel slipper igennem.

## TPA-02 · **Mellem** · Edge-signering bruger Bearer-token som HMAC-nøgle (transitional), og mTLS/enheds-CA mangler fortsat

**Evidens:** `edge/security.py:1-42` — selvdokumenteret "transitional mutual-auth": HMAC-SHA256 med API-token som nøgle. Kendte åbne risici R05/R08 (ingen mTLS, ingen enheds-CA, ingen disk-kryptering) er fortsat åbne i risikoregistret.

**Risiko:** Token-tyveri = fuld enhedsimitation inkl. gyldige signaturer; signeringen tilføjer integritet/replay-metadata men ikke reel anden faktor. Acceptabelt i LAB; svagt for "ny edge ude i den virkelige verden".

**Anbefaling:** Før den nye edge udsendes: per-device nøglepar (Ed25519) genereret ved provisionering, public key registreret i CMDB, signering med enhedsnøglen (ikke tokenet). Fuld mTLS kan følge senere; nøgle-pr.-enhed er det afgørende spring og er allerede forudset i koden ("towards per-device signing keys or mTLS"). Positivt konstateret: al edge→headend-trafik har `verify=True` (TLS-validering) uden undtagelser (`edge/upload/headend_client.py:339-621`, `edge/ai/site_look_config_client.py:141`).

## TPA-03 · **Mellem** · MD5 som config-fingerprint, duplikeret 7 steder

**Evidens:** `headend/main.py:324, 4221, 4317, 12782, 12881, 15895` + `headend/api/service_access_api.py:79` — `config_version = md5(device_config)`.

**Risiko:** Ikke en aktiv sårbarhed (fingerprint, ikke kryptografisk beskyttelse), men (a) MD5 trigger findings i enhver ekstern audit/CRA-review og kræver så forklaring, (b) logikken er kopieret 7 gange — en fremtidig ændring rammer ikke alle steder (det er allerede sket: både `hashlib.md5` og alias `_hl.md5` bruges).

**Anbefaling:** Én hjælpefunktion `config_fingerprint()` med SHA-256; migrér additivt (nyt felt eller accepter re-sync én gang).

## TPA-04 · **Mellem** · Dynamisk SQL med interpoleret tabel-/kolonnenavn

**Evidens:** `headend/itim.py:134`, `headend/ai/ai_batch_submit.py:106`, `headend/ai/ollama_service.py:124`, `headend/ai/text_services.py:44` (`text(f"SELECT value FROM {tbl} …")`), `headend/tools/backfill_capture_metadata.py:304`, `edge/utils/database.py:230,248` (`f"… SET {col}=1 …"`).

**Risiko:** I de fundne tilfælde kommer `tbl`/`col` fra interne konstanter — ikke udnytteligt i dag. Men mønsteret er en injection-fælde ved næste refaktorering, og det unddrager sig statisk analyse. Værdier er korrekt parameteriseret (`:k`, `?`) — kun identifiers interpoleres.

**Anbefaling:** Whitelist-konstant (`ALLOWED_TABLES`/`ALLOWED_COLUMNS`) med eksplicit assert før interpolation, eller flyt til faste forespørgsler pr. tabel. Lav indsats, fjerner hele fældeklassen.

## TPA-05 · **Lav** · JWT/cookie-håndtering er i orden — med to skærpelser

**Evidens:** `headend/main.py:85-92` (JWT_SECRET: kræves eksplicit ≥32 tegn i produktion; ellers random pr. proces), `:791-795` (alg pinned til én algoritme ved både encode og decode), `:799-812` (cookie: HttpOnly, SameSite=Lax, Secure styret af `COOKIE_SECURE`, default `true` — `:99`), CORS med eksplicit origin (`:204-207`).

**Anbefaling:** (1) `SameSite=Strict` for admin-session-cookien, eller CSRF-token på muterende kald, da SameSite=Lax stadig tillader top-level GET cross-site; verificér at ingen muterende endpoints er GET. (2) Overvej kort JWT-levetid + refresh frem for `JWT_EXPIRE_H` timer flad levetid ved prod-eksponering.

## TPA-06 · **Lav** · Signaturverifikation på edge-requests: replay-vindue bør bekræftes

**Evidens:** `headend/main.py:2627-2711` verificerer signatur og parser timestamp/nonce; det blev ikke verificeret i denne gennemgang, om nonce-genbrug afvises og hvor stort tidsvinduet er (kræver dybere læsning af hele middleware-kæden).

**Anbefaling:** Dokumentér og test replay-beskyttelsen eksplicit (nonce-cache med TTL, maks. clock-skew). Én unit-test kan lukke usikkerheden.

## TPA-07 · **Lav** · Node-agent security-collector matcher på naive strenge

**Evidens:** `node-agent/collectors/security.py:294` — mønstre som `"eval("`, `"cmd="` i log-linjer.

**Anbefaling:** Fint som heuristik; markér den som heuristik i SIEM-visningen så fund ikke forveksles med verificerede detektioner.

## Positivt konstateret (skal siges højt i en fair audit)

Ingen `shell=True`, `pickle.loads`, `yaml.load` uden loader, `eval`/`exec` på inputdata eller `verify=False` i produktionskode (kun ML-relateret `model.eval()` i `edge/training/`, som er noget andet). Ingen hardkodede secrets fundet i sweep (JWT/nøgler kommer fra env/DB; Fernet-nøgle genereres eksplicit — `headend/cmdb.py:436-456`). Værdi-parametre i SQL er konsekvent parameteriseret. bcrypt til passwords. Rate-limiting (slowapi) til stede. CORS er ikke wildcard. Dette er væsentligt over gennemsnittet for et projekt i denne fase.
