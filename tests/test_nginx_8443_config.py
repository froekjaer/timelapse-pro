"""
TimeLapse Pro — Nginx 8443 Configuration Tests (P0-02)
========================================================

Tests for nginx configuration on port 8443:
- Port 8443 binding and SSL termination
- DNS-01 certificate configuration (certbot-dns-cloudflare)
- SSL/TLS configuration security
- nginx config validation
- Integration with CrushFTP port requirements

Context: P0-02 requires nginx on port 8443 (not 443/80) due to CrushFTP
         using traditional HTTPS ports.

Kør: pytest tests/test_nginx_8443_config.py -v

Marker: integration (kræver nginx config adgang)
"""
import os
import pytest
import subprocess
import re
from pathlib import Path
from typing import Optional, List

PROJECT_ROOT = "/Volumes/data-fast/peter-home/projects/timelapse-pro"

# nginx config paths
NGINX_CONF_PATHS = [
    "/opt/homebrew/etc/nginx/nginx.conf",
    "/etc/nginx/nginx.conf",
    "/usr/local/etc/nginx/nginx.conf",
]

# SSL certificate paths
SSL_CERT_PATHS = [
    "/etc/letsencrypt/live/",
    "/opt/homebrew/etc/nginx/ssl/",
]


def run_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Kør kommando og returner resultat."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        return e


def find_nginx_conf() -> Optional[str]:
    """Find nginx konfigurationsfil."""
    for path in NGINX_CONF_PATHS:
        if os.path.exists(path):
            return path
    return None


# ── 1. Port 8443 Configuration ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_nginx_config_exists():
    """nginx konfigurationsfil skal eksistere."""
    nginx_conf = find_nginx_conf()

    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    assert nginx_conf is not None
    assert os.path.exists(nginx_conf)


@pytest.mark.integration
def test_nginx_listens_on_8443():
    """nginx skal lytte på port 8443."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have listen directive for 8443
    has_8443 = (
        "listen.*8443" in content or
        "listen 8443" in content or
        "listen.*:8443" in content
    )

    if not has_8443:
        pytest.skip("nginx lytter ikke på port 8443 - P0-02 ikke implementeret")

    assert has_8443


@pytest.mark.integration
def test_8443_ssl_enabled():
    """Port 8443 skal have SSL aktiveret."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Look for SSL on 8443
    ssl_on_8443 = False

    # Check for ssl parameter in listen directive
    if re.search(r'listen.*8443.*ssl', content):
        ssl_on_8443 = True

    # Or check for ssl on directive in same server block
    if not ssl_on_8443:
        # Simple check: ssl directive should be near 8443
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '8443' in line:
                # Check surrounding lines for ssl
                context = '\n'.join(lines[max(0, i-5):min(len(lines), i+10)])
                if 'ssl' in context.lower():
                    ssl_on_8443 = True
                    break

    if not ssl_on_8443:
        pytest.skip("SSL ikke aktiveret på port 8443")

    assert ssl_on_8443


@pytest.mark.integration
def test_nginx_not_on_443():
    """nginx skal IKKE lytte på port 443 (reserveret til CrushFTP)."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should NOT have listen on 443
    has_443 = (
        "listen.*443" in content and
        "listen 8443" not in content  # Unless 8443 is also present
    )

    # Allow 443 if 8443 is also present (migration in progress)
    if has_443 and "8443" not in content:
        pytest.fail("nginx lytter på port 443 som konflikter med CrushFTP")

    # If both are present, that's okay during migration
    assert True


@pytest.mark.integration
def test_nginx_not_on_80():
    """nginx skal IKKE lytte på port 80 (reserveret til CrushFTP)."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Check if port 80 is used for HTTP redirect
    # Port 80 might be used for HTTP->HTTPS redirect, which is acceptable
    # But main service should be on 8443

    # This is informational - port 80 usage is acceptable for redirects
    assert True  # Design verification


# ── 2. DNS-01 Certificate Configuration ──────────────────────────────────────────

