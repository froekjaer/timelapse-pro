# Findings — Edge-generator-pipeline og TL-043EB9E72EFD (2026-08-04)

> **TILLÆG (samme dato, senere):** Peter foreslog `ssh -p 2201 orangepi@localhost`
> — dette virkede og gav FAKTISK, ny evidens der reviderer flere fund nedenfor.
> Se "Del E — Tillæg" til sidst i dokumentet. Læs Del E FØRST hvis du kun har
> tid til én sektion — den korrigerer F-02 og F-03 væsentligt.

**Format:** Per Mission Framework Collaborative Intelligence Evaluation Protocol
(`Dokumentation/Mission_Framework_Assessment/00_Collaborative_Intelligence_Evaluation_Protocol.md`)
— hvert fund har observation, evidens, impact, confidence, foreslået target-state,
anbefalet handling, dependencies, risiko, acceptkriterier. Ingen påstand uden
fil:linje- eller kommando-output-evidens.

**Scope:** Peters "Klargør ny Edge" + "Edge ISO"-flow for Orange Pi 4 Pro, fra
`headend/tools/hardware/orangepi4pro/target.yaml` gennem `inject_edge_image.py`
til den fysiske enhed `TL-043EB9E72EFD` ("Mod baggård"), sammenholdt med den
ældre referenceenhed `TL-C87FF9587CA0` ("Kamera 1").

**Adgang under undersøgelsen:** Ingen SSH til `TL-043EB9E72EFD` (`Connection
refused`). Ingen SSH til `TL-C87FF9587CA0` (`Permission denied` med Headends
operatørnøgle — ikke undersøgt yderligere, ude af scope for denne omgang). Al
enhedsspecifik evidens for `TL-043EB9E72EFD` er fra tidligere SSH-sessioner
samme dag (før SSH gik ned) + den lokale portals "Kør kommando"/Doctor-output
Peter selv har delt. Al databaseevidens er direkte `psql`-forespørgsler mod
`timelapse_db` kørt i forbindelse med denne rapport.

---

## Del A — Status lige nu (verificeret ved direkte DB-forespørgsel, 2026-08-04)

```
device_id                 | customer_name | site_name           | camera_name | status | first_seen
TL-C87FF9587CA0           | Frøkjær       | Nordre Villavej 17c | Kamera 1    | online | 2026-04-28
TL-MACMINI-HEADEND-TEST-1 |               |                     |             | online | 2026-06-07
TL-043EB9E72EFD           |               |                     | Mod baggård | online | 2026-08-04
```

`MOD-BAGGARD-NXHT` findes IKKE i `devices`-tabellen — slettet under oprydningen
kl. 10:52 (se HANDOVER_LOG samme dato). Den aktive `device_assignments`-række
for kameralokationen "Mod baggård" (id `e6338559-102f-470d-85ac-b242db9d58f1`)
peger korrekt på `TL-043EB9E72EFD` (assignment id 7, `unassigned_at` er NULL,
`assignment_type=zero_touch_enroll`). Den gamle `MOD-BAGGARD-NXHT`-tildeling
(id 6) er korrekt afsluttet (`unassigned_at` sat) — ren historik, ingen aktiv
konflikt. `TL-043EB9E72EFD.customer_id`/`site_id` peger korrekt på Hyldager
Fotografilm/Vardevej 26c, selvom de denormaliserede tekstfelter
`customer_name`/`site_name` er tomme (se F-11).

**Konklusion:** Der er ikke "forkerte enheder" i CMDB som følge af oprydningen
— der er én ekstra, harmløs historisk tildelingsrække. Den fysiske enhed ER
korrekt registreret som `TL-043EB9E72EFD` og er synlig under Enheder/Dashboard.
Det oplevede problem er, at ENHEDEN SELV (lokal totp-service/hostname) stadig
udgiver sig for at være `MOD-BAGGARD-NXHT` — se F-01.

---

## Del B — Fund

### F-01 · Lokal enheds-identitet matcher ikke CMDB

**Observation:** Login-skærmen på `https://192.168.86.117:8443/` viser
`🔑 QR-kode: edge-MOD-BAGGARD-NXHT`, og hostname er `tl-modbaggardnxht`. CMDB
har korrekt `TL-043EB9E72EFD`.

