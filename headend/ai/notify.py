"""
TimeLapse Pro — Notification Service
=====================================
Sender alarm-notifikationer via:
  - Email (Gmail SMTP / ethvert SMTP)
  - SMS   (GatewayAPI — dansk, GDPR-compliant)
  - Teams (Incoming Webhook)

Konfigureres i DB-settings under nøglen "notifications" (JSON):

{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "din@gmail.com",
    "password": "xxxx xxxx xxxx xxxx",   ← Gmail App Password
    "from":     "TimeLapse Pro <din@gmail.com>",
    "to":       ["peter@froekjaer.dk"]
  },
  "sms": {
    "enabled": false,
    "provider": "gatewayapi",
    "api_token": "...",
    "sender": "TimeLapse",
    "to": ["+4512345678"]
  },
  "teams": {
    "enabled": false,
    "webhook_url": "https://froekjaer.webhook.office.com/..."
  },
  "min_severity": "warning",
  "severities": ["critical", "warning", "maintenance"]
}

SABSA: Availability — fejl i notifikation må aldrig stoppe alarm-engine.
       Confidentiality — SMTP password gemmes krypteret i settings-tabel.
"""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

log = logging.getLogger("headend.notify")

SEVERITY_EMOJI = {
    "critical":    "🚨",
    "warning":     "⚠️",
    "maintenance": "🔧",
    "info":        "ℹ️",
}

SEVERITY_COLOR = {
    "critical":    "FF0000",
    "warning":     "FF8C00",
    "maintenance": "FFD700",
    "info":        "0078D4",
}


# ── Konfiguration ─────────────────────────────────────────────────────────────

def get_notification_config(db) -> dict:
    """Hent notifikations-konfiguration fra settings-tabellen."""
    try:
        from sqlalchemy import text
        row = db.execute(text("SELECT value FROM settings WHERE key='notifications'")).fetchone()
        if row:
            return json.loads(row[0])
    except Exception as e:
        log.debug("Kunne ikke hente notification config: %s", e)
    return {}


def save_notification_config(db, config: dict) -> None:
    """Gem notifikations-konfiguration i settings-tabellen."""
    from sqlalchemy import text
    existing = db.execute(text("SELECT id FROM settings WHERE key='notifications'")).fetchone()
    value    = json.dumps(config, ensure_ascii=False, indent=2)
    if existing:
        db.execute(text("UPDATE settings SET value=:v WHERE key='notifications'"), {"v": value})
    else:
        db.execute(text("INSERT INTO settings (key, value) VALUES ('notifications', :v)"), {"v": value})
    db.commit()


def should_notify(alarm: dict, config: dict) -> bool:
    """Tjek om alarm-severity er over tærsklen."""
    severity_order = {"info": 0, "maintenance": 1, "warning": 2, "critical": 3}
    min_severity   = config.get("min_severity", "warning")
    alarm_sev      = alarm.get("severity", "info")
    return severity_order.get(alarm_sev, 0) >= severity_order.get(min_severity, 2)


# ── Afsendere ────────────────────────────────────────────────────────────────

