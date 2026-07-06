# nginx → Cloudflare Tunnel — konkret migrationsplan for LAB-domænet (v1)

> **STATUS 2026-07-05 (Claude) — SUPERSEDED for prod/staging, ÅBENT SPØRGSMÅL for `rd`/lab:**
> Peter har eksplicit bedt om at dokumenterne rettes så Cloudflare Tunnel ikke bruges "til
> frontend" ("Du må gerne rette dokumenterne så vi ikke anvender Claudflare tunnel til
> frontend"). For `backend.timelapse-pro.dk` (staging/prod) er dette allerede udført — se
> `PORT_AUDIT_og_WEBSITE_v10.md` §4, `GO_LIVE_CHECKLIST_v10.md` §A og
> `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §8: arkitekturen er nu port 8443 + DNS-01, ikke
> Cloudflare Tunnel.
>
> DETTE dokument beskriver derimod en Cloudflare Tunnel-migration for det NUVÆRENDE
> `rd`/lab-domæne (`timelapse.froekjaer.dk`), som er et andet domæne, en anden maskine (ingen
> CrushFTP-portkonflikt dér) og ikke kundevendt. Jeg kan ikke afgøre med sikkerhed om Peters
> "til frontend"-instruktion også dækker dette lab-domæne, eller kun den kundevendte
> prod-frontend — planen herunder er derfor markeret SUPERSEDED/PÅ HOLD, ikke slettet, indtil
> Peter bekræfter. Hvis lab-domænet SKAL undgå Cloudflare Tunnel ligesom prod, er den relevante
> erstatning enten (a) fortsat direkte nginx på standard 80/443 (som i dag — ingen
> portkonflikt på `rd`), eller (b) samme 8443-mønster som prod, hvis konsistens på tværs af
> miljøer foretrækkes. Ingen kode er ændret som følge af denne markering.

**Dato:** 2026-07-04 (nat)
**Forfatter:** Claude (mens Peter sov — se `HANDOVER_LOG.md`)
**Status:** Forberedt, IKKE eksekveret. Kræver Peter (interaktivt Cloudflare-login kan
ikke automatiseres). **Se SUPERSEDED-banner ovenfor — afventer Peters bekræftelse for `rd`/lab.**
**Forhold til eksisterende dokumentation:** `PORT_AUDIT_og_WEBSITE_v10.md` §4 beskrev
tidligere migrationen for de FREMTIDIGE produktionsdomæner
(`timelapse-pro.dk`/`backend.timelapse-pro.dk`) — men §4 er nu selv rettet til IKKE at bruge
Cloudflare Tunnel (se banner ovenfor). Dette dokument gør fortsat det samme konkret
for det AKTUELLE lab-domæne (`timelapse.froekjaer.dk` + `openwebui.froekjaer.dk`), som
er det, der rent faktisk er eksponeret på public 80/443 i dag (VPEN-2026-001,
GO_LIVE_CHECKLIST_v10.md §A-01–A-04) — men om det SKAL Tunnel-migreres er nu et åbent
spørgsmål, ikke en besluttet plan.

---

## 0. Hvorfor lab-domænet også skal migreres

`RISK_ASSESSMENT_v10.md` §5.2 (VPEN-2026-001) noterer: "Med Cloudflare foran er dette
acceptabelt i lab" — men jeg har IKKE kunnet bekræfte i denne gennemgang, om
`timelapse.froekjaer.dk` rent faktisk proxies gennem Cloudflare (orange-cloud DNS) i
dag, eller om DNS peger direkte på Mac Mini'ens IP. **Peter bør bekræfte dette FØRST**
(`dig timelapse.froekjaer.dk` — hvis IP'en er en Cloudflare-IP-range, er der allerede
et lag beskyttelse; hvis det er jeres egen offentlige IP, er nginx reelt direkte
eksponeret på internettet lige nu). Uanset svaret lukker denne migration hullet
permanent og er identisk arbejde med det, der alligevel skal laves til produktion.

---

## 1. Nuværende konfiguration (bekræftet ved læsning af den faktiske fil)

`deploy/nginx/timelapse.froekjaer.dk.conf` (linje 29-171) har to domæner, hver med et
`listen 80` (ACME + redirect) og `listen 443 ssl` (faktisk trafik) server-block:

- `timelapse.froekjaer.dk` — statisk SPA (`timelapse-ui/dist`) + `/api/*` proxy til
  `127.0.0.1:8000`, med rate-limiting og en fuld CSP-header.
- `openwebui.froekjaer.dk` — proxy til `127.0.0.1:8080` bag et `auth_request`-kald mod
  headend for adgangskontrol.

## 2. Ny nginx-konfiguration (fuld fil, klar til at erstatte den nuværende)

Ændringer fra original: (a) begge `listen 80`-blokke fjernet — ACME-challenge og
redirect er ikke længere nginx' ansvar, Cloudflare terminerer TLS og styrer redirect
selv; (b) `listen 443 ssl` → `listen 127.0.0.1:18443 ssl` på begge resterende blokke;
(c) **alt andet er byte-for-byte uændret** (samme proxy_pass, samme headers, samme CSP,
samme rate-limiting) for at minimere risikoen for at introducere nye fejl samtidig med
port-migrationen.

```nginx
events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;

    log_format timelapse '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent"';
    access_log /opt/homebrew/var/log/nginx-timelapse-access.log timelapse;
    error_log  /opt/homebrew/var/log/nginx-timelapse-error.log warn;

    limit_req_zone $binary_remote_addr zone=api_login:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=api_general:10m rate=120r/m;

    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    server {
        listen 127.0.0.1:18443 ssl;
        server_name openwebui.froekjaer.dk;

        ssl_certificate     /opt/homebrew/etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /opt/homebrew/etc/nginx/ssl/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        location = /_timelapse_openwebui_auth {
            internal;
            proxy_pass http://127.0.0.1:8000/api/openwebui/access/check;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header Cookie            $http_cookie;
            proxy_set_header Host              timelapse.froekjaer.dk;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
        }

        location / {
            auth_request /_timelapse_openwebui_auth;
            auth_request_set $timelapse_user_email $upstream_http_x_timelapse_user_email;
            auth_request_set $timelapse_user_name  $upstream_http_x_timelapse_user_name;
            auth_request_set $timelapse_user_role  $upstream_http_x_timelapse_user_role;
            error_page 401 403 = @openwebui_denied;
            proxy_pass http://127.0.0.1:8080;
            proxy_http_version 1.1;
            proxy_buffering off;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_set_header Upgrade           $http_upgrade;
            proxy_set_header Connection        $connection_upgrade;
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Timelapse-User-Email $timelapse_user_email;
            proxy_set_header X-Timelapse-User-Name  $timelapse_user_name;
            proxy_set_header X-Timelapse-User-Role  $timelapse_user_role;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie            $http_cookie;
            proxy_cookie_flags ~ secure httponly samesite=lax;
        }

        location @openwebui_denied {
            return 302 https://timelapse.froekjaer.dk/openwebui;
        }
    }

    server {
        listen 127.0.0.1:18443 ssl;
        server_name timelapse.froekjaer.dk;

        ssl_certificate     /opt/homebrew/etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /opt/homebrew/etc/nginx/ssl/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' https://timelapse.froekjaer.dk https://openwebui.froekjaer.dk; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" always;

        root /Users/peter/projects/timelapse-pro/timelapse-ui/dist;
        index index.html;

        location / {
            try_files $uri $uri/ /index.html;
        }

        location ~ ^/api/auth/login {
            limit_req zone=api_login burst=5 nodelay;
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie            $http_cookie;
        }

        location /api/import/ {
            client_max_body_size 1024m;
            proxy_request_buffering off;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie            $http_cookie;
        }

        location /api/ {
            limit_req zone=api_general burst=60 nodelay;
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie            $http_cookie;
        }
    }
}
```

**NB — `noTLSVerify`:** da nginx nu kun lytter på loopback med det eksisterende
selvsamme certifikat, skal cloudflared-config'en (§3) bruge `noTLSVerify: true` for
denne origin, præcis som eksemplet i `PORT_AUDIT_og_WEBSITE_v10.md` §4.3 — ellers
klager cloudflared over certifikatets `server_name`-mismatch mod `127.0.0.1`.

## 3. cloudflared config til lab-domænerne

```yaml
tunnel: <tunnel-id>
credentials-file: /Users/peter/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: timelapse.froekjaer.dk
    service: https://127.0.0.1:18443
    originRequest:
      noTLSVerify: true
  - hostname: openwebui.froekjaer.dk
    service: https://127.0.0.1:18443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

## 4. Ordnet, sikker udførelsesplan

**Vigtigt princip:** hold 80/443 KØRENDE sideløbende med 18443, indtil Tunnel er
bekræftet at virke udefra. Fjern først 80/443 til allersidst. På den måde er der
aldrig et vindue hvor siden er nede for rigtige brugere.

1. **Bekræft nuværende beskyttelse (afgør hastværk):**
   ```bash
   dig +short timelapse.froekjaer.dk
   ```
   Sammenlign med jeres kendte offentlige IP — hvis den IKKE matcher (dvs. det er en
   Cloudflare-IP), er I allerede proxied, og dette bliver et forbedringsarbejde, ikke et
   akut hul.

2. **Installer cloudflared** (kræver Homebrew, ingen live-ændring endnu):
   ```bash
   brew install cloudflare/cloudflare/cloudflared
   ```

3. **Interaktivt login — DETTE KAN JEG IKKE GØRE FOR DIG.** Åbner en browser til
   Cloudflare OAuth:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create timelapse-headend
   ```
   Notér `<tunnel-id>` fra outputtet — bruges i næste trin.

4. **Skriv `~/.cloudflared/config.yml`** med indholdet fra §3 ovenfor (udskift
   `<tunnel-id>` to steder).

5. **Tilføj `127.0.0.1:18443`-lytteren UDEN at fjerne 80/443 endnu** — brug filen fra
   §2, men behold midlertidigt de to `listen 80`-server-blokke fra den oprindelige fil
   oveni (kopiér dem ind igen). Test config-syntaks før reload:
   ```bash
   nginx -t -c /opt/homebrew/etc/nginx/timelapse.froekjaer.dk.conf
   nginx -s reload
   curl -sk https://127.0.0.1:18443/api/health
   ```
   Forventet: `{"status":"ok",...}` — hvis fejl her, STOP og undersøg før du går videre.

6. **Start tunnel foreground først (ikke som service endnu) og test udefra:**
   ```bash
   cloudflared tunnel run timelapse-headend
   ```
   I et andet terminalvindue/fra en anden maskine:
   ```bash
   curl https://timelapse.froekjaer.dk/api/health
   ```
   Bemærk: DNS skal først pege på tunnelen (§4.4 i `PORT_AUDIT_og_WEBSITE_v10.md` har
   CNAME-opskriften) — dette trin virker kun efter DNS er opdateret i Cloudflare
   dashboardet og har propageret.

7. **Installer som launchd-service** (så tunnelen overlever genstart):
   ```bash
   cloudflared service install
   ```

8. **Kun når 6 er bekræftet virkende i mindst nogle timer:** fjern `listen 80`-blokkene
   fra nginx-configen (den rene version i §2 ovenfor har dem allerede fjernet), og fjern
   `listen 443 ssl` helt (erstattet af `18443` fra start). Reload nginx igen og
   genbekræft `curl https://timelapse.froekjaer.dk/api/health` udefra.

9. **Slutverifikation:**
   ```bash
   sudo lsof -i -n -P | grep LISTEN | grep -v '127.0.0.1\|::1'
   ```
   Forventet: INGEN nginx/TimeLapse-proces på denne liste længere — kun evt.
   cloudflared (som selv opretter udgående forbindelser, ikke lytter offentligt).

## 5. Rollback

Hvis noget går galt EFTER trin 8 (public adgang holder op med at virke): behold en
kopi af den ORIGINALE `deploy/nginx/timelapse.froekjaer.dk.conf` (med `listen 80`/`443`)
ved siden af — reload med den originale fil for øjeblikkeligt at genskabe direkte
adgang, mens du fejlsøger cloudflared/DNS i baggrunden. Ingen af cloudflared-trinnene er
destruktive for nginx eller headend — det er rent additivt, indtil trin 8.

## 6. Ikke dækket her

- DNS-opsætning i selve Cloudflare-dashboardet (kræver kontoadgang — se
  `PORT_AUDIT_og_WEBSITE_v10.md` §4.4 for CNAME-opskriften).
- Selve produktionsdomænerne (`timelapse-pro.dk`/`backend.timelapse-pro.dk`) — dækket
  fyldestgørende i `PORT_AUDIT_og_WEBSITE_v10.md` §4-§5, kan tilføjes som yderligere
  `ingress`-regler i samme `config.yml` når I er klar til det skridt.
- Port 22222 (SFTP) → 12222-migrationen (GO_LIVE §A-08, kun "anbefalet", ikke blocker).