**Evidens:** Skærmbillede fra Peter (2026-08-04). Root cause: jeg patchede
`/etc/timelapse/bootstrap.yaml`s `device_id`/`expected_device_id` manuelt
tidligere samme dag for at låse enrollment op (se HANDOVER_LOG 10:20-entry),
men nåede aldrig at rette `/etc/timelapse/bt-config.yaml`s `totp.secret`/`sid`
til den nye identitet, fordi Peter blev låst ude før kommandoen kunne køres
(se 22:37-entry).

**Impact:** Forvirrende/misvisende for teknikeren; ingen funktionel skade (BT
PAN-login virker stadig med det gamle secret, som jeg genfandt fra
morgen-backuppen). Den lokale TLS-certifikat blev også udstedt til
`tl-modbaggardnxht.local` ved build-tid (samme rodfejl).

**Confidence:** Høj — bekræftet direkte i skærmbillede + kendt egen handling.

**Foreslået target-state:** Enhedens lokale selv-identifikation matcher CMDB
(`edge-TL-043EB9E72EFD`), inkl. TOTP-sid og lokal TLS-hostname.

**Anbefalet handling:** Når shell-adgang er genoprettet (afhænger af F-08/F-09):
kør den tidligere forberedte kommando til at opdatere `bt-config.yaml`s
`totp.secret`/`sid` til værdierne for `TL-043EB9E72EFD` (allerede i DB), og
overvej at genudstede lokal TLS/hostname til `tl-043eb9e72efd.local`.

**Dependencies:** F-08, F-09 (kræver arbejdende shell).

**Risiko:** Lav — rent lokal konfigurationsfil, ingen CMDB-mutation nødvendig.

**Acceptkriterier:** Login-skærmen viser `edge-TL-043EB9E72EFD`; ingen
funktionstab af lokal BT-adgang under overgangen.

---

### F-02 · `extra_packages` fra hardware-target når aldrig det flashede image

**Observation:** `target.yaml` for orangepi4pro lister `gphoto2,
libgphoto2-6, libgphoto2-port12, gpsd, gpsd-clients, python3-gps, autossh,
bluez, bluez-tools, python3-dbus` som `extra_packages`. Doctor på
`TL-043EB9E72EFD` rapporterer `gphoto2 mangler`.

**Evidens:**
- `headend/tools/hardware/orangepi4pro/target.yaml:38-49` (extra_packages-liste)
- `headend/tools/Dockerfile.edge:30-37` — pakkerne installeres faktisk her,
  men KUN i den midlertidige Docker-rootfs der eksporteres til `rootfs.tar.gz`
- `headend/tools/inject_edge_image.py:481` (kommentar, dokumenteret filter):
  **"Kun /opt/timelapse/, /etc/timelapse/, /etc/systemd/system/timelapse-*
  udpakkes"** fra denne tarball ind på det RIGTIGE base-image
- `headend/tools/inject_edge_image.py:730` og `:951-955` — `EXTRA_PACKAGES`
  sendes som env-var ind i injektionscontaineren, men bruges kun til ét
  betinget tjek (`grep -q gpsd`), aldrig til et faktisk `apt-get install` mod
  det virkelige base-image.

**Impact:** Enhver ny Orange Pi 4 Pro bygget med denne generator mangler
gphoto2 (kamera-styring virker ikke), og efter al sandsynlighed `autossh`
(reverse-tunnel-tjenesten kan ikke starte). `bluez` fremstår tilfældigt OK,
fordi det officielle OrangePi-baseimage allerede leverer Bluetooth-stakken —
ikke fordi vores pipeline installerede den.

**Confidence:** Høj for gphoto2 (direkte Doctor-bekræftet + kode-sporet).
Middel for autossh-konsekvensen (logisk følge af samme mekanisme, men IKKE
selv verificeret ved shell — se F-09-afhængighed).

**Foreslået target-state:** Alle `extra_packages` fra det valgte hardware-
target er faktisk installeret på det endelige flashede image.

**Anbefalet handling:** Chroot ind i det mountede base-image inde i den
allerede-privilegerede injektionscontainer og køre
`apt-get update && apt-get install -y $EXTRA_PACKAGES` der. Kræver
internetadgang under build (allerede tilfældet for base-image-download) og
formentlig `qemu-user-static` for cross-arch chroot, hvis build-maskinen ikke
selv er arm64.

**Dependencies:** Ingen (kan rettes i generatoren uafhængigt af den aktuelle
enheds tilstand — retter kun FREMTIDIGE builds).

**Risiko:** Middel — ændrer selve build-pipelinen; skal testes med et fuldt
build+flash-cyklus før det erklæres løst, ikke kun kode-review.

