# TimeLapse Pro Update Flow Testplan

Dato: 2026-06-12

## Scope

Denne testplan dækker alle update-typer i TimeLapse Pro:

- `os_security`
- `os_updates`
- `application_security`
- `application_updates`
- `timelapse_security`
- `timelapse_updates`

Edge må ikke hente direkte fra internet, GitHub eller eksterne package repositories i production. Edge installerer kun Headend-signerede artifacts.

## Flow

1. CMDB modtager installeret OS, kernel, OS-pakker, Python/venv-pakker og managed software fra Edge og Headend node-agent.
2. Headend sammenholder installed-state med et Headend-ejet update catalog fra lab/mirror.
3. Headend genererer SBOM fra CMDB inventory.
4. Headend opretter update-kandidater pr. type og severity.
5. Lab bygger artifact/bundle og kører preflight, installation, rollback og postflight-test.
6. Artifact registreres i Headend artifact-katalog med manifest, sha256 og signatur.
7. Artifact bindes til update/change ticket.
8. Test/lab deploy gennemføres og dokumenteres som `deployed`.
9. Update kan promoveres til staging.
10. Staging deploy gennemføres efter samme testplan, hvis relevant.
11. Production auto-deploy sker kun hvis resolved customer/site/device policy siger `auto` for update-typen, og alle gates er opfyldt.

## Lab Gate

Krav før promotion fra lab/test:

- SBOM findes for target device/headend.
- Artifact er registreret og signeret i Headend.
- Artifact-manifest indeholder distributionsmodel og rollback-strategi.
- Edge/Headend pre-update backup er oprettet.
- Offline install er testet uden internetadgang fra Edge.
- Postflight bekræfter service/API/capture/update-policy.
- Rollback test er dokumenteret eller begrundet som manuel.

## Staging Gate

Krav før production:

- Staging update har status `deployed`, hvis policy kræver staging.
- Ingen target har status `failed`, `blocked` eller `rolled_back` uden accepteret risk decision.
- GRC-risk og CMDB device-matrix er gennemgået.
- Maintenance/reboot-vindue er vurderet.

## Production Auto-Deploy Gate

Auto-deploy kan kun ske når:

- Update har et Headend-signeret artifact, hvis update-typen kræver artifact.
- Resolved update policy for target er `auto`.
- `customer_acceptance_required` er false, eller senere kundeaccept-flow har godkendt change request.
- `staging_required` er false, eller tilsvarende staging update er `deployed`.
- Edge henter update via `/api/updates/policy/{device_id}` og rapporterer mellemstatus til `/api/updates/report`.

## Customer Acceptance Future Hook

Kundeaccept skal senere kunne leveres via:

- Mail med signed change request og approval-link.
- API/webhook til kundens ticketing-system.
- Importeret kundegodkendelse bundet til `change_tickets` og `change_approvals`.

Ingen af disse integrationer må omgå artifact-, SBOM-, staging- eller policy-gates.
