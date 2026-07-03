# Codex - Go-live krav foer Internet og timelapse-pro.dk

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Gælder:** Foer Headend saettes Internet-facing og foer skift til `timelapse-pro.dk`.

## 1. Go-live beslutning

Codex-vurdering pr. 2026-06-23: **No-go for Internet-facing production**.

Systemet kan fortsaette i lab/pre-production, men foelgende krav skal opfyldes foer `backend.timelapse-pro.dk` bruges som produktionsbackend.

## 2. Netvaerk og porte

| Krav | Status | Gate |
|---|---|---|
| Mac Headend maa ikke eje public TCP 80/443 for TimeLapse backend | Aaben | P0 |
| Cloudflare Tunnel eller tilsvarende skal terminere public backend hostname | Aaben | P0 |
| Headend-origin skal lytte paa loopback/non-standard port, fx `127.0.0.1:18443` | Aaben | P0 |
| TCP 21 maa ikke anvendes | OK/skal verificeres | P0 |
| TCP 22 maa ikke bruges til TimeLapse SFTP eller normal TimeLapse drift | Delvist | P0 |
| TCP 8080 maa ikke vaere public | OK/skal verificeres | P0 |
| Ukendte/co-resident porte skal klassificeres | Aaben | P1 |
| OpenWebUI skal vaere lab-only eller RBAC-beskyttet intern service | Aaben | P1 |

## 3. Domaener

| Domaene | Formaal | Krav |
|---|---|---|
| `www.timelapse-pro.dk` | Public informationssite | Statisk hosting, ikke Headend-origin |
| `timelapse-pro.dk` | Redirect eller public site | Ikke direkte Headend |
| `backend.timelapse-pro.dk` | Kunde/admin UI og API | Cloudflare Tunnel/WAF/rate limiting |

Login-knapper paa public website skal redirecte til `https://backend.timelapse-pro.dk/login`.

## 4. Auth og adgang

| Krav | Status | Gate |
|---|---|---|
| RBAC paa alle admin/customer endpoints | Delvist/godt | P0 |
| CMDB maa ikke vaere anonymt laesbar | Loest | P0 |
| Stabil staerk JWT secret | Loest i drift | P0 |
| MFA/WebAuthn for super_admin/admin/high-risk operations | Aaben | P1, P0 hvis flere admins/kunder |
| Rate limiting paa login/API | Delvist via nginx | P1 |
| Break-glass adgang krypteret og auditeret | Delvist | P1 |

## 5. Device identity og updates

| Krav | Status | Gate |
|---|---|---|
| Aktiv Edge HMAC-signering | Delvist | P0 |
| Stale/legacy credentials migreret eller revokeret | Aaben | P0 |
| Edge maa ikke bruge direkte GitHub/Internet/apt i prod | Princip implementeret | P0 |
| App artifact update E2E paa aktiv Edge | Loest i lab | P0 |
| OS offline artifact update E2E paa aktiv Edge | Aaben | P1 |
| Change ticket med artifact/SBOM/rollback | Delvist | P1 |
| Per-target update status | Aaben | P1 |

## 6. Backup og resiliens

| Krav | Status | Gate |
|---|---|---|
| Headend backup koerer til kendt target | Delvist | P0 |
| Restore-test gennemfoert og dokumenteret | Aaben | P0 |
| RTO/RPO defineret | Aaben | P1 |
| Startup-preflight for `/Volumes/data-fast` | Aaben | P1 |
| Node-agent koerer og rapporterer frisk inventory | Aaben | P0/P1 |
| Offsite backup plan | Aaben | P1 |

## 7. GDPR og compliance

| Krav | Status | Gate |
|---|---|---|
| DPIA-template pr. kunde/site | Aaben | P0 for kundeproduktion |
| Retention policy pr. kamera | Aaben | P0 |
| Databehandleraftale-template | Aaben | P0 |
| Subprocessor-liste, inkl. Google/Gemini | Aaben | P1 |
| Adgangslog pr. billede/download/export | Aaben | P1 |
| Incident response med GDPR 72t proces | Aaben | P1 |

## 8. Kvalitet og drift

| Krav | Status | Gate |
|---|---|---|
| GitHub Actions groenne | Senest groent efter CI-fix | P0 |
| `slowapi` i requirements | Aaben | P1 |
| Frontend lint gate | Aaben | P1 |
| README/driftsmanual opdateret | Delvist via Codex docs | P1 |
| Nikon Z30 LAB/fokus/video QA | Aaben | P1 foer rigtigt site |

## 9. Endelig go-live test

Foer go-live skal foelgende dokumenteres:

```bash
lsof -nP -iTCP -sTCP:LISTEN
curl https://backend.timelapse-pro.dk/api/health
curl -i https://backend.timelapse-pro.dk/api/cmdb/
curl -i https://backend.timelapse-pro.dk/api/admin/stats
```

Forventet:

- Ingen TimeLapse-origin paa public `*:80`, `*:443`, `*:21`, `*:22`, `*:8080`.
- Health `200`.
- CMDB/admin endpoints `401` uden login.
- Seneste backup kan restores.
- Aktiv Edge kan heartbeat, capture, upload og update-policy-poll.