**Acceptkriterier:** Et nybygget, flashet Orange Pi 4 Pro-image har `gphoto2`
og `autossh` installeret og virkende ved første boot, uden manuel efterinstallation.

**Hvorfor ikke fundet før:** `TL-C87FF9587CA0` blev sat op før denne
automatiserede generator eksisterede (formentlig manuel installation). Dette
er sandsynligvis første gang en helt ny enhed er gået hele vejen generér →
flash → boot → enrollér med DENNE pipeline.

---

### F-03 · Reverse-tunnel-portkollision + to ikke-synkroniserede tunnel-mekanismer

**Observation:** Peters oprindelige fund: "SSH reverse tunnel doesn't come
alive... It should not be possible to select the same port as other devices."

**Evidens (DB, kørt i forbindelse med denne rapport):**
```
device_id       | reverse_tunnel_port | manual_remote_port (device_config.ssh_tunnel)
TL-C87FF9587CA0 | 2201                | (ikke tjekket i denne omgang)
TL-043EB9E72EFD | 2204                | 2202
```
`headend/main.py` (`_ensure_device_provisioning_credentials`, linje ~15182-15190)
auto-allokerer `device.reverse_tunnel_port` kollisionsfrit (starter ved 2201,
tjekker kun mod andre enheders SAMME kolonne). Det MANUELLE
`ssh_tunnel.remote_port`-felt i `timelapse-ui/src/pages/SystemAdminPage.tsx`
(linje ~351, 466-489) er et frit tekstfelt, default hardkodet `'2201'`, uden
noget kollisionstjek og uden kendskab til den auto-allokerede værdi.

**Impact:** To separate, ikke-synkroniserede portkilder for den samme
fysiske SSH-tunnel-mekanisme. `TL-043EB9E72EFD`s manuelle værdi (2202) matcher
ikke dens egen korrekt allokerede værdi (2204) — sandsynlig medvirkende årsag
til at tunnelen ikke kommer op, uafhængigt af F-02s autossh-mangel.

**Confidence:** Høj (direkte DB-verificeret).

**Foreslået target-state:** Én autoritativ portkilde pr. enhed; UI'et kan
aldrig gemme en port der allerede er i brug af en anden enhed, og forslår
automatisk næste ledige.

**Anbefalet handling:** (1) Kortsigtet: lad `SystemAdminPage.tsx`s tunnel-
sektion hente og forudfylde `device.reverse_tunnel_port` i stedet for den
hardkodede `'2201'`, og valider mod alle andre enheders porte (begge kilder)
før gem. (2) Langsigtet: overvej at fjerne den config-drevne
`SshTunnelManager`/`ssh_tunnel`-mekanisme helt og kun bruge den statiske,
allerede-auto-allokerede `autossh`-systemd-enhed — to parallelle
implementeringer af samme funktion er en vedvarende fejlkilde.

**Dependencies:** Ingen for kortsigtet fix.

**Risiko:** Lav for kortsigtet UI-valideringsfix. Høj for den langsigtede
konsolidering (rører driftskritisk tunnel-infrastruktur for eksisterende
enheder som `TL-C87FF9587CA0`) — bør IKKE gøres uden separat godkendelse.

**Acceptkriterier:** UI'et kan ikke gemme en tunnel-port der kolliderer med en
anden enheds port; forslår næste ledige.

---

### F-04 · HAL hardware-detektion manglede a733/sun60i (RETTET i repo i dag)

**Observation:** Enrollment-log viste "HAL: Ukendt hardware ('sun60iw2') —
bruger GenericAdapter" for `TL-043EB9E72EFD`, selvom `OrangePiAdapter` selv
allerede genkender netop denne streng.

**Evidens:** `edge/hal/orangepi.py:22` — `if "a733" in self._raw or
"sun60iw2" in self._raw: return "OrangePi 4 Pro (Allwinner A733, arm64)"`.
Men det overordnede valg-gate i `edge/hal/__init__.py:76-78` havde IKKE
`"a733"`/`"sun60i"` i sin nøgleords-liste, så `OrangePiAdapter` blev aldrig
valgt.

**Impact:** Enheden kørte på en generisk HAL-adapter i stedet for den
Orange-Pi-specifikke — potentielt påvirker GPIO-relæ-styring,
hardware-specifik NPU-detektion m.m.

**Confidence:** Høj — direkte kode-modsigelse fundet og rettet.