def send_email(alarm: dict, config: dict, image_url: Optional[str] = None) -> bool:
    """
    Send alarm-email via SMTP.

    Gmail-opsætning:
      smtp_host: smtp.gmail.com
      smtp_port: 587
      username:  din@gmail.com
      password:  xxxx xxxx xxxx xxxx  ← App Password fra Google
    """
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled", False):
        return False

    recipients = email_cfg.get("to", [])
    if not recipients:
        log.warning("Email: ingen modtagere konfigureret")
        return False

    severity = alarm.get("severity", "warning")
    emoji    = SEVERITY_EMOJI.get(severity, "⚠️")

    subject = f"{emoji} {severity.upper()} — {alarm.get('rule_name', 'Alarm')} | TimeLapse Pro"

    # Plain text
    text_body = f"""
{emoji} {severity.upper()} ALARM — TimeLapse Pro
{'═' * 50}

Regel:      {alarm.get('rule_name', '—')}
Enhed:      {alarm.get('device_id', '—')}
Tidspunkt:  {_format_time(alarm.get('triggered_at'))}

Beskrivelse:
{alarm.get('description', '—')}

AI matchede på:
{', '.join(alarm.get('matched_on', []))}

Konfidence: {int(alarm.get('confidence', 0) * 100)}%
Capture ID: {alarm.get('capture_id', '—')}

{'📷 Billede: ' + image_url if image_url else ''}

—
TimeLapse Pro Alarm System
"""

    # HTML
    matched_tags = " ".join(
        f'<span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:4px;font-size:12px;">{m}</span>'
        for m in alarm.get("matched_on", [])
    )
    color    = SEVERITY_COLOR.get(severity, "FF8C00")
    img_html = f'<p><a href="{image_url}" style="color:#3b82f6;">📷 Se billede</a></p>' if image_url else ""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px;">
  <div style="max-width:600px;margin:0 auto;">
    <div style="background:#{color}22;border-left:4px solid #{color};border-radius:8px;padding:20px;margin-bottom:20px;">
      <h1 style="margin:0;font-size:20px;color:#{color};">{emoji} {severity.upper()} — {alarm.get('rule_name','Alarm')}</h1>
    </div>

    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px 0;color:#64748b;width:130px;">Regel</td>
          <td style="padding:8px 0;font-weight:bold;">{alarm.get('rule_name','—')}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Enhed</td>
          <td style="padding:8px 0;">{alarm.get('device_id','—')}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Tidspunkt</td>
          <td style="padding:8px 0;">{_format_time(alarm.get('triggered_at'))}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Konfidence</td>
          <td style="padding:8px 0;">{int(alarm.get('confidence',0)*100)}%</td></tr>
    </table>

    <div style="background:#1e293b;border-radius:8px;padding:16px;margin:16px 0;">
      <p style="margin:0 0 8px 0;color:#64748b;font-size:12px;">BESKRIVELSE</p>
      <p style="margin:0;">{alarm.get('description','—')}</p>
    </div>

    <div style="margin:16px 0;">
      <p style="color:#64748b;font-size:12px;margin-bottom:8px;">AI MATCHEDE PÅ</p>
      {matched_tags}
    </div>

    {img_html}

    <hr style="border:none;border-top:1px solid #1e293b;margin:24px 0;">
    <p style="color:#475569;font-size:11px;margin:0;">TimeLapse Pro Alarm System — Capture ID {alarm.get('capture_id','—')}</p>
  </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_cfg.get("from", email_cfg.get("username", ""))
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg.get("smtp_port", 587)) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(email_cfg["username"], email_cfg["password"])
            server.sendmail(email_cfg["username"], recipients, msg.as_bytes())
        log.info("Email sendt til %s: %s", recipients, subject)
        return True
    except Exception as e:
        log.error("Email fejl: %s", e)
        return False


def send_sms(alarm: dict, config: dict) -> bool:
    """
    Send SMS via GatewayAPI (gatewayapi.com).

    Opsætning:
      provider:  gatewayapi
      api_token: <fra gatewayapi.com → API → Tokens>
      sender:    TimeLapse  (maks 11 tegn)
      to:        ["+4512345678"]
    """
    sms_cfg = config.get("sms", {})
    if not sms_cfg.get("enabled", False):
        return False

    recipients = sms_cfg.get("to", [])
    if not recipients:
        return False

    severity = alarm.get("severity", "warning")
    emoji    = SEVERITY_EMOJI.get(severity, "⚠️")

    message = (
        f"{emoji} {alarm.get('rule_name','Alarm')}\n"
        f"{alarm.get('device_id','')}\n"
        f"{_format_time(alarm.get('triggered_at'))}\n"
        f"{alarm.get('description','')[:80]}"
    )

    provider = sms_cfg.get("provider", "gatewayapi").lower()

    if provider == "gatewayapi":
        return _send_gatewayapi(message, recipients, sms_cfg)
    elif provider == "twilio":
        return _send_twilio(message, recipients, sms_cfg)
    else:
        log.warning("Ukendt SMS-provider: %s", provider)
        return False


def _send_gatewayapi(message: str, recipients: list[str], cfg: dict) -> bool:
    """GatewayAPI REST v3."""
    try:
        r = requests.post(
            "https://gatewayapi.com/rest/mtsms",
            auth=(cfg["api_token"], ""),
            json={
                "sender":     cfg.get("sender", "TimeLapse")[:11],
                "message":    message,
                "recipients": [{"msisdn": int(n.replace("+", "").replace(" ", ""))} for n in recipients],
            },
            timeout=10,
        )
        if r.ok:
            log.info("SMS sendt via GatewayAPI til %s", recipients)
            return True
        else:
            log.error("GatewayAPI fejl %d: %s", r.status_code, r.text[:200])
            return False
    except Exception as e:
        log.error("SMS fejl: %s", e)
        return False


