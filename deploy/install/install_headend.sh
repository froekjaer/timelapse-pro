#!/bin/zsh
# TimeLapse Pro — Headend installations-script (macOS)
#
# Formål: gøre det muligt for Peter (ALENE, uden Claude/Codex-adgang, jf.
# Dokumentation/MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md §5) at bringe headend op
# på en NY fysisk maskine — staging (iMac) eller en fremtidig prod-server
# (timelapse-pro.dk, eller flere prod-servere senere) — uden live agent-hjælp.
#
# Skrevet 2026-07-05 (Claude), macOS-only (jf. Peters bekræftelse: RPi5 er udfaset,
# staging+prod er macOS for nu; Linux kan tilføjes senere hvis relevant).
#
# VIGTIGT — hvad dette script IKKE gør (bevidst, se INSTALLATION_GUIDE_HEADEND_v1.md):
#   - Opretter IKKE det første RBAC-login for dig (kræver MFA-enrollment i browseren,
#     kan ikke scriptes sikkert — se guiden §7).
#   - Rører IKKE CA/mTLS (koden findes ikke endnu, se opgave #52 / HANDOVER_LOG.md).
#   - Kører IKKE certbot automatisk (DNS-01/Cloudflare-token er en manuel/bevidst
#     handling — se guiden §6).
#   - Sletter/overskriver ALDRIG en eksisterende /etc/timelapse/headend.env uden at
#     spørge først.
#   - Bygger/deployer IKKE marketingsitet (www.timelapse-pro.dk) — det hostes
#     bevidst SEPARAT fra staging-/prod-maskinerne (se PORT_AUDIT_og_WEBSITE_v10.md
#     §5.3), fordi disse maskiner allerede kører CrushFTP på 21/22/80/443.
#
# VIGTIGT — portvalg (rettet 2026-07-05, se PORT_AUDIT_og_WEBSITE_v10.md §3/§4):
#   CrushFTP kører allerede på BÅDE staging-iMac'en og prod-Mac Mini'en og optager
#   21, 22, 80 og 443 på disse maskiner. Dette script binder derfor nginx til en
#   ikke-standard, direkte-offentlig port (default 8443, se TL_BACKEND_PORT) i
#   stedet for 443 — og rører ALDRIG 21/22/80/443. Certifikatet udstedes via
#   DNS-01 (certbot-dns-cloudflare), som slet ikke kræver at nginx besvarer noget
#   på port 80 — se guiden §6.
#
# Kør som: sudo ./install_headend.sh --config /path/til/dit-miljø.conf
# Se headend.env.example i denne mappe for et udgangspunkt til konfigurationsfilen.

set -euo pipefail

LOG_PREFIX="[install_headend]"

log()  { echo "$LOG_PREFIX $*"; }
warn() { echo "$LOG_PREFIX ⚠️  $*" >&2; }
die()  { echo "$LOG_PREFIX ❌ $*" >&2; exit 1; }

# ── 0. Argumenter ────────────────────────────────────────────────────────────
CONFIG_FILE=""
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG_FILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      cat <<EOF
Brug: $0 --config <miljø.conf> [--dry-run]

Konfigurationsfilen skal sætte som minimum:
  TL_ENV=rd|staging|prod
  TL_DOMAIN_BACKEND=backend.timelapse-pro.dk   # UI+API-domænet
  TL_BACKEND_PORT=8443                         # (valgfri, default 8443) — se nedenfor
  TL_REPO_DIR=/Volumes/data-fast/peter-home/projects/timelapse-pro
  TL_DATA_DIR=/Volumes/data-fast/timelapse-incoming/canonical-images
  TL_DB_NAME=timelapse_db
  TL_DB_USER=timelapse

TL_BACKEND_PORT: staging- og prod-maskinerne kører allerede CrushFTP på 21/22/80/443
  — TimeLapse Pro's nginx må ALDRIG binde til disse. Default er derfor 8443 (bekræftet
  Cloudflare-proxy-kompatibel HTTPS-port, se PORT_AUDIT_og_WEBSITE_v10.md §4). Sæt kun
  denne til noget andet hvis 8443 også er optaget på den konkrete maskine.