**Status:** **RETTET** i `edge/hal/__init__.py` (tilføjet `"a733"`, `"sun60i"`
til nøgleordslisten). **Kun i repoet — IKKE deployeret** til
`TL-043EB9E72EFD` (kræver SSH eller ny build+flash).

**Acceptkriterier:** Enrollment-log/Doctor viser "HAL: OrangePi detekteret",
ikke "Ukendt hardware", på næste kørsel efter deployment.

---

### F-05 · `target.yaml` dokumenterer forkert SoC/NPU for orangepi4pro

**Observation:** Peter korrigerede mig — Orange Pi 4 Pro HAR en NPU
(op til 3 TOPS, INT8/INT16/FP16/BF16). Jeg havde fejlagtigt hævdet den ikke
havde en NPU, baseret alene på `target.yaml`s eget (forkerte) kommentar,
uden at sammenholde mod evidens jeg allerede havde set samme session.

**Evidens (direkte modsigelse i repoet):**
- `headend/tools/hardware/orangepi4pro/target.yaml:2,9,17,76-77`: "SoC:
  Rockchip RK3399", "NPU: ingen", "soc: RK3399"
- `edge/scripts/timelapse-bt-pan.sh:4`: "Board: OrangePi 4 Pro (**Allwinner
  A733**/sun60iw2, AIC8800 BT chip)"
- Enhedens egen `platform.platform()`-output (Doctor, flere gange i dag):
  `Linux-5.15.147-sun60iw2-aarch64` — `sun60iw2` er Allwinners egen
  platform-navngivning, ikke Rockchips.
- `edge/npu_viplite/README.md:3`: "Board-side wrapper for **Allwinner/Orange
  Pi A733** VIPLite `.nb` models" — substantielt, allerede eksisterende
  NPU-integrationsarbejde for netop denne chip (træningspipeline,
  parity-evaluering, probe-værktøj: `edge/tools/probe_orangepi_npu.py`,
  `edge/ai/npu_runtime.py`, `edge/training/train_edge_qa_model.py`).

**Impact:** `target.yaml`s forkerte SoC-dokumentation er sandsynligvis en
copy-paste-fejl fra den ÆLDRE, RK3399-baserede "Orange Pi 4"/"Orange Pi 4
LTS" — mens den faktiske hardware Peter bruger er en nyere,
Allwinner-A733-baseret variant markedsført under samme "Orange Pi 4 Pro"-navn.
Dette er en reel, allerede eksisterende fejl i repoet, ikke noget nyt fra
denne uge.

**Confidence:** Høj for selve modsigelsen (direkte kode-citater). Middel for
at NPU-manglen på `TL-043EB9E72EFD` (Doctor: "NPU runner/model/VIPLite
wrapper mangler") skyldes SAMME rodfejl som F-02 (extra_packages/build-
artefakter når aldrig det flashede image) — logisk sammenhængende, men ikke
selv verificeret ved shell.

**Foreslået target-state:** `target.yaml` dokumenterer korrekt SoC (Allwinner
A733) og NPU-kapacitet. Doctor/NPU-fund omklassificeres fra "kosmetisk støj"
(min tidligere, forkerte vurdering) til reelt, undersøgelsesværdigt gap.

**Anbefalet handling:** (1) Ret `target.yaml`s SoC/NPU-kommentarer og
`notes`-felt. (2) Undersøg om `edge/npu_viplite/`s allerede-byggede
VIPLite-wrapper + model kan/bør bages ind i flashable images via samme
mekanisme som F-02s fix (chroot-baseret installation), eller om det kræver
en separat cmake-kompileringssteg i injektions-pipelinen.

**Dependencies:** Delvist overlap med F-02 (samme klasse rodfejl:
"build-artefakter når ikke det endelige image").

**Risiko:** Lav for dokumentationsrettelsen. Middel-høj for at faktisk bage
NPU-runtime ind (kompileringsafhængigheder, cross-arch build-kompleksitet).

**Acceptkriterier:** `target.yaml` matcher fysisk hardware. Beslutning
truffet (af Peter) om NPU-baking er i scope for næste generator-iteration
eller udskudt.

---

### F-06 · Doctor: "bootstrap token mangler" er falsk positiv for enrollerede enheder

**Observation:** Doctor viser konsekvent "FEJL bootstrap token mangler" på
`TL-043EB9E72EFD`, selvom enheden er succesfuldt enrolleret.

