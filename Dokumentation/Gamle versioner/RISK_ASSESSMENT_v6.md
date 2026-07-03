# TimeLapse Pro — SABSA Risikovurdering v6

**Version:** 6.0  
**Dato:** 6. maj 2026  
**Forfatter:** Peter Frøkjær / TimeLapse Pro  
**Status:** Gældende  
**Afløser:** Risk Assessment v5

---

## 1. Formål og scope

Denne risikovurdering dækker TimeLapse Pro's samlede system:

- **Edge-lag:** Orange Pi 4 Pro enheder på byggepladser og sites med Canon DSLR-kameraer
- **Headend-lag:** Mac Mini (primær) med FastAPI, SQLite og SFTP-server
- **Transport-lag:** SFTP (billeder), HTTPS/JWT (API), SSH (tunnel + vedligehold)
- **Præsentations-lag:** React/TypeScript UI (Windows/Mac/browser)
- **Sprint C features:** RBAC, Camera/Pi-kobling, Reverse SSH tunnel, Opdateringsstyring, intern PKI, SFTP chroot-isolation

---

## 2. SABSA Business Attributes Profile

SABSA-attributterne mappes til TimeLapse Pros forretningsbehov:

| # | Attribut | Forretningsbetydning | Relevante kontroller |
|---|----------|---------------------|---------------------|
| 1 | **Availability** | Billeder skal tages og uploades uden afbrydelse, uanset netværksstatus | Store-and-forward, circular buffer, nightly reboot, heartbeat monitoring |
| 2 | **Integrity** | Hvert billede er bevismateriale — manipulation må ikke forekomme | SHA-256 pr. billede, XMP-signering, sidecar JSON, WAL SQLite |
| 3 | **Confidentiality** | Kundedata må ikke tilgås af uvedkommende — hverken andre kunder eller tredjepart | SFTP chroot, RBAC, JWT, intern CA, data-klassifikation |
| 4 | **Accountability** | Al adgang og alle handlinger skal kunne spores | SSH tunnel audit log, RBAC login log, capture audit trail, Event tabel |
| 5 | **Authenticity** | Edge-enheder og brugere skal bevise identitet | Bootstrap token, JWT, SSH Ed25519-nøgler, intern CA client-certs |
| 6 | **Manageability** | Systemet skal kunne administreres centralt uden fysisk adgang til sites | Reverse SSH tunnel, config hierarki, opdateringsstyring, UI |
| 7 | **Continuity** | Systemet skal overleve strømafbrydelse, netværkstab og hardwarefejl | Cold-start cache, Camera/Pi-kobling (historik bevares ved hardwareudskiftning), nightly reboot |
| 8 | **Extensibility** | Nye sites, kameraer og kunder tilføjes uden ændring af kodebasen | Multi-tenant hierarki (global→customer→site→device), driver abstraction |
| 9 | **Privacy** | Kundedata holdes adskilt — en kunde må aldrig se en andens data | SFTP chroot, RBAC customer_id scope, separate DB-rækker |
| 10 | **Auditability** | Compliance-dokumentation skal kunne genereres | Security report generator, MFA-dokumentationsfelter, chroot-verificeringslog |
| 11 | **Resilience** | Systemet skal detektere og genopstå fra fejl automatisk | Rollback ved fejlet opdatering, relay force-off, quality check med fallback |

---

## 3. Risikoappetit

Fire niveauer anvendes konsistent gennem hele risk registeret:

| Niveau | Label | Beskrivelse | Eksempel |
|--------|-------|-------------|---------|
| 1 | **Accepterer** | Risikoen accepteres uden yderligere kontrol | Mindre image-kvalitetsfejl |
| 2 | **Tolererer** | Risikoen tolereres med eksisterende kontroller | Midlertidig netværkstab |
| 3 | **Behandler** | Yderligere kontroller implementeres | Uautoriseret SFTP-adgang |
| 4 | **Eliminerer** | Risikoen elimineres — zero tolerance | Kundedata-lækage, rootkit på edge |

---

## 4. 5×5 Risikovurderingsmatrix

```
Sandsynlighed
    5 │  5  10  15  20  25
    4 │  4   8  12  16  20
    3 │  3   6   9  12  15
    2 │  2   4   6   8  10
    1 │  1   2   3   4   5
      └────────────────────
        1   2   3   4   5  → Konsekvens
```

| Score | Niveau | Farve |
|-------|--------|-------|
| 1–4   | Lav    | 🟢 |
| 5–9   | Medium | 🟡 |
| 10–15 | Høj    | 🟠 |
| 16–25 | Kritisk| 🔴 |