Marketingsitet (www.timelapse-pro.dk) er IKKE en del af dette script — det hostes
bevidst et andet sted end staging-/prod-maskinerne (se PORT_AUDIT_og_WEBSITE_v10.md §5.3).

Se example-staging.conf og example-prod.conf i denne mappe for komplette eksempler.
Den genererede /etc/timelapse/headend.env (secrets) er noget ANDET end denne
config-fil — den bygges automatisk af scriptet, du skal ikke selv skrive den.
--dry-run udskriver hvad scriptet VILLE gøre uden at ændre noget.
EOF
      exit 0
      ;;
    *) die "Ukendt argument: $1 (brug --help)" ;;
  esac
done

[[ -n "$CONFIG_FILE" ]] || die "Mangler --config <fil>. Se --help."
[[ -r "$CONFIG_FILE" ]] || die "Kan ikke læse config-fil: $CONFIG_FILE"

# shellcheck source=/dev/null
source "$CONFIG_FILE"

: "${TL_ENV:?TL_ENV skal være sat i config-filen (rd|staging|prod)}"
: "${TL_DOMAIN_BACKEND:?TL_DOMAIN_BACKEND skal være sat i config-filen}"
: "${TL_REPO_DIR:?TL_REPO_DIR skal være sat i config-filen}"
: "${TL_DATA_DIR:?TL_DATA_DIR skal være sat i config-filen}"
: "${TL_DB_NAME:=timelapse_db}"
: "${TL_DB_USER:=timelapse}"
: "${TL_BACKEND_PORT:=8443}"

if [[ "$TL_BACKEND_PORT" =~ ^(21|22|80|443)$ ]]; then
  die "TL_BACKEND_PORT=$TL_BACKEND_PORT er forbudt — CrushFTP ejer 21/22/80/443 på staging/prod (se PORT_AUDIT_og_WEBSITE_v10.md §3)."
fi

case "$TL_ENV" in
  rd|staging|prod) ;;
  *) die "TL_ENV skal være rd, staging eller prod — fik: '$TL_ENV'" ;;
esac

log "Miljø: $TL_ENV"
log "Backend-domæne: $TL_DOMAIN_BACKEND (port $TL_BACKEND_PORT — se PORT_AUDIT_og_WEBSITE_v10.md §4)"
log "Repo: $TL_REPO_DIR"
log "Marketingsite hostes IKKE af dette script (separat hosting, se §5.3 i PORT_AUDIT-dokumentet)."
[[ "$DRY_RUN" == "1" ]] && warn "DRY-RUN — ingen ændringer foretages"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [dry-run] $*"
  else
    eval "$@"
  fi
}

# ── 1. Forudsætninger ────────────────────────────────────────────────────────
log "Tjekker forudsætninger..."

[[ "$(uname)" == "Darwin" ]] || die "Dette script er macOS-only (jf. Peters bekræftelse 2026-07-05). Linux-understøttelse er ikke bygget endnu."

command -v brew    >/dev/null 2>&1 || die "Homebrew mangler — installér fra https://brew.sh først"
command -v python3 >/dev/null 2>&1 || die "python3 mangler"
command -v psql    >/dev/null 2>&1 || die "psql (PostgreSQL client) mangler — 'brew install postgresql@17'"
command -v nginx   >/dev/null 2>&1 || die "nginx mangler — 'brew install nginx'"
command -v npm     >/dev/null 2>&1 || die "npm mangler (til UI-build) — 'brew install node'"

[[ -d "$TL_REPO_DIR" ]] || die "TL_REPO_DIR findes ikke: $TL_REPO_DIR (klon repoet dertil først)"
[[ -f "$TL_REPO_DIR/headend/main.py" ]] || die "Finder ikke headend/main.py under $TL_REPO_DIR — forkert sti?"

log "Forudsætninger OK."

# ── 2. Kataloger (data + config UDENFOR repoet, jf. eksisterende konvention) ──
# /etc/timelapse/ holder secrets/config, adskilt fra Git-repoet — samme mønster
# som det eksisterende headend.env på rd-systemet (se SERVICES_OG_DRIFT-dokumentet).
ENV_DIR="/etc/timelapse"
ENV_FILE="$ENV_DIR/headend.env"
VENV_DIR="${TL_VENV_DIR:-$HOME/.venvs/timelapse-headend}"