**Evidens:** `edge/scripts/bootstrap_agent.py:263-273` — efter succesfuld
enrollment skrives `/opt/timelapse/edge/bootstrap.yaml` MED BEVIDST
`bootstrap_token: ""` (korrekt sikkerhedspraksis — et engangs-token skal
ikke ligge og flyde efter brug; den rigtige, fortsatte credential er
`api_token.txt`, skrevet separat samme sted). `edge/tools/bootstrap_cli.py:705`
tjekker blot om feltet er sat, uden at tage højde for enrollment-status.

**Impact:** Kosmetisk Doctor-støj for enhver allerede-enrolleret enhed —
ingen reel funktionsfejl.

**Confidence:** Høj (direkte kode-bekræftet på begge sider).

**Foreslået target-state:** Doctor tjekker `.enrolled`-markøren og/eller
`api_token.txt`s tilstedeværelse som det egentlige "har enheden gyldige
credentials"-signal, ikke det (korrekt) tomme bootstrap-token-felt.

**Anbefalet handling:** Rettelse i `bootstrap_cli.py::collect_doctor_evidence`.
Lav risiko, ren kvalitetsforbedring.

**Dependencies:** Ingen.

**Risiko:** Lav.

**Acceptkriterier:** Doctor viser "OK" for credentials på en allerede-
enrolleret enhed uden bootstrap-token, og en klar "FEJL" kun for en enhed der
reelt hverken har token ELLER api_token.txt.

---

### F-07 · Doctor tjekker aldrig `timelapse-ssh-tunnel`-servicen

**Observation:** Under forsøg på at diagnosticere tunnel-problemet via den
ALLEREDE FUNGERENDE "Kør kommando"-kanal (uafhængig af det ødelagte
"Åben Terminal"), var der intet whitelisted CLI-flag der viser
tunnel-service-status.

**Evidens:** `edge/tools/bootstrap_cli.py:37-43` (`EXPECTED_SERVICES`) lister
kun `timelapse-edge, timelapse-bt-pan, timelapse-bt-agent, timelapse-captive,
timelapse-totp` — `timelapse-ssh-tunnel` er IKKE med. `print_service_status()`
(linje 1132) tjekker kun én hardkodet `SERVICE_NAME`-konstant, ikke tunnelen.

**Impact:** Der er i praksis INGEN fjern-diagnostisk synlighed for
reverse-tunnel-tilstanden uden SSH/fysisk konsol — hverken Doctor eller nogen
whitelisted CLI-genvej dækker den.

**Confidence:** Høj (direkte kode-gennemgang).

**Foreslået target-state:** Doctor/Overblik viser tunnel-service-status
(active/failed/inactive) som en selvstændig linje.

**Anbefalet handling:** Tilføj `timelapse-ssh-tunnel` til `EXPECTED_SERVICES`
(eller en separat tunnel-specifik statuslinje, evt. med seneste
autossh-fejlbesked fra journalctl).

**Dependencies:** Ingen.

**Risiko:** Lav.

**Acceptkriterier:** Doctor viser tunnel-service-tilstand uden at kræve SSH.

---

### F-08 · GLIBC-mismatch på `TL-043EB9E72EFD` (system-niveau, IKKE vores kode)

**Observation:** `bootstrap_cli.py --doctor` fejler nu med
`GLIBC_2.36'/GLIBC_2.38' not found (required by libexpat.so.1)`.

**Evidens:** Peters direkte terminaloutput. Ingen egen shell-adgang til at
undersøge videre.

**Impact:** Højeste prioritet — påvirker sandsynligvis ALLE fremtidige
Python-proces-genstarter på enheden, inkl. `timelapse-edge`/`timelapse-totp`,
hvis de crasher. Kørende processer er kun upåvirkede fordi de startede FØR
bruddet.

**Confidence:** Middel — selve symptomet er utvetydigt (systemniveau-
biblioteksversionskonflikt), men ROD-årsagen (OrangePi's rootfs→SSD-
migreringsværktøj) er en velunderbygget hypotese, ikke direkte verificeret.

**Foreslået target-state:** Konsistent, fungerende glibc/systempakke-tilstand.

**Anbefalet handling:** Kræver fysisk/konsol-adgang. Læs `/etc/os-release`,
`dpkg -l | grep -E 'libc6 |libexpat1 '`, evt. `apt list --upgradable`, og
vurder om en `apt --fix-broken install`/pakke-nedgradering er sikker, eller
om en fuld re-flash er den ansvarlige vej.