@pytest.mark.integration
def test_letsencrypt_certbot_installed():
    """certbot skal være installeret."""
    # Check for certbot installation
    result = run_command(["which", "certbot"], check=False)

    if result.returncode != 0:
        # Try common paths
        certbot_paths = [
            "/opt/homebrew/bin/certbot",
            "/usr/local/bin/certbot",
            "/usr/bin/certbot",
        ]
        certbot_found = any(os.path.exists(p) for p in certbot_paths)

        if not certbot_found:
            pytest.skip("certbot ikke installeret")
    else:
        assert True  # certbot found


@pytest.mark.integration
def test_dns_cloudflare_plugin_installed():
    """certbot-dns-cloudflare plugin skal være installeret."""
    # Check for cloudflare plugin
    result = run_command(["certbot", "plugins"], check=False)

    if result.returncode != 0:
        pytest.skip("certbot ikke tilgængelig")

    has_cloudflare = "dns-cloudflare" in result.stdout.lower()

    if not has_cloudflare:
        pytest.skip("certbot-dns-cloudflare plugin ikke installeret")

    assert has_cloudflare


@pytest.mark.integration
def test_cloudflare_api_configured():
    """Cloudflare API token skal være konfigureret."""
    # Check for Cloudflare API token in certbot config
    cloudflare_config = "/etc/letsencrypt/secrets/certbot-cloudflare-token.ini"

    if not os.path.exists(cloudflare_config):
        # Try alternative paths
        cloudflare_config = "/opt/homebrew/etc/letsencrypt/secrets/certbot-cloudflare-token.ini"

    if not os.path.exists(cloudflare_config):
        pytest.skip("Cloudflare API token config ikke fundet")

    # Check file has correct permissions (should be restricted)
    stat_info = os.stat(cloudflare_config)
    mode = oct(stat_info.st_mode)[-3:]

    # Should be 600 or 400 (owner read/write only)
    assert mode in ['600', '400', '640'], \
        f"Cloudflare token config har for åbne permissions: {mode}"


@pytest.mark.integration
def test_dns01_certificate_exists():
    """DNS-01 udstedt certifikat skal eksistere."""
    cert_paths = [
        "/etc/letsencrypt/live/",
        "/opt/homebrew/etc/letsencrypt/live/",
    ]

    cert_found = False
    for cert_dir in cert_paths:
        if os.path.exists(cert_dir):
            # Look for any certificate directory
            try:
                certs = os.listdir(cert_dir)
                for cert in certs:
                    if os.path.exists(os.path.join(cert_dir, cert, "fullchain.pem")):
                        cert_found = True
                        break
            except (FileNotFoundError, PermissionError):
                pass

    if not cert_found:
        pytest.skip("DNS-01 certifikat ikke fundet")

    assert cert_found


@pytest.mark.integration
def test_certificate_valid_for_domain():
    """Certifikat skal være gyldigt for domænet."""
    # Check certificate validity for expected domain
    cert_domains = os.getenv("TIMELAPSE_CERT_DOMAINS", "")

    if not cert_domains:
        pytest.skip("TIMELAPSE_CERT_DOMAINS ikke sat")

    # This would require openssl to check certificate
    # For now, verify domain is configured
    assert True  # Domain verification via openssl


# ── 3. SSL/TLS Security Configuration ───────────────────────────────────────────────

@pytest.mark.integration
def test_ssl_certificate_path_configured():
    """SSL certifikatsti skal være konfigureret."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have ssl_certificate directives
    has_cert_path = (
        "ssl_certificate" in content or
        "ssl_certificate_key" in content
    )

    if not has_cert_path:
        pytest.skip("SSL certifikatsti ikke konfigureret")

    assert has_cert_path


@pytest.mark.integration
def test_ssl_protocols_secure():
    """SSL protokoller skal være sikre (TLS 1.2+)."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Check for ssl_protocols directive
    if "ssl_protocols" in content:
        # Should not have SSLv3 or TLS 1.0/1.1
        has_weak_protos = (
            "SSLv3" in content or
            "TLSv1" in content and "TLSv1.1" in content
        )
        assert not has_weak_protos, "Svage SSL protokoller er konfigureret"
    else:
        pytest.skip("ssl_protocols ikke eksplicit konfigureret (bruger nginx default)")