---

## 5. Risikoregister

### R01 — Uautoriseret adgang til billeddata via SFTP

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Confidentiality, Privacy |
| Trussel | SFTP-credentials lækker; angriber tilgår andre kunders data |
| Sandsynlighed | 2 (lav — key-baseret auth, per-site bruger) |
| Konsekvens | 5 (kritisk — brud på kundefortrolighed, GDPR) |
| **Risikoscore** | **🟠 10** |
| Risikoappetit | Behandler |
| Eksisterende kontroller | Per-site SFTP-bruger, hierarkisk mappestruktur |
| **Nye kontroller (Sprint C)** | SFTP chroot-isolation (ChrootDirectory), `internal-sftp`, chroot-verificeringslog i DB |
| Residualrisiko efter kontrol | 🟢 4 (2×2 — chroot eliminerer lateral bevægelse) |

---

### R02 — Uautoriseret adgang til admin-UI

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Confidentiality, Authenticity |
| Trussel | Svage credentials eller manglende adgangskontrol giver adgang til alle kunders data |
| Sandsynlighed | 3 (medium — ingen RBAC hidtil) |
| Konsekvens | 5 (kritisk — fuld systemadgang) |
| **Risikoscore** | **🔴 15** |
| Risikoappetit | Behandler → Eliminerer |
| **Nye kontroller (Sprint C)** | RBAC med 4 roller, JWT med 12t udløb, `require_role()` på alle endpoints, password bcrypt-hashing, standard super_admin skal skifte password ved opstart |
| Residualrisiko efter kontrol | 🟡 6 (2×3 — RBAC reducerer drastisk; MFA ville reducere yderligere til 🟢 4) |
| **Åbent punkt** | MFA til UI-login mangler stadig implementering |

---

### R03 — Tab af billedhistorik ved hardwarefejl på Orange Pi

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Continuity, Integrity |
| Trussel | Orange Pi fejler; ny Pi registrerer nyt device_id; historik mistes |
| Sandsynlighed | 3 (medium — hardware fejler over tid) |
| Konsekvens | 3 (medium — tab af dokumentationsevne) |
| **Risikoscore** | **🟡 9** |
| Risikoappetit | Behandler |
| **Nye kontroller (Sprint C)** | Camera/Pi-kobling: logisk kamera (Camera-tabel) adskilt fra fysisk hardware (Device-tabel); DeviceAssignment-historik bevares; captures knyttet til camera_id |
| Residualrisiko efter kontrol | 🟢 3 (1×3 — hardwareudskiftning er nu en simpel reassignment) |

---

### R04 — Ingen remote adgang ved netværks- eller konfigurationsfejl på site

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Manageability, Availability |
| Trussel | Edge-node er fejlkonfigureret eller API utilgængeligt; fysisk besøg nødvendigt |
| Sandsynlighed | 3 (medium — særligt ved nye installationer) |
| Konsekvens | 3 (medium — driftsomkostning, forsinkelse) |
| **Risikoscore** | **🟡 9** |
| Risikoappetit | Behandler |
| **Nye kontroller (Sprint C)** | Reverse SSH tunnel: auto-start ved API-tab, primary + fallback endpoint, audit-log, deny-flag pr. customer/site |
| Residualrisiko efter kontrol | 🟢 3 (1×3 — tunnel giver remote adgang selv uden API) |

---

### R05 — Kompromitteret edge-enhed (fysisk adgang)

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Confidentiality, Integrity, Authenticity |
| Trussel | Fysisk adgang til Orange Pi; angriber læser SFTP-credentials og JWT fra disk |
| Sandsynlighed | 2 (lav — sites er typisk beskyttede) |
| Konsekvens | 4 (høj — credentials kan bruges til at tilgå headend) |
| **Risikoscore** | **🟠 8** |
| Risikoappetit | Behandler |
| Eksisterende kontroller | SFTP-password i config (ikke i kode), API JWT med udløb |
| **Planlagte kontroller** | Intern CA + client-certs (mTLS): kompromitteret cert kan revokeres; SSH-nøgler med passphrase; disk-kryptering (overlayFS eller LUKS) |
| Residualrisiko efter kontrol | 🟡 6 (2×3) |

---