log "Opretter $ENV_DIR (kræver sudo)..."
run "sudo mkdir -p '$ENV_DIR'"
run "sudo chown root:staff '$ENV_DIR'"
run "sudo chmod 750 '$ENV_DIR'"

run "mkdir -p '$TL_DATA_DIR'"

# ── 3. Python venv + dependencies ───────────────────────────────────────────
log "Opsætter Python venv ($VENV_DIR)..."
run "python3 -m venv '$VENV_DIR'"
run "'$VENV_DIR/bin/pip' install --upgrade pip"
run "'$VENV_DIR/bin/pip' install -r '$TL_REPO_DIR/headend/requirements.txt'"

# ── 4. PostgreSQL: DB + bruger (idempotent) ─────────────────────────────────
log "Sikrer PostgreSQL-database '$TL_DB_NAME' og bruger '$TL_DB_USER'..."
if [[ "$DRY_RUN" != "1" ]]; then
  if ! psql -U "$(whoami)" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$TL_DB_USER'" | grep -q 1; then
    log "Opretter DB-rolle '$TL_DB_USER' (login + createdb, IKKE superuser)..."
    createuser --login --createdb "$TL_DB_USER" || warn "Kunne ikke oprette rolle — findes den måske allerede under et andet navn?"
  fi
  if ! psql -U "$(whoami)" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$TL_DB_NAME'" | grep -q 1; then
    log "Opretter database '$TL_DB_NAME'..."
    createdb -U "$(whoami)" -O "$TL_DB_USER" "$TL_DB_NAME"
  fi
else
  echo "  [dry-run] ville oprette rolle/DB $TL_DB_USER/$TL_DB_NAME hvis de ikke findes"
fi

# ── 5. /etc/timelapse/headend.env — generér KUN hvis den ikke findes ────────
if [[ -f "$ENV_FILE" ]]; then
  warn "$ENV_FILE findes allerede — rører den IKKE (for at undgå at overskrive en"
  warn "produktions-JWT_SECRET eller anden allerede-live konfiguration). Sammenlign"
  warn "manuelt med headend.env.example hvis du vil tilføje nye nøgler."
else
  log "Genererer $ENV_FILE (nyt JWT_SECRET, aldrig genbrugt fra et andet miljø)..."
  JWT_SECRET_VALUE="$(openssl rand -hex 32)"
  BASE_URL="https://${TL_DOMAIN_BACKEND}:${TL_BACKEND_PORT}"
  ENV_CONTENT="# TimeLapse Pro headend — genereret af install_headend.sh $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Miljø: $TL_ENV. Denne fil ligger BEVIDST udenfor Git-repoet (/etc/timelapse/),
# jf. eksisterende konvention — se SERVICES_OG_DRIFT_kilde_til_sandhed.md.
# ALDRIG commit denne fil eller dens indhold noget sted.

TIMELAPSE_ENV=${TL_ENV}
JWT_SECRET=${JWT_SECRET_VALUE}
DATABASE_URL=postgresql://${TL_DB_USER}@localhost/${TL_DB_NAME}
SFTP_BASE=${TL_DATA_DIR}
BASE_URL=${BASE_URL}
ALLOWED_ORIGIN=${BASE_URL}
COOKIE_SECURE=true

# ── Valgfrit — udfyld hvis/når disse features skal bruges i dette miljø ─────
# GOOGLE_APPLICATION_CREDENTIALS=/etc/timelapse/gcp-service-account.json
# GOOGLE_CLOUD_LOCATION=europe-west1
# CHANGE_TICKET_GPG_KEY=<gpg-key-id>
"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [dry-run] ville skrive følgende til $ENV_FILE (secrets udeladt her):"
    echo "$ENV_CONTENT" | sed 's/JWT_SECRET=.*/JWT_SECRET=<genereret>/'
  else
    echo "$ENV_CONTENT" | sudo tee "$ENV_FILE" >/dev/null
    sudo chown root:staff "$ENV_FILE"
    sudo chmod 640 "$ENV_FILE"
  fi
  log "TIMELAPSE_ENV=${TL_ENV} sat — bemærk: koden i main.py kræver i dag en eksplicit,"
  log "≥32-tegns JWT_SECRET når TIMELAPSE_ENV=prod (raise ved opstart hvis ikke) —"
  log "det er allerede opfyldt her (openssl rand -hex 32 = 64 tegn)."