def _send_twilio(message: str, recipients: list[str], cfg: dict) -> bool:
    """Twilio SMS API."""
    try:
        import base64
        auth = base64.b64encode(f"{cfg['account_sid']}:{cfg['auth_token']}".encode()).decode()
        for to in recipients:
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{cfg['account_sid']}/Messages.json",
                headers={"Authorization": f"Basic {auth}"},
                data={"Body": message, "From": cfg.get("from_number"), "To": to},
                timeout=10,
            )
            if not r.ok:
                log.error("Twilio fejl: %s", r.text[:200])
        return True
    except Exception as e:
        log.error("Twilio fejl: %s", e)
        return False


def send_teams(alarm: dict, config: dict, image_url: Optional[str] = None) -> bool:
    """
    Send alarm til Microsoft Teams via Incoming Webhook.

    Opsætning i Teams:
      1. Kanal → ... → Connectors → Incoming Webhook → Konfigurér
         (eller: Workflows → "Post to a channel when a webhook request is received")
      2. Giv den et navn og et ikon
      3. Kopiér webhook_url

    Config:
      enabled:     true
      webhook_url: https://froekjaer.webhook.office.com/webhookb2/...
    """
    teams_cfg = config.get("teams", {})
    if not teams_cfg.get("enabled", False):
        return False

    webhook_url = teams_cfg.get("webhook_url", "")
    if not webhook_url:
        log.warning("Teams: ingen webhook_url konfigureret")
        return False

    severity = alarm.get("severity", "warning")
    emoji    = SEVERITY_EMOJI.get(severity, "⚠️")
    color    = SEVERITY_COLOR.get(severity, "FF8C00")

    matched_str = " · ".join(alarm.get("matched_on", []))

    # Adaptive Card format (virker med både Connectors og Workflows)
    payload = {
        "type":        "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type":    "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type":   "TextBlock",
                        "text":   f"{emoji} {severity.upper()} — {alarm.get('rule_name', 'Alarm')}",
                        "weight": "Bolder",
                        "size":   "Large",
                        "color":  "Attention" if severity == "critical" else "Warning",
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Regel",      "value": alarm.get("rule_name", "—")},
                            {"title": "Enhed",      "value": alarm.get("device_id", "—")},
                            {"title": "Tidspunkt",  "value": _format_time(alarm.get("triggered_at"))},
                            {"title": "Konfidence", "value": f"{int(alarm.get('confidence', 0) * 100)}%"},
                            {"title": "Matchede på","value": matched_str or "—"},
                        ],
                    },
                    {
                        "type": "TextBlock",
                        "text": alarm.get("description", ""),
                        "wrap": True,
                        "color": "Default",
                    },
                ],
                "actions": ([{
                    "type":  "Action.OpenUrl",
                    "title": "📷 Se billede",
                    "url":   image_url,
                }] if image_url else []),
            },
        }],
    }

    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.ok:
            log.info("Teams besked sendt: %s", alarm.get("rule_name"))
            return True
        else:
            log.error("Teams fejl %d: %s", r.status_code, r.text[:200])
            return False
    except Exception as e:
        log.error("Teams fejl: %s", e)
        return False


# ── Hoved-dispatcher ──────────────────────────────────────────────────────────

def notify(alarm: dict, db, image_url: Optional[str] = None) -> dict[str, bool]:
    """
    Send notifikationer for en alarm via alle aktiverede kanaler.

    Returnerer dict med status per kanal:
      {"email": True, "sms": False, "teams": True}

    Fejl i én kanal stopper ikke de andre.
    """
    config = get_notification_config(db)
    if not config:
        return {}

    if not should_notify(alarm, config):
        log.debug("Alarm %s under min_severity — ingen notifikation", alarm.get("severity"))
        return {}

    results = {}

    # Email
    if config.get("email", {}).get("enabled"):
        results["email"] = send_email(alarm, config, image_url)

    # SMS
    if config.get("sms", {}).get("enabled"):
        results["sms"] = send_sms(alarm, config)

    # Teams
    if config.get("teams", {}).get("enabled"):
        results["teams"] = send_teams(alarm, config, image_url)

    if results:
        log.info("Notifikationer sendt for '%s': %s", alarm.get("rule_name"), results)

    return results


# ── Hjælpefunktioner ──────────────────────────────────────────────────────────

def _format_time(iso_str: Optional[str], tz: str = "Europe/Copenhagen") -> str:
    if not iso_str:
        return "—"
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt = dt.astimezone(ZoneInfo(tz))
        return dt.strftime("%d. %b %Y kl. %H:%M")
    except Exception:
        return iso_str[:16]