### R06 — Ondsindet eller fejlet opdatering ruller ud til alle sites

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Availability, Integrity, Continuity |
| Trussel | Buggy opdatering deployes til alle devices simultaneously |
| Sandsynlighed | 2 (lav — CI/CD tests eksisterer) |
| Konsekvens | 5 (kritisk — alle sites mister captures) |
| **Risikoscore** | **🟠 10** |
| Risikoappetit | Behandler |
| **Nye kontroller (Sprint C)** | Update policy pr. device (auto/manual), staged rollout (global→customer→site→device), automatisk rollback ved heartbeat-fejl, maintenance window |
| Residualrisiko efter kontrol | 🟢 4 (2×2 — rollback + manuel godkendelse for app_updates) |

---

### R07 — SFTP-certifikat eller SSH-nøgle kompromitteret

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Authenticity, Confidentiality |
| Trussel | SSH-nøgle eller SFTP-credentials stjæles; langsigtet uautoriseret adgang |
| Sandsynlighed | 2 |
| Konsekvens | 4 |
| **Risikoscore** | **🟠 8** |
| Risikoappetit | Behandler |
| **Nye kontroller (Sprint C/D)** | Intern CA: kompromitteret cert udløber, ingen fornyelse = effektiv revokering; Key Management UI: ét sted at se og tilbagekalde alle nøgler; SSH CA på headend: sign edge-nøgler, revokér ved at fjerne CA-trust |
| Residualrisiko efter kontrol | 🟢 4 (2×2) |

---

### R08 — Man-in-the-middle på API-kommunikation

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Confidentiality, Integrity, Authenticity |
| Trussel | Angriber intercepts HTTPS-kommunikation og stjæler JWT |
| Sandsynlighed | 2 (lav — lukket netværk, edge initierer forbindelser) |
| Konsekvens | 3 (medium — session-hijacking begrænset af JWT-udløb) |
| **Risikoscore** | **🟡 6** |
| Risikoappetit | Tolererer med kontrol |
| Eksisterende kontroller | HTTPS, JWT 12t udløb, StrictHostKeyChecking |
| **Planlagte kontroller** | CA-pinning i edge (stoler kun på headend CA-cert), mTLS (edge præsenterer client-cert), cert-fingerprint i bootstrap.yaml |
| Residualrisiko efter kontrol | 🟢 2 (1×2) |

---

### R09 — Dataredundans og backup

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Availability, Continuity |
| Trussel | Headend-disk fejler; alle billeder mistes |
| Sandsynlighed | 2 |
| Konsekvens | 4 |
| **Risikoscore** | **🟠 8** |
| Risikoappetit | Behandler |
| Eksisterende kontroller | Backup-funktion til NAS, edge circular buffer (50 GB lokal buffer) |
| **Åbne punkter** | Automatisk off-site backup ikke implementeret; backup-test-procedure mangler |
| Residualrisiko efter kontrol | 🟡 6 (2×3) |

---

### R10 — SSH tunnel misbrug (uautoriseret adgang via tunnel)

| Felt | Værdi |
|------|-------|
| SABSA-attribut | Accountability, Confidentiality |
| Trussel | SSH tunnel bruges til uautoriseret adgang til edge-enhed |
| Sandsynlighed | 1 (lav — kræver adgang til headend + tunnel) |
| Konsekvens | 3 (medium — adgang til edge-enhed) |
| **Risikoscore** | **🟢 3** |
| Risikoappetit | Accepterer med audit |
| **Nye kontroller (Sprint C)** | `deny`-flag pr. customer/site/device, fuld audit-log (SshTunnelLog), tunnel kun aktiv ved behov, restricted shell på tunnel-bruger |
| Residualrisiko efter kontrol | 🟢 2 (1×2) |

---

## 6. PKI og nøgleinfrastruktur (ny i v6)

### 6.1 Intern CA-arkitektur

```
TimeLapse Root CA  (Mac Mini — offline privat nøgle)
  ├── Headend Server Cert  (HTTPS API — fornyes årligt)
  ├── Device Client Certs  (pr. Orange Pi — fornyes halvårligt)
  └── SFTP SSH CA          (underskriver device SSH-nøgler)
```

### 6.2 Certifikat-levetider

| Type | Levetid | Fornyelse |
|------|---------|-----------|
| Root CA | 10 år | Manuel |
| Headend server cert | 1 år | Halvautomatisk (Key Mgmt UI) |
| Device client cert | 6 måneder | Automatisk ved bootstrap |
| SFTP SSH user key | Ubegrænset | Revokering ved kompromittering |
| SSH tunnel key | Ubegrænset | Revokering via Key Mgmt UI |
| JWT access token | 12 timer | Automatisk ved login |

### 6.3 Vurdering: Self-signed vs. intern CA