fi

# ── 6. UI-build ──────────────────────────────────────────────────────────────
log "Bygger UI (npm ci && npm run build)..."
run "cd '$TL_REPO_DIR/timelapse-ui' && npm ci && npm run build"

# ── 7. launchd — headend-service ────────────────────────────────────────────
STARTER_SCRIPT="/usr/local/sbin/timelapse-headend-start"
log "Installerer starter-script ($STARTER_SCRIPT) og launchd-plist..."

STARTER_CONTENT="#!/bin/zsh
set -euo pipefail
ENV_FILE=\"\${TIMELAPSE_HEADEND_ENV_FILE:-$ENV_FILE}\"
WORKDIR=\"\${TIMELAPSE_HEADEND_WORKDIR:-$TL_REPO_DIR/headend}\"
UVICORN=\"\${TIMELAPSE_HEADEND_UVICORN:-$VENV_DIR/bin/uvicorn}\"
export HOME=\"\${HOME:-$HOME}\"
export PATH=\"/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\${PATH:-}\"
if [[ -r \"\$ENV_FILE\" ]]; then
  set -a; source \"\$ENV_FILE\"; set +a
fi
cd \"\$WORKDIR\"
exec \"\$UVICORN\" main:app --host 127.0.0.1 --port 8000 --log-level info
"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "  [dry-run] ville skrive $STARTER_SCRIPT"
else
  echo "$STARTER_CONTENT" | sudo tee "$STARTER_SCRIPT" >/dev/null
  sudo chmod 755 "$STARTER_SCRIPT"
fi

PLIST_LABEL="dk.froekjaer.timelapse-headend"
PLIST_PATH="/Library/LaunchDaemons/${PLIST_LABEL}.plist"
PLIST_CONTENT="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key><string>${PLIST_LABEL}</string>
  <key>UserName</key><string>$(whoami)</string>
  <key>ProgramArguments</key><array><string>${STARTER_SCRIPT}</string></array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>TIMELAPSE_HEADEND_ENV_FILE</key><string>${ENV_FILE}</string>
  </dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/timelapse-headend.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/timelapse-headend.log</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
</dict>
</plist>
"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "  [dry-run] ville installere $PLIST_PATH og bootstrappe launchd"
else
  echo "$PLIST_CONTENT" | sudo tee "$PLIST_PATH" >/dev/null
  sudo launchctl bootout system "$PLIST_PATH" 2>/dev/null || true
  sudo launchctl bootstrap system "$PLIST_PATH"
  sudo launchctl kickstart -k "system/${PLIST_LABEL}"
fi

# ── 8. nginx ─────────────────────────────────────────────────────────────────
NGINX_CONF_DIR="/opt/homebrew/etc/nginx"
NGINX_CONF="$NGINX_CONF_DIR/nginx.conf"
log "Genererer nginx-config: kun backend-vhost på port ${TL_BACKEND_PORT} (marketingsite hostes separat, se §5.3)."

# Fælles fundament (rate limiting, security headers) — matcher den nuværende,
# afprøvede rd-config (deploy/nginx/timelapse.froekjaer.dk.conf).
read -r -d '' NGINX_BASE <<'NGINXEOF' || true
events { worker_connections 1024; }
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

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

NGINXEOF

# ── Certifikat-kip-i-halen-problem, LØST VIA DNS-01 (se guide §6) ───────────
# Tidligere brugte scriptet HTTP-01 (ACME-webroot på port 80) til at bevise
# domæneejerskab, hvilket krævede at nginx allerede svarede på :80 — men på
# staging/prod ejer CrushFTP port 80, så det er slet ikke en mulighed her.
# Løsningen er DNS-01 (certbot-dns-cloudflare): certbot beviser ejerskab via et
# TXT-opslag i Cloudflare-DNS'en og rører INGEN port på denne maskine overhovedet.
# Det betyder cert-udstedelse er fuldstændig uafhængig af om nginx kører — og
# derfor KAN (men behøver ikke) køres FØR første kørsel af dette script.
#
# Scriptet detekterer alligevel om certifikatet allerede findes, af to grunde:
#   1. Robusthed hvis Peter kører scriptet før certbot (fx ved første smoke-test).
#   2. Vi vil aldrig risikere at `nginx -t` fejler pga. manglende cert-filer.
# - Findes IKKE endnu → skriver kun et :${TL_BACKEND_PORT}-bootstrap-block over
#   PLAIN HTTP (ikke SSL, da der intet certifikat er) med et statussvar. Kør
#   certbot DNS-01 (guide §6, kræver INGEN åben port), og kør SÅ dette script
#   IGEN — det opdager da certifikatet og skriver det fulde SSL-block.
#   BEMÆRK: fordi ${TL_BACKEND_PORT} typisk er en ikke-standard port, er der
#   ingen browser-relevant grund til at redirecte HTTP→HTTPS på den — der er
#   ingen legitim plaintext-trafik at omdirigere her.
#   - Findes ALLEREDE → fuldt SSL-block på :${TL_BACKEND_PORT}, direkte offentligt
#     bundet (ikke 127.0.0.1 — der er intet reverse-proxy-lag foran).

_cert_exists() {
  local domain="$1"
  [[ -f "/opt/homebrew/etc/nginx/ssl/${domain}/fullchain.pem" && -f "/opt/homebrew/etc/nginx/ssl/${domain}/privkey.pem" ]]
}

if _cert_exists "$TL_DOMAIN_BACKEND"; then
  log "Certifikat fundet for ${TL_DOMAIN_BACKEND} — skriver fuldt SSL-block på :${TL_BACKEND_PORT}."
  BACKEND_BLOCK="    server {
        listen ${TL_BACKEND_PORT} ssl;
        server_name ${TL_DOMAIN_BACKEND};
        ssl_certificate     /opt/homebrew/etc/nginx/ssl/${TL_DOMAIN_BACKEND}/fullchain.pem;
        ssl_certificate_key /opt/homebrew/etc/nginx/ssl/${TL_DOMAIN_BACKEND}/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;

        root ${TL_REPO_DIR}/timelapse-ui/dist;
        index index.html;

        location / { try_files \$uri \$uri/ /index.html; }

        location ~ ^/api/auth/login {
            limit_req zone=api_login burst=5 nodelay;
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie \$http_cookie;
        }

        location /api/import/ {
            client_max_body_size 1024m;
            proxy_request_buffering off;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie \$http_cookie;
        }

        location /api/ {
            limit_req zone=api_general burst=60 nodelay;
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_pass_header Set-Cookie;
            proxy_set_header Cookie \$http_cookie;
        }
    }
"
else
  warn "Intet certifikat fundet endnu for ${TL_DOMAIN_BACKEND} — skriver kun et plain-HTTP :${TL_BACKEND_PORT}-bootstrap-block."
  warn "Kør certbot DNS-01 (guide §6 — rører INGEN port) og kør derefter dette script IGEN for at aktivere SSL."
  BACKEND_BLOCK="    server {
        listen ${TL_BACKEND_PORT};
        server_name ${TL_DOMAIN_BACKEND};
        location / { return 200 \"TimeLapse Pro: ${TL_DOMAIN_BACKEND} er oppe, men venter stadig paa TLS-certifikat (koer certbot DNS-01, se INSTALLATION_GUIDE_HEADEND_v1.md paragraf 6).\\n\"; }
    }
"
fi

FULL_NGINX_CONF="${NGINX_BASE}
${BACKEND_BLOCK}
}
"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "  [dry-run] ville skrive $NGINX_CONF (se ovenfor for indhold-skitse)"
else
  [[ -f "$NGINX_CONF" ]] && sudo cp "$NGINX_CONF" "${NGINX_CONF}.bak-$(date +%Y%m%d%H%M%S)"
  echo "$FULL_NGINX_CONF" | sudo tee "$NGINX_CONF" >/dev/null
  sudo nginx -t -c "$NGINX_CONF" || die "nginx -t fejlede — se output ovenfor, ret config før du fortsætter. En backup af den gamle config ligger ved siden af."
  if pgrep -x nginx >/dev/null 2>&1; then
    sudo nginx -s reload
    log "nginx genindlæst med den nye config."
  else
    sudo nginx
    log "nginx startet."
  fi
  if _cert_exists "$TL_DOMAIN_BACKEND"; then
    log "Certifikat fundet — nginx kører nu med fuld HTTPS på :${TL_BACKEND_PORT}."
  else
    warn "nginx kører kun med et plain-HTTP :${TL_BACKEND_PORT}-bootstrap for ${TL_DOMAIN_BACKEND}."
    warn "Kør certbot DNS-01 nu (guide §6 — rører INGEN port), og kør SÅ dette script igen for at aktivere HTTPS."
  fi
