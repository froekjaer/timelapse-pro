# OS-baseline for Edge-enheder — analyse og anbefaling

**Dato:** 2026-09-11
**Forfatter:** Kimi (AI-assistent)
**Anledning:** Peter: "Vi skal have samme versionsnummer på alle enheder. Jeg vil også gerne have samme OS på alle enheder. Jeg vil virkelig gerne have at vi finder ud af hvilke OS der er det sikreste at gå med. Vores ISO builder SKAL sikre at alt er med, og alt er opdateret."
**Status:** Anbefaling til beslutning — ikke implementeret endnu.

---

## 1. Målt virkelighed lige nu (verificeret via SSH 2026-09-11)

| | TL-043EB9E72EFD (.144) | TL-C87FF9587CA0 (.134) |
|---|---|---|
| OS | Ubuntu **22.04.5** LTS (Jammy) | Ubuntu **24.04.4** LTS (Noble) |
| Kernel | 5.15.147-sun60iw2 (vendor BSP) | 5.15.147-sun60iw2 (vendor BSP) — **identisk** |
| Python | 3.10.12 | 3.12.3 |
| numpy | 2.2.6 | **2.5.3** |
| cryptography | 50.0.0 | 50.0.1 |
| uvicorn | 0.46.0 (+extras) | 0.52.4 (uden extras) |
| qrcode | 8.2 | **MANGLER** → tekniker-QR-login er reelt i stykker på denne enhed |
| python-dotenv | 1.2.2 | **MANGLER** |
| onnxruntime/flatbuffers/protobuf/OPi.GPIO | mangler | installeret (NPU-spor) |

**Konklusion på målingen:** Enhederne er allerede divergeret — både i OS, Python og pakkesæt. `qrcode`-manglen på .134 er et konkret funktionstab, opstået fordi miljøet ikke er reproducerbart. Det er præcis det problem F-011 advarede om.

## 2. Den ufravigelige begrænsning: vendor BSP-kernel

- NPU'en (VIPLite) og kamera/ISP-pipelinen kræver Allwinners vendor BSP-kernel (`linux5.15-sun60iw2`). Mainline-kernel har **ingen** NPU- eller kamera-support (jf. Armbian-overlayets dokumenterede begrænsninger, 2026-08).
- Begge enheder kører allerede **samme** BSP-kernel (5.15.147) — også den Noble-opgraderede .134. Det beviser at Noble-userland fungerer i produktion oven på BSP-kernen.
- **Sikkerhedsmæssigt er kernen det svageste led uanset valg:** en vendor BSP-kernel følger ikke Canonicals CVE-backports. Det kan ingen userland-pakke ændre. Mitigation: netværkssegmentering, fail2ban, få åbne porte, signerede opdateringer — og genbesøg af kernelsporet når OrangePi/Allwinner udgiver nyere BSP.

Derfor handler OS-valget reelt om **userland**: Jammy (22.04) eller Noble (24.04).

## 3. Sammenligning: Jammy vs. Noble userland

| | Ubuntu 22.04 Jammy | Ubuntu 24.04 Noble |
|---|---|---|
| Standard sikkerhedsvedligehold | til **~april 2027** | til **juni 2029** |
| Ubuntu Pro ESM (gratis ≤5 maskiner) | til 2032 | til 2034 (+ legacy 2036) |
| Python | 3.10 | 3.12 (hurtigere, længere upstream-support) |
| OpenSSL / OpenSSH | 3.0.2 / 8.9 | 3.0.13 / 9.6 (flere hardening-defaults) |
| Officielt OrangePi-image m. BSP-kernel | ✅ Ja (1.0.6, sha256-pinnet i `target.yaml`) | ❌ Nej — kun via `do-release-upgrade` eller community-byg |
| Produktionserforing hos jer | Standard siden start | ✅ .134 kører det allerede stabilt |
| Reproducerbarhed i ISO-builder i dag | ✅ Direkte | ⚠️ Kræver upgrade-trin i bygget |

**Anbefaling: Ubuntu 24.04 Noble som fælles baseline** — fordi:
1. **2+ år længere standard-support** (2029 vs 2027) — afgørende for enheder der skal leve længe uplanlagt.
2. Nyere krypto-stack og Python 3.12 med længere upstream levetid.
3. **Allerede bevist i jeres produktion** på .134 med den påkrævede BSP-kernel — risikoen er målt, ikke gættet.
4. Én fælles Python-version (3.12) gør F-011-pinning mulig med ÉT fælles requirements-sæt (numpy 2.5.x kræver Python ≥3.11 — kan ikke pinnés ens på Jammy).

