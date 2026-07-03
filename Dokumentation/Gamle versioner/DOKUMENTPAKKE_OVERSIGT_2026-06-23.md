# TimeLapse Pro - Dokumentpakke 2026-06-23

**Dato:** 2026-06-23  
**Formål:** Pege på de gældende dokumenter efter konsolideret dokumentgennemgang, risk assessment og port-/go-live-plan.

## Autoritative dokumenter

| Dokument | Formål |
|---|---|
| `RISK_ASSESSMENT_v7_2026-06-23.md` | Samlet SABSA/ISO 27001/IEC 62443/CRA/NIS2/GDPR risk assessment og virtuel penetrationstest |
| `KRAVREGISTER_og_STATUS_2026-06-23.md` | Samlet krav-/ønskeregister, bygget status, mangler og tidslinje |
| `GO_LIVE_CHECKLIST_2026-06-23.md` | Konkrete krav før Headend sættes på Internet og domænet skifter |
| `PORT_AUDIT_og_WEBSITE_2026-06-23.md` | Dokumentation af portkrav, aktuelle afvigelser og plan for `www.timelapse-pro.dk` / `backend.timelapse-pro.dk` |
| `BRUGERMANUAL_2026-06-23.md` | Brugermanual for kunde/site manager/almindelig bruger |
| `ADMINISTRATORMANUAL_2026-06-23.md` | Administratormanual for drift, sikkerhed, update, backup, CMDB og go-live |
| `Sessionoverlevering_2026-06-23_konsolideret.md` | Komprimeret sessionoverlevering til ny Codex-session |

## Læste kilder og begrænsninger

Der er lavet tekstudtræk fra lokale filer i `Dokumentation/`:

- 79 filer fundet.
- 54.470 tekstlinjer udtrukket til midlertidigt analyse-korpus.
- Markdown, konfigurationsfiler og de fleste `.docx` blev læst.
- Google Drive-pointere (`.gdoc`, `.gslides`) er identificeret, men ikke hentet via Drive i denne kørsel.
- 2 ældre `.docx` timeoutede ved lokal `textutil`-konvertering.
- 3 PDF-manualer kunne ikke konverteres lokalt, fordi `pdftotext` ikke var tilgængelig.

De nyeste/gældende assessment-, update-, config-, Nikon-, go-live- og portdokumenter er læst og vægtet højest. Ældre dokumenter er brugt til historik og konfliktidentifikation.

## Kendte uoverensstemmelser

| Emne | Uoverensstemmelse | Beslutning/anbefaling |
|---|---|---|
| Porte `80/443` | Ældre docs og aktiv nginx bruger public `80/443`; nyere krav siger TimeLapse ikke må eje dem på Mac Headend | Public `80/443` må ejes af Cloudflare/website/proxy, men Mac Headend-origin flyttes til `127.0.0.1:18443` |
| SFTP port | Ældre docs bruger `22`/`2222`; nyere portprofil bruger `22222`, og portplan foreslår `12222` | Ny production bør bruge `12222` eller dokumenteret non-standard port; aldrig TimeLapse på `22` |
| JWT algoritme | Ældre RBAC-docs beskriver RS256; aktuel kode bruger HS256 | Dokumentér HS256 som aktuel implementation; migrér til RS256/EdDSA eller behold HS256 med stærk secret og kort session, men ret docs |
| Auth tokens i UI | Ældre docs siger ingen localStorage; aktuel UI bruger localStorage til bruger/API config | Før production bør auth-cookie være primær, og localStorage-brug risikovurderes/ryddes |
| MFA | Ældre docs beskriver MFA som Sprint C-klar; aktuelle assessments viser MFA/WebAuthn ikke fuldt enforced | Gør MFA/WebAuthn obligatorisk for admin og high-risk operations før moden flerbrugerdrift |
| Update flow | Ældre scripts/docs har `git pull`/direkte GitHub og apt-veje; nyere krav siger Edge må ikke bruge Internet | Legacy paths markeres lab-only/opt-in og må ikke være production path |
| OS updates | Ældre flow brugte `apt-get upgrade`; nyere krav kræver Headend-signeret offline artifact | Kun offline artifact med manifest/signatur/hash og `apt-get --no-download` accepteres |
| AI-tags | Lokal Ollama er testet, men hallucinerer; brugerkrav ønsker brugbare vejr-/lys-/kvalitetstags | Semantiske tags bør ligge i cloud/Gemini med fast ontologi; Edge AI bør være deterministisk CV/kvalitet |
| Kamera | Ældre docs er Canon EOS 1300/1000-orienterede; aktivt kamera er Nikon Z30 | Nikon Z30 profil er gældende og skal færdiggøres i LAB/fokus/video |
| Backup | Docs omtaler backupfunktion, men restore-test mangler | Backup er ikke production-godkendt før restore-test foreligger |
| Node-agent | CMDB/GRC kræver frisk Headend inventory; reassessment viser node-agent stoppet | Genetabler node-agent før go-live |
| Open WebUI | UI/link findes, men service/rolle er uklar | Beslut lab-only eller prod-komponent med launchd, health, RBAC og non-standard loopback port |
| Storage | Ældre paths peger på `/Volumes/data`; aktiv storage er `/Volumes/data-fast` | `/Volumes/data-fast` er canonical nu; startup-preflight og single source of truth mangler |

## Samlet status

TimeLapse Pro er lab/pre-production-klar og har en stærk retning:

- aktiv edge tager billeder og uploader
- Headend UI/API svarer
- RBAC og CMDB er væsentligt forbedret
- app artifact-update er E2E-testet på aktiv edge
- Global Config og kamera-binding er på plads
- Edge image build og download-flow er etableret

Systemet er ikke klar til Internet-facing production endnu. De største blockere er:

1. Port-/proxy-migration væk fra public `80/443` på Mac Headend.
2. Backup + restore evidence.
3. GDPR DPIA/retention/databehandlergrundlag.
4. Frisk CMDB inventory via node-agent.
5. HMAC/stale credential cleanup og MFA-governance.
6. Nikon Z30 LAB/fokus/video-funktioner færdiggøres.