**Dependencies:** Kræver adgang jeg ikke har (fysisk konsol eller genoprettet
SSH).

**Risiko:** Høj hvis der forsøges rettet uden fuld forståelse af hvordan
migreringsværktøjet efterlod pakke-tilstanden.

**Acceptkriterier:** `bootstrap_cli.py --doctor` og andre Python-værktøjer
kører uden GLIBC-fejl.

---

### F-09 · SSH `Connection refused` på `TL-043EB9E72EFD`

**Observation:** `ssh`/`nc -z` mod port 22 giver `Connection refused`
(ikke timeout, ikke auth-fejl — intet lytter).

**Evidens:** Egne `ssh`/`nc`-forsøg denne session, flere gange, samme resultat.

**Impact:** Blokerer al fjern-diagnostik og -rettelse af denne specifikke
enhed. Blokerer også reverse-tunnel (selv hvis autossh var installeret,
ville et lokalt sshd stadig skulle køre for tunnelen at have noget at
forwarde til).

**Confidence:** Lav-middel på selve rodårsagen — hypotese: samme rodfejl som
F-08 (hvis sshd/dens hjælpeprocesser mangler glibc-symboler). IKKE
verificeret.

**Foreslået target-state:** sshd lytter og accepterer forbindelser med den
eksisterende nøgle-baserede auth (uændret fra tidligere).

**Anbefalet handling:** Fra fysisk/konsol-adgang: `systemctl status ssh`,
`journalctl -u ssh --no-pager | tail -50`.

**Dependencies:** Samme adgangsbegrænsning som F-08.

**Risiko:** Se F-08.

**Acceptkriterier:** `ssh -i ~/.ssh/timelapse_headend_ed25519 orangepi@<ip>`
lykkes igen.

---

### F-10 · `TL-C87FF9587CA0`-parallel ikke verificeret (afgrænset i denne omgang)

**Observation (Peters spørgsmål):** Er de tilføjelser der er lavet i dag
også nødvendige/tilstede på den gamle referenceenhed?

**Evidens:** DB-niveau: `TL-C87FF9587CA0` har allerede `has_own_bt_totp=true`,
`has_own_ssh_key=true`, `reverse_tunnel_port=2201` — sat op af Codex i
PKI-hærdningsarbejdet 2026-08-03 (se HANDOVER_LOG samme dato), UAFHÆNGIGT af
dagens arbejde. `factory_totp_disabled=false`, `shared_ssh_key_disabled=false`
(nye kolonner fra i dag, defaulter korrekt til `false` for eksisterende
enheder — additiv migration, ingen adfærdsændring).

**Ikke verificeret (kræver SSH, som fejlede med "Permission denied" mod
denne enhed tidligere i dag — årsag ikke undersøgt):** Hvilke pakker der
faktisk er installeret i dens venv/OS; om den har samme
GLIBC/`extra_packages`-tilstand eller ej (den blev formentlig sat op manuelt,
uafhængigt af generatoren — se F-02).

**Impact:** Ukendt indtil SSH-adgang til `TL-C87FF9587CA0` er bekræftet.

**Confidence:** Lav — for lidt evidens til en konklusion.

**Foreslået target-state:** Bekræftet parity-status mellem de to enheder.

**Anbefalet handling:** Forsøg SSH til `TL-C87FF9587CA0` igen (evt. med en
anden bruger end `orangepi`, da den er en ældre, muligvis manuelt sat op
enhed) for faktisk at sammenligne installerede pakker.

**Dependencies:** SSH-adgang til `TL-C87FF9587CA0`.

**Risiko:** Lav — kun-læsning, ingen mutation planlagt.

**Acceptkriterier:** Enten bekræftet parity, eller en dokumenteret liste over
faktiske forskelle.

---

### F-11 · `device.customer_name`/`site_name` tomme på `TL-043EB9E72EFD` trods korrekt FK

**Observation:** De denormaliserede tekstfelter er tomme, selvom
`customer_id`/`site_id` korrekt peger på Hyldager Fotografilm/Vardevej 26c.

**Evidens:** Direkte DB-forespørgsel, Del A ovenfor. Sandsynlig årsag:
`zero_touch_enroll`-flowet (bootstrap-enrollment) sætter kun FK'erne, ikke de
denormaliserede tekstfelter, i modsætning til `prepare_edge_provisioning`
("Klargør ny Edge"), som sætter begge.