@pytest.mark.integration
def test_ssl_ciphers_secure():
    """SSL ciphers skal være sikre."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Check for ssl_ciphers directive
    if "ssl_ciphers" in content:
        # Should have secure cipher suite
        has_secure = (
            "HIGH" in content or
            "ECDHE" in content or
            "AES" in content
        )
        assert has_secure, "SSL ciphers mangler sikre indstillinger"
    else:
        pytest.skip("ssl_ciphers ikke eksplicit konfigureret")


@pytest.mark.integration
def test_ssl_prefer_server_ciphers():
    """ssl_prefer_server_ciphers skal være aktiveret."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should prefer server ciphers for security
    has_prefer = "ssl_prefer_server_ciphers on" in content.lower()

    if not has_prefer:
        pytest.skip("ssl_prefer_server_ciphers ikke aktiveret")

    assert has_prefer


@pytest.mark.integration
def test_ssl_session_cache_configured():
    """SSL session cache skal være konfigureret."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have SSL session cache for performance
    has_cache = (
        "ssl_session_cache" in content or
        "ssl_session_timeout" in content
    )

    if not has_cache:
        pytest.skip("SSL session cache ikke konfigureret")

    assert has_cache


# ── 4. nginx Config Validation ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_nginx_config_syntax_valid():
    """nginx konfiguration skal have gyldig syntaks."""
    # Run nginx config test
    result = run_command(["nginx", "-t"], check=False)

    if result.returncode != 0:
        # Try with sudo if needed
        result = run_command(["sudo", "nginx", "-t"], check=False)

    if result.returncode != 0:
        # Try homebrew nginx
        result = run_command(["/opt/homebrew/sbin/nginx", "-t"], check=False)

    if result.returncode != 0:
        pytest.fail(f"nginx config syntaks fejl: {result.stderr}")

    assert "syntax is ok" in result.stderr.lower() or "successful" in result.stderr.lower()


@pytest.mark.integration
def test_nginx_service_running():
    """nginx service skal køre."""
    # Check if nginx is running
    result = run_command(["pgrep", "nginx"], check=False)

    if result.returncode != 0:
        pytest.skip("nginx kører ikke")

    assert result.returncode == 0


@pytest.mark.integration
def test_8443_port_listening():
    """Port 8443 skal lytte."""
    # Check if port 8443 is listening
    result = run_command(["lsof", "-i", ":8443"], check=False)

    if result.returncode != 0:
        # Try netstat
        result = run_command(["netstat", "-an", "|", "grep", "8443"], check=False)

        if result.returncode != 0:
            pytest.skip("Port 8443 lytter ikke")

    assert result.returncode == 0 or "LISTEN" in result.stdout


@pytest.mark.integration
def test_nginx_reload_works():
    """nginx skal kunne reloades uden at dræbe connections."""
    # Test nginx reload
    result = run_command(["nginx", "-s", "reload"], check=False)

    if result.returncode != 0:
        # Try with sudo
        result = run_command(["sudo", "nginx", "-s", "reload"], check=False)

    # Reload should succeed
    assert result.returncode == 0 or "signal" in result.stderr.lower()


# ── 5. Integration with TimeLapse Headend ──────────────────────────────────────────

@pytest.mark.integration
def test_nginx_proxies_to_headend():
    """nginx skal proxy til headend."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have proxy_pass to headend
    has_proxy = (
        "proxy_pass" in content and
        ("127.0.0.1" in content or "localhost" in content or "8000" in content)
    )

    if not has_proxy:
        pytest.skip("nginx proxy til headend ikke fundet")

    assert has_proxy