**Self-signed individuelle certifikater frarådes** — hvert device kræver manuel trust-konfiguration ved udskiftning.

**Intern mini-CA anbefales** fordi:
- Rotation: ny headend-cert signeres af CA → edges opdateres automatisk ved næste config-pull
- Revokering: nyt device kan ikke få cert uden CA-signering
- Skalering: O(1) kompleksitet uanset antal devices
- Implementation: ~50 linjer `cryptography`-bibliotek (allerede i venv)

---

## 7. Key Management UI — funktionskrav

Ny side i TimeLapse UI: **Nøglehåndtering** (kun `super_admin`):

### 7.1 Sektioner

**CA & Certifikater**
- Vis CA cert fingerprint og udløbsdato
- Download CA cert (til import i browser/OS)
- Udsted nyt headend server cert
- List alle aktive device client certs med udløb

**SSH-nøgler (SFTP)**
- List alle sftp_* brugere og deres nøgler
- Generer ny SSH-nøgle pr. site (knap)
- Kopier public key til clipboard
- Marker nøgle som revokeret (fjerner fra authorized_keys)

**SSH-nøgler (Tunnel)**
- List alle device tunnel-nøgler
- Generer nøglepar til ny enhed
- Download provisionerings-pakke (bootstrap.yaml + nøgle + CA cert)
- Marker nøgle som revokeret

**Bootstrap tokens**
- Generer éngangsbrug bootstrap-token til ny enhed
- List aktive tokens med udløb (24 timer)
- Invalider token manuelt

**Provisionerings-pakke**
- Vælg: kunde → site → kamera
- Klik "Generer pakke" → downloader `timelapse_provision_<site>.zip`:
  ```
  timelapse_provision_nvj17c.zip
    bootstrap.yaml          ← device_id, headend_url, bootstrap_token
    headend_ca.crt          ← CA cert til pinning
    tunnel_key              ← SSH privat nøgle (tunnel)
    tunnel_key.pub          ← SSH public nøgle
    INSTALL.md              ← trin-for-trin installationsguide
  ```

---

## 8. Samlet risikooverblik

| Risk | Nuværende score | Score efter Sprint C | Trend |
|------|----------------|---------------------|-------|
| R01 — SFTP data-adskillelse | 🟠 10 | 🟢 4 | ↓↓ |
| R02 — UI adgangskontrol | 🔴 15 | 🟡 6 | ↓↓↓ |
| R03 — Hardware-historik | 🟡 9 | 🟢 3 | ↓↓ |
| R04 — Remote adgang | 🟡 9 | 🟢 3 | ↓↓ |
| R05 — Kompromitteret edge | 🟠 8 | 🟡 6 | ↓ |
| R06 — Opdateringsfejl | 🟠 10 | 🟢 4 | ↓↓ |
| R07 — Nøgle-kompromittering | 🟠 8 | 🟢 4 | ↓↓ |
| R08 — Man-in-the-middle | 🟡 6 | 🟢 2 | ↓↓ |
| R09 — Backup | 🟠 8 | 🟡 6 | ↓ |
| R10 — SSH tunnel misbrug | 🟢 3 | 🟢 2 | ↓ |

**Samlet risikoprofil:** Fra 3 kritiske/høje risici til 0 kritiske og 2 høje efter Sprint C.

---

## 9. Åbne punkter og næste skridt

| Prioritet | Punkt | Sprint |
|-----------|-------|--------|
| 🔴 Høj | MFA til admin-UI login | C/D |
| 🟠 Medium | Intern CA implementering + Key Management UI | D |
| 🟠 Medium | Automatisk off-site backup | D |
| 🟠 Medium | Disk-kryptering på edge (overlayFS/LUKS) | D |
| 🟡 Lav | Backup-testprocedure dokumenteret | D |
| 🟡 Lav | mTLS (edge client-cert ved API-kald) | E |

---

## 10. Dokumenthistorik

| Version | Dato | Ændringer |
|---------|------|-----------|
| 1.0 | apr 2026 | Initial assessment |
| 2.0 | apr 2026 | Sprint A controls tilføjet |
| 3.0 | apr 2026 | SFTP og config hierarki |
| 4.0 | apr 2026 | LAB mode og diagnostics |
| 5.0 | apr 2026 | Multi-tenant, customer isolation |
| **6.0** | **maj 2026** | **Sprint C: RBAC, SSH tunnel, Camera/Pi-kobling, opdateringsstyring, intern PKI, SFTP chroot** |

---

*Næste review: ved Sprint D eller ved væsentlige arkitekturændringer*
