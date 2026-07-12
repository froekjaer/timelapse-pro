"""
TimeLapse Pro — Edge Technician UI

Local web UI for technicians to manage edge devices via QR code login.
Served on port 8099 when edge has network connectivity.
"""
from __future__ import annotations

import html
import json
import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

try:
    from technician_auth import TechnicianAuth, get_auth
except ImportError:
    # Fallback for direct execution
    from edge.technician_auth import TechnicianAuth, get_auth

log = logging.getLogger(__name__)

DEFAULT_PORT = 8099
TECH_UI_PORT = int(os.getenv("TIMELAPSE_TECH_UI_PORT", str(DEFAULT_PORT)))
EDGE_DATA_DIR = Path(os.getenv("TIMELAPSE_EDGE_DIR", "/opt/timelapse/edge"))
HEADEND_URL = os.getenv("TIMELAPSE_HEADEND_URL", "http://headend.local:8000")
DEVICE_ID = os.getenv("TIMELAPSE_DEVICE_ID", "unknown")


class TechnicianUIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for technician UI."""

    def __init__(self, *args, auth: TechnicianAuth, **kwargs):
        self.auth = auth
        self.start_time = time.time()
        super().__init__(*args, directory=EDGE_DATA_DIR, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use proper logging."""
        log.info(f"{self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)

        # Serve technician UI pages
        if parsed.path in ("/", "/index.html"):
            self.serve_technician_home()
        elif parsed.path == "/auth":
            self.serve_auth_page()
        elif parsed.path == "/api/status":
            self.serve_status_api()
        elif parsed.path == "/api/quality":
            self.serve_quality_api()
        elif parsed.path.startswith("/static/"):
            # Serve static files from edge directory
            super().do_GET()
        else:
            self.send_error(404, "Not found")

    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed = urlparse(self.path)

        if parsed.path == "/api/auth/start":
            self.handle_auth_start()
        elif parsed.path == "/api/auth/poll":
            self.handle_auth_poll()
        else:
            self.send_error(404, "Not found")

    def serve_technician_home(self) -> None:
        """Serve technician home page."""
        session = self.get_active_session()

        if session and session.get("status") == "confirmed":
            self.serve_dashboard(session)
        else:
            self.serve_login_page()

    def serve_login_page(self) -> None:
        """Serve QR code login page."""
        # Create auth session
        auth_session = self.auth.create_auth_session(ttl_minutes=15)
        qr_data_uri, auth_url = self.auth.generate_qr_code(auth_session)

        html = self.generate_login_html(qr_data_uri, auth_url, auth_session)
        self.send_html(html)

    def serve_auth_page(self) -> None:
        """Serve auth redirect page."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authenticating...</title>
            <meta http-equiv="refresh" content="0;url=/">
        </head>
        <body>
            <p>Redirecting to login...</p>
        </body>
        </html>
        """
        self.send_html(html)

    def serve_dashboard(self, session: dict) -> None:
        """Serve technician dashboard after successful login."""
        html = self.generate_dashboard_html(session)
        self.send_html(html)

    def serve_status_api(self) -> None:
        """Serve edge status as JSON."""
        status = self.get_edge_status()
        self.send_json(status)

    def serve_quality_api(self) -> None:
        """Serve latest autonomous optimizer data as JSON."""
        quality_data = self.get_latest_quality_data()
        self.send_json(quality_data)

    def handle_auth_start(self) -> None:
        """Handle auth start request."""
        session = self.auth.create_auth_session(ttl_minutes=15)
        qr_data_uri, auth_url = self.auth.generate_qr_code(session)

        self.send_json({
            "session_id": session.session_id,
            "expires_at": session.expires_at,
            "qr_code": qr_data_uri,
            "auth_url": auth_url,
        })

    def handle_auth_poll(self) -> None:
        """Handle auth poll request."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode("utf-8"))

        session_id = data.get("session_id")
        session = self.auth.get_active_session(session_id)

        if session and session.status == "confirmed":
            self.send_json({
                "status": "confirmed",
                "technician_username": session.technician_username,
                "technician_user_id": session.technician_user_id,
            })
        else:
            self.send_json({"status": "pending"})

    def get_active_session(self) -> Optional[dict]:
        """Get current active technician session."""
        # Try to get from cookie
        cookie_header = self.headers.get("Cookie", "")
        session_id = None

        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("tech_session="):
                session_id = part.split("=", 1)[1]
                break

        if session_id:
            session = self.auth.get_active_session(session_id)
            if session and session.status == "confirmed":
                return {
                    "id": session.session_id,
                    "username": session.technician_username,
                    "user_id": session.technician_user_id,
                }

        return None

    def get_edge_status(self) -> dict:
        """Get current edge status."""
        try:
            # Try to read status from agent
            status_file = EDGE_DATA_DIR / "status.json"
            if status_file.exists():
                with open(status_file) as f:
                    return json.load(f)
        except Exception as e:
            log.debug("Could not read status file: %s", e)

        # Fallback status
        return {
            "device_id": DEVICE_ID,
            "status": "unknown",
            "uptime_seconds": time.time() - self.start_time,
            "last_capture": None,
        }

    def get_latest_quality_data(self) -> dict:
        """Get latest autonomous optimizer data from captures."""
        import os
        try:
            # Find latest sidecar file
            captures_dir = EDGE_DATA_DIR / "captures"
            if not captures_dir.exists():
                return {"error": "captures directory not found"}

            # Find latest JSON sidecar
            sidecars = sorted(
                captures_dir.glob("**/*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            if not sidecars:
                return {"error": "no sidecar files found"}

            latest_sidecar = sidecars[0]
            with open(latest_sidecar) as f:
                sidecar_data = json.load(f)

            # Extract autonomous optimizer data
            ai_analysis = sidecar_data.get("ai_analysis", {})
            autonomous = ai_analysis.get("autonomous_optimizer")
            site_look = ai_analysis.get("site_look_matching") or autonomous.get("site_look_matching") if autonomous else None

            if not autonomous:
                return {"error": "no autonomous optimizer data in sidecar"}

            return {
                "filename": latest_sidecar.stem + ".jpg",
                "timestamp": latest_sidecar.stat().st_mtime,
                "autonomous_optimizer": autonomous,
                "site_look_matching": site_look,
            }
        except Exception as e:
            log.debug("Could not read latest quality data: %s", e)
            return {"error": str(e)}

    def send_html(self, html: str, status_code: int = 200) -> None:
        """Send HTML response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def send_json(self, data: dict, status_code: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def generate_login_html(self, qr_data_uri: str, auth_url: str, session: Any) -> str:
        """Generate login page HTML with QR code."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TimeLapse Pro - Edge Technician Login</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * {{ box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0;
                    padding: 20px;
                }}
                .card {{
                    background: white;
                    border-radius: 16px;
                    padding: 40px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 400px;
                }}
                h1 {{ color: #333; margin-bottom: 10px; font-size: 24px; }}
                p {{ color: #666; margin-bottom: 30px; }}
                .qr-container {{
                    background: #f5f5f5;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .qr-code {{
                    width: 200px;
                    height: 200px;
                    margin: 0 auto;
                }}
                .device-id {{
                    font-family: monospace;
                    background: #f0f0f0;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    word-break: break-all;
                }}
                .status {{
                    margin-top: 20px;
                    padding: 12px;
                    border-radius: 8px;
                    font-size: 14px;
                }}
                .status.waiting {{ background: #fff3cd; color: #856404; }}
                .status.success {{ background: #d4edda; color: #155724; }}
                .loading {{ animation: pulse 2s infinite; }}
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🔧 Technician Login</h1>
                <p>Scan QR koden for at logge ind</p>

                <div class="qr-container">
                    <img src="{qr_data_uri}" alt="Scan QR Code" class="qr-code">
                </div>

                <div class="device-id">{DEVICE_ID}</div>

                <div class="status waiting loading">
                    ⏳ Venter på login via QR kode...
                </div>
            </div>

            <script>
            const sessionId = '{html.escape(session.session_id)}';
            let pollCount = 0;
            const maxPolls = 180; // 15 minutes

            function pollAuth() {{
                if (pollCount >= maxPolls) {{
                    document.querySelector('.status').textContent = '⏱ Login timeout - prøv igen';
                    return;
                }}

                fetch('/api/auth/poll', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ session_id: sessionId }})
                }})
                .then(r => r.json())
                .then(data => {{
                    pollCount++;
                    if (data.status === 'confirmed') {{
                        document.querySelector('.status').className = 'status success';
                        document.querySelector('.status').textContent = '✅ Login OK! Redirecting...';
                        setTimeout(() => window.location.reload(), 1000);
                    }} else {{
                        setTimeout(pollAuth, 2000);
                    }}
                }})
                .catch(err => {{
                    console.error('Poll error:', err);
                    setTimeout(pollAuth, 2000);
                }});
            }}

            pollAuth();
            </script>
        </body>
        </html>
        """

    def generate_dashboard_html(self, session: dict) -> str:
        """Generate technician dashboard HTML."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TimeLapse Pro - Edge Technician</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * {{ box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .card {{
                    background: white;
                    padding: 24px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                h1 {{ margin: 0; font-size: 20px; }}
                h2 {{ margin-top: 0; font-size: 18px; }}
                .btn {{
                    background: #0284c7;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 4px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                }}
                .btn:hover {{ background: #026aa7; }}
                .btn.logout {{ background: #dc3545; }}
                .btn.logout:hover {{ background: #c82333; }}
                .status-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 16px;
                }}
                .status-item {{
                    background: #f8f9fa;
                    padding: 16px;
                    border-radius: 4px;
                }}
                .status-item .label {{
                    font-size: 12px;
                    color: #666;
                    margin-bottom: 4px;
                }}
                .status-item .value {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #333;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔧 Edge Technician</h1>
                    <div>
                        <span style="margin-right: 16px; color: #666;">
                            {html.escape(session.get('username', 'Unknown'))}
                        </span>
                        <button class="btn logout" onclick="logout()">Log ud</button>
                    </div>
                </div>

                <div class="card">
                    <h2>Enheds Status</h2>
                    <div class="status-grid">
                        <div class="status-item">
                            <div class="label">Enheds ID</div>
                            <div class="value">{html.escape(DEVICE_ID)}</div>
                        </div>
                        <div class="status-item">
                            <div class="label">Headend</div>
                            <div class="value">{html.escape(HEADEND_URL)}</div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h2>Fototekniske Anbefalinger</h2>
                    <div id="quality-panel">Indlæser...</div>
                </div>

                <div class="card">
                    <h2>Konfiguration</h2>
                    <p>Tekniker menu - kom snart</p>
                </div>
            </div>

            <script>
            function logout() {{
                document.cookie = 'tech_session=; path=/; max-age=0';
                window.location.reload();
            }}

            // Load quality data
            async function loadQualityData() {{
                try {{
                    const response = await fetch('/api/quality');
                    const data = await response.json();
                    renderQualityData(data);
                }} catch (err) {{
                    console.error('Failed to load quality data:', err);
                    document.getElementById('quality-panel').innerHTML = '<p class="text-gray-500">Kunne ikke hente data</p>';
                }}
            }}

            function renderQualityData(data) {{
                const panel = document.getElementById('quality-panel');
                if (data.error) {{
                    panel.innerHTML = `<p class="text-gray-500">${{data.error}}</p>`;
                    return;
                }}

                const opt = data.autonomous_optimizer;
                if (!opt) {{
                    panel.innerHTML = '<p class="text-gray-500">Ingen optimerer data</p>';
                    return;
                }}

                // Score
                const score = opt.score || {{}};
                let scoreHtml = '';
                if (score.overall !== undefined) {{
                    const grade = score.grade || 'unknown';
                    const gradeEmoji = {{
                        excellent: '🌟',
                        good: '👍',
                        usable: '⚠️',
                        needs_attention: '🔴'
                    }}[grade] || '📊';
                    scoreHtml = `
                        <div class="mb-3">
                            <div class="flex items-center gap-2">
                                <span class="text-2xl">${{gradeEmoji}}</span>
                                <div>
                                    <div class="font-semibold">${{grade.charAt(0).toUpperCase() + grade.slice(1)}} kvalitet</div>
                                    <div class="text-2xl font-bold">${{score.overall.toFixed(1)}}%</div>
                                </div>
                            </div>
                        </div>
                    `;
                }}

                // Control plan
                const control = opt.control_plan || {{}};
                let controlHtml = '';
                if (control.next_capture_ev_delta !== undefined) {{
                    const ev = control.next_capture_ev_delta;
                    const evText = ev === 0 ? '0' : (ev > 0 ? `+${{ev.toFixed(1)}}` : ev.toFixed(1));
                    controlHtml = `
                        <div class="mb-3">
                            <div class="font-semibold text-sm mb-2">Kontrolplan</div>
                            <div class="text-sm space-y-1">
                                <div class="flex justify-between">
                                    <span>Næste EV:</span>
                                    <span class="font-semibold ${{-ev !== 0 ? 'text-sky-600' : 'text-gray-400'}}">${{evText}} EV</span>
                                </div>
                                ${{-control.autonomous_safe_to_apply ? '<div class="text-xs text-amber-600">Kræver manuel godkendelse</div>' : ''}}
                            </div>
                        </div>
                    `;
                }}

                // Recommendations
                const recs = opt.recommendations || [];
                let recsHtml = '';
                if (recs.length > 0) {{
                    recsHtml = '<div class="space-y-2">';
                    recs.slice(0, 5).forEach(rec => {{
                        const kindIcons = {{
                            exposure: '💡',
                            white_balance: '✨',
                            focus: '⚙️',
                            depth_of_field: '⚙️',
                            schedule: '⚠️',
                            maintenance: '🔧'
                        }};
                        const icon = kindIcons[rec.kind] || '💡';
                        const confidence = Math.round(rec.confidence * 100);
                        recsHtml += `
                            <div class="p-2 border rounded hover:bg-gray-50">
                                <div class="flex items-start justify-between gap-2">
                                    <div class="flex items-start gap-2 flex-1">
                                        <span class="text-xl">${{icon}}</span>
                                        <div>
                                            <div class="font-medium text-sm">${{rec.action}}</div>
                                            <div class="text-xs text-gray-600">${{rec.reason}}</div>
                                        </div>
                                    </div>
                                    <div class="text-xs font-semibold ${{-confidence >= 70 ? 'text-sky-600' : 'text-gray-500'}}">${{confidence}}%</div>
                                </div>
                            </div>
                        `;
                    }});
                    recsHtml += '</div>';
                }}

                panel.innerHTML = scoreHtml + controlHtml + recsHtml;
            }}

            // Load quality data on page load
            loadQualityData();
            </script>
        </body>
        </html>
        """


def find_available_port(start_port: int = DEFAULT_PORT) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return DEFAULT_PORT


def serve_technician_ui(
    auth: TechnicianAuth,
    port: int = TECH_UI_PORT,
    daemon: bool = True,
) -> Optional[HTTPServer]:
    """
    Start technician UI HTTP server.

    Args:
        auth: TechnicianAuth instance
        port: Port to serve on
        daemon: Run as daemon thread

    Returns:
        HTTPServer if started, None if port unavailable
    """
    # Find available port
    available_port = find_available_port(port)

    def handler(*args, **kwargs):
        return TechnicianUIHandler(*args, auth=auth, **kwargs)

    try:
        server = HTTPServer(("0.0.0.0", available_port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=daemon)
        thread.start()

        log.info("Technician UI started: http://0.0.0.0:%d", available_port)
        return server

    except OSError as e:
        log.error("Failed to start technician UI: %s", e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize auth
    db_path = EDGE_DATA_DIR / "technician_auth.db"
    auth = TechnicianAuth(db_path, DEVICE_ID, HEADEND_URL)

    # Start server
    serve_technician_ui(auth)
    log.info("Technician UI running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down technician UI")