**Alternativet** (bliv på Jammy til 2027 og genovervej) er forsvarligt men kortere sigtet, og det fastholder Python 3.10-splittelsen.

## 4. ISO-builder: status mod Peters krav ("alt med, alt opdateret")

Gennemgang af `Dockerfile.edge` + `build_edge_disk_image.py` + `inject_edge_image.py`:

| Krav | Status i dag | Fund |
|---|---|---|
| Alt er med | ❌ | `opencv-python-headless` installeres **post-flash manuelt** (kommentar i `requirements.edge-base.txt`) — uden for den reproducerbare vej. NPU-pakkerne (onnxruntime m.fl.) ligeledes. Resultat: .134 og .144 er divergeret, `qrcode` forsvundet på .134. |
| Alt er opdateret (OS-lag) | ❌ | `inject_edge_image.py` kører **aldrig** `apt-get update/upgrade` på base-imaget. Nye enheder shippes med OrangePi 1.0.6-imagets pakker fra dets byggedato — kendte CVE'er følger med ud. |
| Alt er opdateret (Python-lag) | ⚠️ | Venv bygges i Docker med `apt-get update` (friske systempakker i payload-laget), men med **upinnede** `>=`-requirements → to byg på forskellige dage giver forskellige enheder. |
| Reproducerbarhed | ⚠️ | Base-Docker-tag `arm64v8/ubuntu:22.04` er ikke digest-pinnet. Base-OS-imaget ER sha256-pinnet (godt). SBOM (apt+pip) genereres ved byg (godt fundament). Git-provenance-tvang (godt). |

### Konkret forbedringsplan for builderen (efter OS-beslutning)

1. **Pin `edge/requirements.txt`** til verificerede versioner (`==`) fra den valgte baseline — én fælles fil, samme versioner på alle enheder.
2. **Flyt `opencv-python-headless` (+ NPU-pakker efter behov) ind i Docker-bygget**, så intet installeres manuelt post-flash.
3. **Tilføj OS-opdateringstrin i `inject_edge_image.py`:** chroot `apt-get update && apt-get -y upgrade` (+ `unattended-upgrades`-konfiguration) på det mountede image før udpakning af payload — så nye images altid er patched på byggedagen.
4. **Digest-pin base-Docker-imaget** (`arm64v8/ubuntu:24.04@sha256:…`) efter OS-skift.
5. **Noble-baseline i builderen:** enten (a) `do-release-upgrade` i chroot under byg (tungt men reproducerbart), eller (b) genbyg når OrangePi udgiver officielt Noble-image — besluttes med OS-valget.
6. **Verifikationstrin:** byg fejler hvis SBOM-diff mod forrige byg indeholder uventede ændringer (ratchet mod utilsigtet drift).

## 5. Foreslået eksekveringsrækkefølge

1. **Beslutning (Peter):** Noble som fælles baseline? (min anbefaling: ja)
2. Akut funktionsfix: geninstallér `qrcode==8.2` + `python-dotenv` på .134 (genopretter tekniker-QR-login) — kan gøres på 2 minutter.
3. F-011: pin requirements mod Noble-baselinen (.134's faktiske versioner som udgangspunkt, efter gennemgang).
4. Builder-forbedringer (pkt 4 ovenfor) i én eller to PR'er.
5. Konvergens af .144: `do-release-upgrade` til Noble (bevist vej) eller reflash med nyt Noble-image når builderen kan producere det.
6. GRC: luk `FIND-TL-C87FF9587CA0-UBUNTU-NOBLE-UNDOCUMENTED-OS-UPGRADE` som "bevidst — nu dokumenteret baseline", opret kontrol for OS-baseline-drift-detektion.

## 6. Risici ved anbefalingen

- `do-release-upgrade` på .144 er en irreversibel operation på en produktionsenhed — kræver fuld backup af captures først (projektreglen: captures slettes aldrig) og fysisk adgang som fallback.
- NPU-sporet (onnxruntime m.fl. på .134) er installeret udenfor git — dets oprindelse og nødvendighed bør dokumenteres som del af punkt 3, så det kommer under den reproducerbare byggevej.
- BSP-kernens CVE-exposition ændres ikke af dette valg — noteret som separat, accepteret spor (punkt 2).

---

**Afventer Peters beslutning på punkt 5.1 før implementering.**
