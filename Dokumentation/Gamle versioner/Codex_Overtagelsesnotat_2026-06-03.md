# TimeLapse Pro - Codex overtagelsesnotat

**Dato:** 2026-06-03  
**Rolle:** SABSA/Senior arkitektur/Senior programmering  
**Formål:** Fast arbejdsanker for videre arbejde efter overtagelse fra Claude og den stalled Codex-samtale.

## Kildehierarki

1. **Nyeste gældende krav/sikkerhed**
   - `Kopi af TimeLapse_Pro_Samlet_Kravspecifikation_v1.0.gdoc`
   - `Kopi af TimeLapse_Pro_Sikkerhedsanalyse_v5.gdoc`
   - `2026-06-03-Timelapse - Risk og plan videre.md`
2. **GRC/update/provisioning**
   - `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md`
   - `SABSA_RISK_ANALYSIS_UPDATE_2026-05-28.md`
   - `VIRTUAL_PENTEST_STATUS_2026-05-28.md`
   - `SYSTEM_HEALTH_REGISTER.md`
3. **Historisk arkitektur/runbook**
   - `TimeLapse_SABSA_Architecture_v9.docx`
   - `TimeLapse_SABSA_Risk_Assessment_v6.md.docx`
   - `RISK_ASSESSMENT_v6.md`
   - `TimeLapse_Roadmap_v4.docx`
   - `TimeLapse_Edge_Runbook_v7.docx`
   - `TimeLapse_Configuration_Guide_v4.docx`
4. **Nikon Z30**
   - `Nikon Z30/Z30 gphoto summary debug.gdoc`
   - seneste commits og samtalehistorik i `2026-06-03-Timelapse - Risk og plan videre.md`

## Gældende arkitekturforståelse

- TimeLapse Pro er en multi-tenant edge/headend-platform til ubestridelig byggepladsdokumentation.
- SABSA-attributterne der styrer designet er især availability, integrity, confidentiality, accountability, authenticity, manageability, continuity, auditability, economic efficiency og customer value.
- Edge skal som normal produktionsregel være pull-baseret og må ikke afhænge af direkte GitHub/Internet.
- Headend er update authority, policy authority og GRC evidence authority.
- Moderne headend er Mac Mini, FastAPI, PostgreSQL, React UI, HTTPS/nginx, SIEM, CMDB, AI/Ollama og backup/update governance.
- Edge har lokal autonomi, SQLite/WAL, store-and-forward, capture quality, sidecar/XMP, API-primary upload og SFTP som sekundær/backup-kanal.
- Nikon Z30 er nu et primært kameramål og er væsentligt mere kapabelt end de gamle Canon-profiler.

## Vigtigste åbne gaps

1. **Production identity og attestation**
   - Reelle produktionsdevices skal have API credentials og signing credentials.
   - Legacy tokens skal udfases.
   - Dummy/import/onboarding devices skal klassificeres korrekt i CMDB, så de ikke forvrænger compliance-score.

2. **Backup, restore og failover evidence**
   - Headend backup skal være off-host/NAS-forankret.
   - Restore skal testes og gemmes som evidence.
   - Cold/warm standby og Edge bare-metal restore/ISO skal designes som governance-flow, ikke kun teknik.

3. **Signed change workflow**
   - Change tickets skal være obligatoriske for updates, backup, restore, ISO og high-risk AI/cloud decisions.
   - Approval skal bindes til bruger, rolle, MFA/session context, scope, risk, rollback og signatur.

4. **Update enforcement**
   - Customer/site/camera/device scope skal håndhæves hele vejen fra policy til target execution.
   - Maintenance window, reboot-policy, staged rollout og rollback evidence skal færdiggøres.
   - Legacy git-update paths skal forblive LAB-only eller fjernes fra production path.

5. **Secrets og transport hardening**
   - `JWT_SECRET` fallback skal verificeres/fjernes for production.
   - SFTP host key policy må ikke bruge AutoAddPolicy i production/lab-flow uden eksplicit trust handling.
   - WiFi-kodeord/config-secrets skal krypteres eller håndteres via device-bound secret flow.

6. **CMDB completeness**
   - Installed-state skal dække hardware, firmware, OS packages, Python/venv packages, app version, services og hardening state.
   - Headend skal beregne missing updates/risk; Edge skal rapportere installed-state, ikke beslutte update authority.

7. **AI governance**
   - Ollama/Open WebUI/Timelapse AI skal styres med kapacitets- og prioritetspolitik.
   - Beslutning mellem local realtime, queued, cloud, backup-headend batch og manual review skal baseres på risk, SLA, cost og customer policy.

8. **Compliance pack**
   - SBOM, VDP/security.txt, DPIA, supportperiode-policy, ENISA/NIS2 incident process og CRA/CE-plan mangler stadig som formel pakke.

## Næste anbefalede arbejdsspor

1. Luk P1-sikkerhedsfund: JWT secret, AutoAddPolicy, WiFi secret handling.
2. Gør backup/restore til et signeret evidence-flow.
3. Gør change ticket obligatorisk for update/backup/restore.
4. Færdiggør device credentials og CMDB device classification.
5. Fortsæt Nikon Z30 med remote focus/liveview/power stability og korrekt drift-profile.

## Hardening-status 2026-06-03

- `JWT_SECRET` er production-fail-fast: `TIMELAPSE_ENV=production` kræver eksplicit secret på mindst 32 tegn.
- SFTP host-key trust er production-safe: uden `known_hosts` nægter Edge at auto-truste host keys. LAB kan eksplicit bruge `TIMELAPSE_SFTP_ALLOW_AUTO_ADD_HOSTKEY=1`.
- WiFi-password via LAB `lab_command` er blokeret som default og altid blokeret i production. Midlertidig LAB/staging brug kræver `TIMELAPSE_ALLOW_LAB_WIFI_PASSWORDS=1`.
- Lokal Edge provisioning CLI er tilføjet i `edge/tools/bootstrap_cli.py` til Headend URL/bootstrap token, WiFi, Ethernet og 4G USB modem.
- Lokal provisioning runbook er tilføjet i `Edge_Local_Provisioning_Runbook_2026-06-03.md`, inkl. captive portal/AP-mode design.

Næste production-readiness punkt er captive portal/AP-mode eller backup/restore evidence, afhængigt af om første site kræver lokal selvbetjent netværksopsætning før installation.