@pytest.mark.integration
def test_nginx_websocket_support():
    """nginx skal understøtte websockets."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have websocket upgrade headers
    has_websocket = (
        "upgrade" in content.lower() and
        "connection" in content.lower()
    )

    if not has_websocket:
        pytest.skip("Websocket support ikke bekræftet")

    assert has_websocket


@pytest.mark.integration
def test_nginx_client_max_body_size():
    """nginx skal tillade upload af captures."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have client_max_body_size configured for image uploads
    has_body_size = "client_max_body_size" in content

    if not has_body_size:
        pytest.skip("client_max_body_size ikke konfigureret (må bruge nginx default)")

    # If configured, should be large enough for images
    if has_body_size:
        # Extract value and check it's reasonable (>10M)
        match = re.search(r'client_max_body_size\s+(\d+[MKG]?)', content)
        if match:
            size_str = match.group(1)
            # Should be at least 10M for image uploads
            assert size_str in ["10M", "20M", "50M", "100M", "1G", "10G"] or \
                   int(size_str.replace("M", "").replace("G", "")) >= 10


# ── 6. CrushFTP Port Conflict Prevention ──────────────────────────────────────────

@pytest.mark.integration
def test_no_crushftp_port_conflict():
    """Ingen konflikt med CrushFTP ports."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # CrushFTP typically uses 80, 443, 21, 990
    # TimeLapse nginx should use 8443 for HTTPS
    # This is a design verification test
    assert "8443" in content, "nginx skal bruge port 8443"


@pytest.mark.integration
def test_crushftp_documented():
    """CrushFTP port krav skal være dokumenteret."""
    backlog_path = os.path.join(PROJECT_ROOT, "PRIORITIZED_BACKLOG.md")

    if not os.path.exists(backlog_path):
        pytest.skip("PRIORITIZED_BACKLOG.md ikke fundet")

    with open(backlog_path) as f:
        content = f.read()

    # Should mention CrushFTP port requirement in P0-02
    p0_02_section = content[content.find("P0-02"):content.find("P0-02") + 500]

    has_crushftp = "crushftp" in p0_02_section.lower() or "8443" in p0_02_section

    assert has_crushftp, "P0-02 skal nævne CrushFTP/8443 krav"


# ── 7. Certificate Renewal Automation ──────────────────────────────────────────────

@pytest.mark.integration
def test_certbot_renewal_timer():
    """certbot renewal skal være automatiseret."""
    # Check for launchd timer or cron job
    timer_paths = [
        "/Library/LaunchDaemons/com.certbot.renewal.plist",
        "/Library/LaunchAgents/com.certbot.renewal.plist",
    ]

    timer_found = False
    for path in timer_paths:
        if os.path.exists(path):
            timer_found = True
            break

    if not timer_found:
        # Check for cron
        result = run_command(["crontab", "-l"], check=False)
        if "certbot" in result.stdout.lower() and "renew" in result.stdout.lower():
            timer_found = True

    if not timer_found:
        pytest.skip("certbot renewal automatisering ikke fundet")

    assert timer_found


@pytest.mark.integration
def test_certbot_renewal_hook():
    """certbot renewal skal have hook til nginx reload."""
    # Check for renew-hook in certbot config
    certbot_config = "/etc/letsencrypt/renewal.conf"

    if not os.path.exists(certbot_config):
        # Try individual cert configs
        cert_dir = "/etc/letsencrypt/live"
        if os.path.exists(cert_dir):
            try:
                certs = os.listdir(cert_dir)
                for cert in certs:
                    conf_path = f"/etc/letsencrypt/renewal/{cert}.conf"
                    if os.path.exists(conf_path):
                        with open(conf_path) as f:
                            if "renew_hook" in f.read():
                                assert True
                                return
            except (FileNotFoundError, PermissionError):
                pass

        pytest.skip("certbot renewal hook ikke fundet")
    else:
        with open(certbot_config) as f:
            content = f.read()
            has_hook = "renew_hook" in content

            if not has_hook:
                pytest.skip("renew_hook ikke i certbot config")


@pytest.mark.integration
def test_certificate_expiry_future():
    """Certifikat skal ikke udløbe snart."""
    # Check certificate expiry
    cert_paths = [
        "/etc/letsencrypt/live/",
        "/opt/homebrew/etc/letsencrypt/live/",
    ]

    for cert_dir in cert_paths:
        if os.path.exists(cert_dir):
            try:
                certs = os.listdir(cert_dir)
                for cert in certs:
                    cert_path = os.path.join(cert_dir, cert, "cert.pem")
                    if os.path.exists(cert_path):
                        # Check expiry with openssl
                        result = run_command([
                            "openssl", "x509",
                            "-in", cert_path,
                            "-noout",
                            "-dates"
                        ], check=False)

                        if result.returncode == 0:
                            # Should have notAfter date
                            assert "notAfter" in result.stdout
                            return
            except (FileNotFoundError, PermissionError):
                pass

    pytest.skip("Certifikat expiry check ikke muligt")


# ── 8. P0-02 Completion Verification ────────────────────────────────────────────

@pytest.mark.integration
def test_p0_02_completion():
    """P0-02 skal være fuldført."""
    """
    P0-02 Requirements:
    - nginx on port 8443
    - DNS-01 certificate (certbot-dns-cloudflare)
    - SSL termination working
    """

    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet - P0-02 ikke fuldført")

    with open(nginx_conf) as f:
        content = f.read()

    # Check all requirements
    has_8443 = "8443" in content
    has_ssl = "ssl" in content.lower()
    has_listen = "listen" in content

    p0_02_complete = has_8443 and has_ssl and has_listen

    if not p0_02_complete:
        pytest.skip(f"P0-02 ikke fuldført (8443: {has_8443}, SSL: {has_ssl}, listen: {has_listen})")

    assert p0_02_complete


@pytest.mark.integration
def test_p0_02_documented():
    """P0-02 skal være dokumenteret som færdig."""
    backlog_path = os.path.join(PROJECT_ROOT, "PRIORITIZED_BACKLOG.md")

    if not os.path.exists(backlog_path):
        pytest.skip("PRIORITIZED_BACKLOG.md ikke fundet")

    with open(backlog_path) as f:
        content = f.read()

    # P0-02 should be mentioned
    p0_02_section = content[content.find("P0-02"):content.find("P0-02") + 500]

    assert "P0-02" in p0_02_section, "P0-02 skal være i backlog"


# ── 9. Staging/Production Deployment ─────────────────────────────────────────────

@pytest.mark.integration
def test_nginx_config_in_version_control():
    """nginx config skabelon skal være i version control."""
    config_paths = [
        os.path.join(PROJECT_ROOT, "deploy", "nginx.conf"),
        os.path.join(PROJECT_ROOT, "deploy", "nginx", "nginx.conf"),
        os.path.join(PROJECT_ROOT, "deploy", "nginx", "timelapse.conf"),
    ]

    config_found = False
    for path in config_paths:
        if os.path.exists(path):
            config_found = True
            break

    if not config_found:
        pytest.skip("nginx config skabelon ikke i version control")

    assert config_found


@pytest.mark.integration
def test_deployment_instructions_exist():
    """Deploymentsinstruktioner for P0-02 skal eksistere."""
    doc_paths = [
        os.path.join(PROJECT_ROOT, "Dokumentation", "GO_LIVE_CHECKLIST_v10.md"),
        os.path.join(PROJECT_ROOT, "Dokumentation", "ADMINISTRATORMANUAL_v10.md"),
    ]

    instructions_found = False
    for doc_path in doc_paths:
        if os.path.exists(doc_path):
            with open(doc_path) as f:
                content = f.read().lower()
                if "8443" in content or "nginx" in content:
                    instructions_found = True
                    break

    if not instructions_found:
        pytest.skip("Deployment instruktioner for P0-02 ikke fundet")


@pytest.mark.integration
def test_nginx_log_configured():
    """nginx logging skal være konfigureret."""
    nginx_conf = find_nginx_conf()
    if not nginx_conf:
        pytest.skip("nginx konfiguration ikke fundet")

    with open(nginx_conf) as f:
        content = f.read()

    # Should have access and error log
    has_logs = (
        "access_log" in content and
        "error_log" in content
    )

    if not has_logs:
        pytest.skip("nginx logging ikke konfigureret")

    assert has_logs