fi

# ── 9. Sundhedstjek (kun HTTP-laget, TLS/cert kommer i et senere trin) ───────
log "Venter på at headend svarer på 127.0.0.1:8000/api/health..."
if [[ "$DRY_RUN" != "1" ]]; then
  for i in $(seq 1 24); do
    if curl -fsS "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
      log "✅ Headend svarer (health OK)."
      break
    fi
    sleep 5
    [[ "$i" == "24" ]] && warn "Headend svarede stadig ikke efter 2 minutter — tjek $HOME/Library/Logs/timelapse-headend.log"
  done
fi

# ── 10. Afsluttende, MANUELLE trin (kan ikke og bør ikke scriptes) ──────────
cat <<EOF

$LOG_PREFIX ══════════════════════════════════════════════════════════════════
$LOG_PREFIX Grundinstallation færdig for miljø: $TL_ENV
$LOG_PREFIX ══════════════════════════════════════════════════════════════════

Resterende trin — SKAL gøres af dig manuelt, kan ikke og bør ikke scriptes:

  1. Certifikat (Let's Encrypt via DNS-01) for ${TL_DOMAIN_BACKEND}:
     CrushFTP ejer port 80/443 på denne maskine, så vi bruger DNS-01
     (certbot-dns-cloudflare) i stedet for HTTP-01 — det rører INGEN port
     overhovedet og kan køres uanset om nginx kører. Kræver en Cloudflare
     API-token med "Zone:DNS:Edit"-rettighed. Se
     INSTALLATION_GUIDE_HEADEND_v1.md §6 for den nøjagtige certbot-kommando.
     KØR DEREFTER DETTE SCRIPT IGEN (samme kommando) — det opdager automatisk
     at certifikatet nu findes og aktiverer SSL på :${TL_BACKEND_PORT}.

  2. FØRSTE LOGIN — kan IKKE scriptes (systemet kræver MFA-enrollment for
     super_admin ved allerførste login, jf. main.py's mfa_required_by_role):
       a. Åbn https://${TL_DOMAIN_BACKEND}:${TL_BACKEND_PORT}/ i en browser
       b. Log ind som admin / changeme
       c. Gennemfør TOTP-opsætning (scan QR-koden med en autenticator-app)
       d. Skift adgangskoden STRAKS bagefter (Indstillinger → Skift adgangskode)
     Se INSTALLATION_GUIDE_HEADEND_v1.md §7 for flere detaljer.

  3. CA/mTLS til edge-enheder er IKKE en del af dette script — koden findes
     endnu ikke (se opgave #52 i HANDOVER_LOG.md). Tilføjes i en senere runde.

  4. Yderligere brugere/roller oprettes via UI'en (Brugere-siden) af den
     nyoprettede super_admin — ikke af dette script.

  5. Marketingsitet (www.timelapse-pro.dk) er IKKE en del af dette script —
     det hostes bevidst separat fra denne maskine (CrushFTP-konflikt), se
     PORT_AUDIT_og_WEBSITE_v10.md §5.3. Login-knapperne på det site skal pege
     på https://${TL_DOMAIN_BACKEND}:${TL_BACKEND_PORT}/ (med portnummer).

$LOG_PREFIX Log: $HOME/Library/Logs/timelapse-headend.log
$LOG_PREFIX Env-fil: $ENV_FILE (IKKE i Git — backup den et sikkert sted separat)
EOF
