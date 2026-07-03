# Codex - TimeLapse Pro dokumentpakke 2026-06-23

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Status:** Rent Codex-dokumentsaet, oprettet for at adskille denne vurdering fra Claude-/andre parallelle dokumenter.

## Autoritative Codex-dokumenter

| Dokument | Formaal |
|---|---|
| `Codex_RISK_ASSESSMENT_v7_2026-06-23.md` | SABSA/ISO 27001/IEC 62443/CRA/NIS2/GDPR risk assessment og virtuel penetrationstest |
| `Codex_KRAVREGISTER_og_STATUS_2026-06-23.md` | Samlet krav, oensker, bygget status, mangler og tidslinje |
| `Codex_GO_LIVE_CHECKLIST_2026-06-23.md` | Konkrete krav foer Headend saettes paa Internettet og domaenet skiftes |
| `Codex_PORT_AUDIT_og_WEBSITE_2026-06-23.md` | Dokumentation af portkrav, aktuelle afvigelser og website/backend-arkitektur |
| `Codex_BRUGERMANUAL_2026-06-23.md` | Brugermanual for kunde, site manager og almindelig bruger |
| `Codex_ADMINISTRATORMANUAL_2026-06-23.md` | Administratormanual for drift, sikkerhed, update, backup, CMDB og go-live |
| `Codex_DOKUMENTPAKKE_OVERSIGT_2026-06-23.md` | Denne oversigt |

## Kildegrundlag

Codex gennemlaeste de lokale dokumenter i `Dokumentation/` og udtrak et midlertidigt tekstkorpus:

- 79 filer fundet.
- 54.470 tekstlinjer udtrukket.
- Markdown, konfigurationsfiler og de fleste `.docx`-filer blev laest.
- `.gdoc`/`.gslides` var lokale Google Drive-pointere og blev ikke hentet i denne koersel.
- 2 aeldre `.docx` timeoutede ved lokal konvertering.
- PDF-hardwaremanualer blev identificeret, men ikke tekstudtrukket lokalt.

De nyeste assessment-, update-, config-, Nikon-, go-live- og portdokumenter er vaegtet hoejest. Aeldre dokumenter bruges som historik og konfliktkilder.

## Centrale uoverensstemmelser

| Emne | Konflikt | Codex-vurdering |
|---|---|---|
| Porte 80/443 | Aeldre docs og aktiv lab-nginx bruger public 80/443; nyere krav siger TimeLapse ikke maa eje dem paa Mac Headend | Public 80/443 maa ejes af Cloudflare/website/proxy, men Mac Headend-origin skal flyttes til loopback/non-standard port |
| SFTP-port | Aeldre docs bruger 22/2222; nyere portmodel bruger 22222 og foreslaar 12222 | TimeLapse maa aldrig bruge 22 til SFTP i prod; 12222 anbefales for ny prod |
| JWT | Aeldre docs beskriver RS256; aktuel kode bruger HS256 | Ret docs eller migrer til asymmetrisk JWT; HS256 kan accepteres midlertidigt med staerk secret |
| UI tokens | Aeldre docs siger ingen localStorage; aktuel UI bruger localStorage til bruger/API config | Foer prod boer auth-cookie vaere primaer, og localStorage-brug risikovurderes |
| MFA | Aeldre docs kalder MFA klar; aktuelle findings viser ikke fuld enforcement | MFA/WebAuthn boer goeres obligatorisk for admin/high-risk operations |
| Update-flow | Aeldre scripts har git/apt direkte fra Edge; nyere krav siger Headend-only | Direkte GitHub/apt maa kun vaere lab-only opt-in |
| AI-tags | Lokal Ollama hallucinerede billedtags | Semantiske tags boer ligge i cloud/Gemini med fast ontologi; Edge AI boer vaere deterministisk kvalitet/fokus |
| Kamera | Aeldre docs er Canon-orienterede; aktivt kamera er Nikon Z30 | Nikon Z30-profil og LAB/fokus/video er gaeldende retning |
| Backup | Backup omtales, men restore-test mangler | Ikke production-godkendt foer restore-evidens findes |
| Storage | Aeldre sti `/Volumes/data`; aktiv sti `/Volumes/data-fast` | `/Volumes/data-fast` er canonical nu; startup-preflight mangler |

## Samlet Codex-status

TimeLapse Pro er lab/pre-production-klar:

- Headend UI/API svarer.
- Aktiv Edge `TL-C87FF9587CA0` er R&D/test-edge.
- Capture/upload virker.
- RBAC, CMDB og Key Management er vaesentligt forbedret.
- App artifact-update er E2E-testet paa aktiv Edge.
- Global Config og kamera-binding er paa plads.
- Edge image build og statisk website er etableret.

Systemet er ikke Internet-facing production-klar endnu. De vigtigste blockere er:

1. Port-/proxy-migration vaek fra public 80/443 paa Mac Headend.
2. Backup + restore-evidens.
3. GDPR DPIA, retention og databehandlergrundlag.
4. Frisk CMDB inventory via node-agent.
5. HMAC/stale credential cleanup.
6. MFA/WebAuthn-governance.
7. Nikon Z30 LAB/fokus/video faerdiggoerelse.

