# TimeLapse Pro — Dokumentpakke (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Formål:** Pege på de gældende (v10-konsoliderede) dokumenter efter dokumentgennemgang, risk assessment og port-/go-live-plan.
**Konsoliderer:** `DOKUMENTPAKKE_OVERSIGT_2026-06-23.md`, `Codex_DOKUMENTPAKKE_OVERSIGT_2026-06-23.md` (arkiveret i `Gamle versioner/`).

> Se `00_START_HER.md` for det fulde master-indeks og onboarding af en ny session.

## Autoritative dokumenter (v10)

| Dokument | Formål |
|---|---|
| `RISK_ASSESSMENT_v10.md` | Samlet SABSA/ISO 27001/IEC 62443/CRA/NIS2/GDPR risk assessment og virtuel penetrationstest |
| `KRAVREGISTER_og_STATUS_v10.md` | Samlet krav-/ønskeregister, bygget status, mangler og tidslinje |
| `GO_LIVE_CHECKLIST_v10.md` | Konkrete krav før Headend sættes på Internet og domænet skifter |
| `PORT_AUDIT_og_WEBSITE_v10.md` | Portkrav, aktuelle afvigelser og plan for `www.timelapse-pro.dk` / `backend.timelapse-pro.dk` |
| `BRUGERMANUAL_v10.md` | Brugermanual for kunde/site manager/almindelig bruger |
| `MENUGUIDE_BRUGER_v1.md` | Menu-for-menu beskrivelse af alle bruger-sider (felt-for-felt, rollekrav, fejlfinding) |
| `ADMINISTRATORMANUAL_v10.md` | Administratormanual for drift, sikkerhed, update, backup, CMDB og go-live |
| `MENUGUIDE_ADMIN_v1.md` | Menu-for-menu beskrivelse af alle admin-sider og Admin-dropdownens undermenuer |
| `Timelapse_pro_full_documentation_v10.md` | Samlet systemdokumentation (arkitektur, komponenter, flows) |
| `SABSA_Architecture_v10.md` | SABSA-arkitektur (konsolideret fra .docx v3–v9) |
| `REGULATORISK_OG_STANDARD_REFERENCE_v1.md` | Living EU/Danmark regulatory horizon og standardreference for AI, cyber, privacy, produkt og OT |
| `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` | Fælles arbejds-, review- og handovermodel for Peter, Claude og Codex |

## Kildegrundlag

Tekstudtræk fra lokale filer i `Dokumentation/`:

- ~79–110 filer gennemgået over flere sessioner.
- Markdown, konfigurationsfiler og de fleste `.docx` blev læst; historiske versioner brugt til historik og konfliktidentifikation.
- Google Drive-pointere (`.gdoc`, `.gslides`) er identificeret men ikke hentet via Drive.
- PDF-hardwaremanualer (OrangePi) beholdes som reference, ikke tekstudtrukket.

De nyeste/gældende dokumenter er vægtet højest.

## Kendte uoverensstemmelser (historik → beslutning)

| Emne | Uoverensstemmelse | Beslutning/anbefaling |
|---|---|---|
| Porte `80/443` | Ældre docs og aktiv nginx bruger public `80/443`; nyere krav siger TimeLapse ikke må eje dem på Mac Headend | ~~Public `80/443` må ejes af Cloudflare/website/proxy; Mac Headend-origin flyttes til `127.0.0.1:18443`~~ (**rettet, periodisk tjek #49:** denne 18443/Cloudflare Tunnel-anbefaling er forældet — CrushFTP ejer fortsat 80/443/21/22 på staging/prod-maskinerne, og backend eksponeres i stedet **direkte på port 8443**, certifikat via DNS-01 (`certbot-dns-cloudflare`), INGEN Cloudflare Tunnel; besluttet 2026-07-05, se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4) |
| SFTP port | Ældre docs bruger `22`/`2222`; nyere portprofil bruger `22222`, portplan foreslår `12222` | Ny production bør bruge `12222`; aldrig TimeLapse på `22` |
| JWT algoritme | Ældre RBAC-docs beskriver RS256; aktuel kode bruger HS256 | Dokumentér HS256 som aktuel; migrér evt. til RS256/EdDSA, ellers stærk secret + kort session |
| Auth tokens i UI | Ældre docs siger ingen localStorage; aktuel UI bruger localStorage | Før production bør auth-cookie være primær, localStorage risikovurderes/ryddes |
| MFA | Ældre docs beskriver MFA som Sprint C-klar; assessments viser ikke fuldt enforced | MFA/WebAuthn obligatorisk for admin/high-risk før moden flerbrugerdrift |
| Update flow | Ældre scripts har `git pull`/apt-veje; nyere krav siger Edge må ikke bruge Internet | Legacy paths lab-only/opt-in; må ikke være production path |
| OS updates | Ældre flow brugte `apt-get upgrade`; nyere krav kræver Headend-signeret offline artifact | Kun offline artifact med manifest/signatur/hash og `apt-get --no-download` |
| AI-tags | Lokal Ollama hallucinerer; brugerkrav ønsker brugbare vejr-/lys-/kvalitetstags | Semantiske tags i cloud/Gemini med fast ontologi; Edge AI deterministisk CV/kvalitet |
| Kamera | Ældre docs er Canon EOS-orienterede; aktivt kamera er Nikon Z30 | Nikon Z30 profil er gældende; færdiggøres i LAB/fokus/video |
| Backup | Docs omtaler backup, men restore-test mangler | Ikke production-godkendt før restore-test foreligger |
| Node-agent | CMDB/GRC kræver frisk inventory; reassessment viser node-agent stoppet | Genetabler node-agent før go-live |
| Open WebUI | UI/link findes, men service/rolle uklar | **Løst (2026-08-20-markeret):** Open WebUI-runtime er committet (`headend/openwebui_runtime.py`, R27 lukket), siden `/openwebui` er admin-gated, og Ollama-runtime-styring (Normal/Pause/Lav-memory) er bygget 2026-07-20. Status: lab-komponent med launchd + RBAC. Sektionen "Peter vil gerne lege med Ollama" er eksplicit eksperimentel |
| Edge polling | Ældre design-docs beskriver separate heartbeat/config/SIEM-loops | **Løst (2026-08-19, PR #76):** konsolideret til én sync-poll (`sync_poll_interval_minutes`, default 5 min, `POST /api/edge/sync/{device_id}`). `docs/admin-guide.md` er opdateret; `docs/system-wide-poll-mechanisms.md` og `docs/drift-mode-optimering.md` er markeret som historiske |
| Storage | Ældre paths peger på `/Volumes/data`; aktiv storage er `/Volumes/data-fast` | `/Volumes/data-fast` er canonical; startup-preflight og single source of truth mangler |

## Samlet status

TimeLapse Pro er lab/pre-production-klar med en stærk retning:

- aktiv edge (`TL-C87FF9587CA0`, R&D/test-edge) tager billeder og uploader
- Headend UI/API svarer
- RBAC, CMDB og Key Management er væsentligt forbedret
- app artifact-update er E2E-testet på aktiv edge
- Global Config og kamera-binding er på plads
- Edge image build og download-flow / statisk website er etableret

Systemet er ikke Internet-facing production-klar endnu. De største blockere:

1. Port-/proxy-migration væk fra public `80/443` på Mac Headend.
2. Backup + restore evidence.
3. GDPR DPIA/retention/databehandlergrundlag.
4. Frisk CMDB inventory via node-agent.
5. HMAC/stale credential cleanup og MFA-governance.
6. Nikon Z30 LAB/fokus/video-funktioner færdiggøres.