**Impact:** Kosmetisk — steder i UI'et der læser de RÅ tekstfelter direkte
(i stedet for at slå FK'en op) kan vise tom kunde/site for denne enhed. Ikke
bekræftet at noget faktisk gør dette (Dashboard bruger `site_id`-match
primært, med tekstfelter kun som fallback).

**Confidence:** Middel — årsagshypotese ikke selv kode-verificeret i denne
omgang.

**Foreslået target-state:** Enrollment-flowet udfylder samme felter som
manuel provisionering.

**Anbefalet handling:** Lavt-prioriteret opfølgning — udfyld
`customer_name`/`site_name` i enrollment-handleren (`/api/devices/enroll`)
fra den tilknyttede Camera/Site, ligesom `prepare_edge_provisioning` gør.

**Dependencies:** Ingen.

**Risiko:** Lav.

**Acceptkriterier:** Nye enrollerede enheder har udfyldte tekstfelter,
matchende deres FK'er.

---

## Del C — Allerede rettet i dag (recap, lavere detaljeringsgrad — se HANDOVER_LOG for fuld evidens)

Case-sensitivity `device_id`-normalisering · `/var/log.hdd`-mount-race (3
systemd-enheder) · migrations-transaktions-forgiftning (8 steder i
`main.py`) · manglende `fastapi`/`uvicorn`/`pyotp`/`python-multipart` i
`edge/requirements.txt` · "Åben Terminal"-JS-escaping-bug (repo-rettet, IKKE
deployeret til `TL-043EB9E72EFD`) · fabriks-TOTP delt fallback →
per-enheds-toggle · delt fleet-wide SSH-masternøgle → per-enheds-nøgle +
togglebar nødadgang + backfill-endpoint · HAL a733/sun60i-detektion (F-04,
denne rapport).

## Del D — Prioriteret rækkefølge (uændret fra tidligere, bekræftet stadig gyldig)

1. **F-08 + F-09** (fysisk/konsol-adgang) — blokerer alt andet på denne
   specifikke enhed.
2. **F-02** (extra_packages-pipeline) — størst arkitektonisk værdi, retter
   ALLE fremtidige builds, ikke kun denne enhed.
3. **F-03** (tunnel-port-UI-validering).
4. **F-01** (lokal identitets-oprydning) — kan vente til efter F-08/F-09.
5. **F-05** (target.yaml-dokumentation) — lav risiko, kan gøres når som helst.
6. **F-06, F-07** (Doctor-forbedringer) — lav risiko, ren kvalitet.
7. **F-10, F-11** — opfølgning, ikke blokerende.

---

## Del E — Tillæg: ny evidens fra `ssh -p 2201 orangepi@localhost` (Peters forslag)

Peter foreslog at teste den etablerede reverse-tunnel direkte fra Headend-
maskinen. Dette lykkedes og gav FAKTISK evidens (ikke antagelser) om
`TL-C87FF9587CA0`, som reviderer flere fund ovenfor.

### E-1 · Autentificering, ikke autossh, er den faktiske låste variabel

`ssh -p 2201 orangepi@localhost` lykkedes UDEN eksplicit `-i`-flag — autentificerede
med Peters personlige `~/.ssh/id_ed25519` (dateret 27. april, FØR
Headend-operatørnøglen `timelapse_headend_ed25519` eksisterede, dateret 15.
juni). Dette bekræfter: `TL-C87FF9587CA0` blev sat op manuelt af Peter, helt
uden om denne generator-pipeline.

### E-2 · `autossh` er IKKE den faktiske tunnel-mekanisme i produktion — reviderer F-02/F-03

Direkte kommandokørsel på `TL-C87FF9587CA0` via den virkende tunnel:
```
os-release:      Ubuntu 24.04.4 LTS (Noble) — IKKE Ubuntu 22.04 Jammy, som target.yaml/generatoren downloader
gphoto2:         /usr/bin/gphoto2 (til stede)
autossh:         "not found" (IKKE installeret — heller ikke her!)
gpsd:            /usr/sbin/gpsd (til stede)
bluetoothctl:    /usr/bin/bluetoothctl (til stede)
device-tree model: sun60iw2 (samme som TL-043EB9E72EFD)
venv-pakker:     fastapi 0.137.2, uvicorn 0.49.0, PyOTP 2.10.0, python-multipart 0.0.32, paramiko 4.0.0 (alle nyere end mine pins i dag)
glibc:           2.39 (Ubuntu 24.04 Noble)
systemctl is-active timelapse-edge / timelapse-ssh-tunnel / timelapse-totp:
                 active / INACTIVE / active
```

**Revision af F-02:** `autossh` er bekræftet FRAVÆRENDE på BÅDE enheder — men
`TL-C87FF9587CA0`s tunnel virker alligevel (jeg forbandt mig netop igennem
den). Den statiske `timelapse-ssh-tunnel.service` (autossh-baseret) er
`inactive` på den velfungerende referenceenhed. **Konklusion: den faktiske,
virkende tunnel-mekanisme er den config-drevne, paramiko-baserede
`SshTunnelManager` (`edge/tunnel/ssh_manager.py`), kørende INDE I
`timelapse-edge`-processen — ikke den statiske autossh-systemd-enhed.**
Autossh-manglen er derfor IKKE forklaringen på `TL-043EB9E72EFD`s
tunnel-problem, som jeg tidligere antog i F-02. Den statiske
`timelapse-ssh-tunnel.service`/autossh-vejen fremstår som forældet/ubrugt
kode, ikke en aktiv fejlkilde.

**Revision af F-03:** Testede direkte begge kandidat-porte for
`TL-043EB9E72EFD`:
- **Port 2202** (dens MANUELLE `ssh_tunnel.remote_port`): en ægte SSH-server
  svarer (host key-advarsel — correctly cleared og retestet), men afviser
  BÅDE Headend-operatørnøglen OG Peters personlige nøgle med "Permission
  denied (publickey)".
- **Port 2204** (dens KORREKT auto-allokerede `reverse_tunnel_port`): "Connection
  refused" — intet lytter overhovedet.

**Ny konklusion:** Tunnelen er IKKE simpelt "død" — noget (højst sandsynligt
`TL-043EB9E72EFD` selv, via den config-drevne manager, ved brug af dens
manuelt satte port 2202) HAR etableret en reverse-tunnel-session på
transportlaget. Men autentificering igennem den fejler nu med nøgler der
tidligere virkede direkte på enheden — **samme mønster som F-08/F-09**
(sshd/nøgle-tilstand ser ud til at være nulstillet eller ændret efter
SSD-migreringen). Dette styrker hypotesen i F-08/F-09 om at glibc- og
SSH-bruddet har en fælles rodårsag i selve migreringen, og at det
sandsynligvis OGSÅ har ramt/nulstillet enhedens `authorized_keys`-tilstand —
ikke kun blokeret port 22 direkte.

### E-3 · `TL-C87FF9587CA0` har samme (harmløse) HAL-detektionsbug — F-04 opgraderet til Høj confidence

Device-tree model er bekræftet "sun60iw2" på DENNE enhed også — samme streng
som `TL-043EB9E72EFD`. F-04s rettelse i `edge/hal/__init__.py` er derfor
relevant for begge enheder, ikke kun den nye. Ikke deployeret til nogen af
dem endnu.

### E-4 · Generatoren downloader en anden OS-version end den eneste reelt validerede

`target.yaml` peger på "Orangepi4pro...ubuntu_jammy_server..." (22.04).
Den ENESTE enhed der reelt har kørt stabilt i produktion i månedsvis
(`TL-C87FF9587CA0`) kører Ubuntu 24.04 (Noble) — en helt anden base. Dette
betyder at `extra_packages`-listen, `apt`-pakkenavne og generelt
OS-kompatibilitet i generatoren ALDRIG er blevet valideret mod den
OS-version generatoren faktisk downloader og flasher. Dette er et selvstændigt,
ikke tidligere dokumenteret risikopunkt.

### Reviderede prioriteter

- **F-02** nedgraderes fra "sandsynlig tunnel-fejl-årsag" til "bekræftet
  manglende pakke, men IKKE årsag til tunnel-problemet". Stadig relevant for
  gphoto2/kamera-styring.
- **F-03** opgraderes: portmismatch er reelt, men er nu tæt kædet sammen med
  F-08/F-09 (samme formodede rodårsag: migrationen har formentlig nulstillet
  autentificerings-/nøgletilstand på enheden, ikke kun portvalget).
- **Ny opfølgning (E-4):** afklar om generatoren bør opdateres til at bruge
  et Ubuntu 24.04 Noble-baseimage i stedet for 22.04 Jammy, givet at det er
  den eneste reelt fältvalideret variant — eller om `TL-C87FF9587CA0` selv
  bør opgraderes/genflashes for at matche generatorens nuværende output.
  Dette er en produktbeslutning, ikke en ren kodefejl — **➡️ Peter**.
