# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Security Events Collector
# ═══════════════════════════════════════════════════════════════════════════
"""
Samler security events fra systemlogs på Linux og macOS.

Events der samles:
  ssh_failure     — Mislykket SSH login (brute force detektion)
  ssh_success     — Vellykket SSH login
  sudo_use        — sudo-kommando udført
  sudo_failure    — sudo afvist (forkert password / ingen rettighed)
  service_crash   — systemd/launchd service crashet
  new_user        — ny bruger oprettet på systemet
  passwd_change   — password ændret
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# ── Event type konstanter ─────────────────────────────────────────────────
SSH_FAILURE    = "ssh_failure"
SSH_SUCCESS    = "ssh_success"
SUDO_USE       = "sudo_use"
SUDO_FAILURE   = "sudo_failure"
SERVICE_CRASH  = "service_crash"
NEW_USER       = "new_user"
PASSWD_CHANGE  = "passwd_change"
HTTP_ERROR         = "http_error"
SUSPICIOUS_REQUEST = "suspicious_request"

SEVERITY_INFO     = "info"
SEVERITY_WARNING  = "warning"
SEVERITY_CRITICAL = "critical"

EVENT_SEVERITY = {
    SSH_FAILURE:   SEVERITY_WARNING,
    SSH_SUCCESS:   SEVERITY_INFO,
    SUDO_USE:      SEVERITY_INFO,
    SUDO_FAILURE:  SEVERITY_WARNING,
    SERVICE_CRASH: SEVERITY_CRITICAL,
    NEW_USER:      SEVERITY_WARNING,
    PASSWD_CHANGE: SEVERITY_WARNING,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _since_iso(lookback_seconds: int) -> str:
    """ISO8601 timestamp for X sekunder siden."""
    return (_now_utc() - timedelta(seconds=lookback_seconds)).isoformat()


# ── Linux collector (journalctl) ──────────────────────────────────────────

# SSH patterns
_SSH_FAIL_RE = re.compile(
    r"Failed (?:password|publickey) for (?:invalid user )?(\S+) from ([\d.]+)"
)
_SSH_OK_RE = re.compile(
    r"Accepted (?:password|publickey) for (\S+) from ([\d.]+)"
)
_SUDO_OK_RE = re.compile(
    r"sudo:\s+(\S+)\s*:.*COMMAND=(.*)"
)
_SUDO_FAIL_RE = re.compile(
    r"sudo:\s+(\S+)\s*:.*user NOT in sudoers|authentication failure"
)
_NEW_USER_RE = re.compile(
    r"new user: name=(\S+)"
)
_PASSWD_RE = re.compile(
    r"password changed for (\S+)"
)


def _collect_linux(lookback_seconds: int) -> list[dict]:
    events = []
    since = (_now_utc() - timedelta(seconds=lookback_seconds)).strftime("%Y-%m-%d %H:%M:%S")

    # ── SSH events ────────────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["journalctl", "-u", "ssh", "-u", "sshd",
             "--since", since, "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=10
        ).stdout

        for line in out.splitlines():
            ts = _parse_journalctl_ts(line)

            m = _SSH_FAIL_RE.search(line)
            if m:
                events.append(_event(SSH_FAILURE, ts,
                    username=m.group(1), source_ip=m.group(2),
                    raw=line.strip()))
                continue

            m = _SSH_OK_RE.search(line)
            if m:
                events.append(_event(SSH_SUCCESS, ts,
                    username=m.group(1), source_ip=m.group(2),
                    raw=line.strip()))
    except Exception as e:
        log.debug("SSH journal fejl: %s", e)

    # ── Sudo events ───────────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["journalctl", "_COMM=sudo",
             "--since", since, "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=10
        ).stdout

        for line in out.splitlines():
            ts = _parse_journalctl_ts(line)

            m = _SUDO_OK_RE.search(line)
            if m:
                events.append(_event(SUDO_USE, ts,
                    username=m.group(1),
                    raw=line.strip()[:200]))
                continue

            if _SUDO_FAIL_RE.search(line):
                events.append(_event(SUDO_FAILURE, ts, raw=line.strip()[:200]))
    except Exception as e:
        log.debug("Sudo journal fejl: %s", e)

    # ── Service crashes ───────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["journalctl", "-p", "err",
             "--since", since, "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=10
        ).stdout

        for line in out.splitlines():
            if "failed" in line.lower() and ("service" in line.lower() or "unit" in line.lower()):
                ts = _parse_journalctl_ts(line)
                events.append(_event(SERVICE_CRASH, ts, raw=line.strip()[:200]))
    except Exception as e:
        log.debug("Service crash journal fejl: %s", e)

    # ── Nye brugere / password-ændringer ─────────────────────────────────
    try:
        out = subprocess.run(
            ["journalctl", "--since", since, "--no-pager",
             "-o", "short-iso", "-g", "new user|password changed"],
            capture_output=True, text=True, timeout=10
        ).stdout

        for line in out.splitlines():
            ts = _parse_journalctl_ts(line)
            m = _NEW_USER_RE.search(line)
            if m:
                events.append(_event(NEW_USER, ts,
                    username=m.group(1), raw=line.strip()))
                continue
            m = _PASSWD_RE.search(line)
            if m:
                events.append(_event(PASSWD_CHANGE, ts,
                    username=m.group(1), raw=line.strip()))
    except Exception as e:
        log.debug("User/passwd journal fejl: %s", e)

    return events


def _parse_journalctl_ts(line: str) -> str:
    """Forsøger at parse ISO timestamp fra journalctl short-iso output."""
    try:
        # Format: 2026-05-11T13:45:12+0000 hostname process[pid]: message
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4})", line)
        if m:
            return m.group(1)
    except Exception:
        pass
    return _now_utc().isoformat()


# ── macOS collector (log show) ────────────────────────────────────────────

_MACOS_SSH_FAIL_RE = re.compile(
    r"Failed (?:password|publickey) for (?:invalid user )?(\S+) from ([\d.]+)"
)
_MACOS_SSH_OK_RE = re.compile(
    r"Accepted (?:password|publickey) for (\S+) from ([\d.]+)"
)
_MACOS_SUDO_RE = re.compile(
    r"sudo\[.*\].*:\s+(\S+)\s*:.*COMMAND=(.*)"
)


def _collect_macos(lookback_seconds: int) -> list[dict]:
    events = []
    since_dt = _now_utc() - timedelta(seconds=lookback_seconds)
    # macOS log show format: YYYY-MM-DD HH:MM:SS
    since_str = since_dt.strftime("%Y-%m-%d %H:%M:%S")

    # ── SSH via log show ──────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["log", "show",
             "--predicate", 'process == "sshd"',
             "--start", since_str,
             "--style", "syslog"],
            capture_output=True, text=True, timeout=15
        ).stdout

        for line in out.splitlines():
            ts = _parse_macos_ts(line)
            m = _MACOS_SSH_FAIL_RE.search(line)
            if m:
                events.append(_event(SSH_FAILURE, ts,
                    username=m.group(1), source_ip=m.group(2),
                    raw=line.strip()[:200]))
                continue
            m = _MACOS_SSH_OK_RE.search(line)
            if m:
                events.append(_event(SSH_SUCCESS, ts,
                    username=m.group(1), source_ip=m.group(2),
                    raw=line.strip()[:200]))
    except Exception as e:
        log.debug("macOS SSH log fejl: %s", e)

    # ── Sudo via log show ─────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["log", "show",
             "--predicate", 'process == "sudo"',
             "--start", since_str,
             "--style", "syslog"],
            capture_output=True, text=True, timeout=15
        ).stdout

        for line in out.splitlines():
            ts = _parse_macos_ts(line)
            m = _MACOS_SUDO_RE.search(line)
            if m:
                events.append(_event(SUDO_USE, ts,
                    username=m.group(1),
                    raw=line.strip()[:200]))
    except Exception as e:
        log.debug("macOS sudo log fejl: %s", e)

    # ── Launchd crashes ───────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["log", "show",
             "--predicate", 'process == "launchd" AND messageType == "error"',
             "--start", since_str,
             "--style", "syslog"],
            capture_output=True, text=True, timeout=15
        ).stdout

        for line in out.splitlines():
            if "failed" in line.lower() or "crash" in line.lower():
                ts = _parse_macos_ts(line)
                events.append(_event(SERVICE_CRASH, ts, raw=line.strip()[:200]))
    except Exception as e:
        log.debug("macOS launchd log fejl: %s", e)

    return events


def _parse_macos_ts(line: str) -> str:
    try:
        m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if m:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        pass
    return _now_utc().isoformat()




def _collect_nginx(log_path: str, lookback_seconds: int) -> list[dict]:
    """Parser nginx access log for security events."""
    events = []
    since = _now_utc() - __import__('datetime').timedelta(seconds=lookback_seconds)
    SUSPICIOUS = [".env", "wp-admin", "phpmyadmin", ".git", "xmlrpc",
                  "shell", "passwd", "etc/shadow", "cmd=", "eval("]
    try:
        with open(log_path) as f:
            for line in f:
                m = re.match(
                    r"([\d.]+) .+ \[(.+?)\] \"(\S+) (\S+) \S+\" (\d+)",
                    line
                )
                if not m:
                    continue
                ip, ts_str, method, path_req, status = m.groups()
                status = int(status)
                try:
                    from datetime import datetime
                    ts = datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
                except Exception:
                    continue
                if ts < since:
                    continue
                ts_iso = ts.isoformat()
                if status >= 400:
                    events.append(_event(
                        "http_error", ts_iso,
                        source_ip=ip,
                        raw=f"{method} {path_req} -> {status}"
                    ))
                if any(s in path_req.lower() for s in SUSPICIOUS):
                    events.append(_event(
                        "suspicious_request", ts_iso,
                        source_ip=ip,
                        raw=f"{method} {path_req} -> {status}"
                    ))
    except Exception as e:
        log.debug("Nginx log fejl: %s", e)
    return events

# ── Fælles event-builder ──────────────────────────────────────────────────

def _event(event_type: str, occurred_at: str,
           username: Optional[str] = None,
           source_ip: Optional[str] = None,
           raw: str = "") -> dict:
    return {
        "event_type":  event_type,
        "severity":    EVENT_SEVERITY.get(event_type, SEVERITY_INFO),
        "username":    username,
        "source_ip":   source_ip,
        "raw_message": raw,
        "occurred_at": occurred_at,
    }


# ── Offentlig API ─────────────────────────────────────────────────────────

def collect_security_events(cfg) -> list[dict]:
    """
    Samler security events for lookback_seconds siden.
    Returnerer liste af event-dicts klar til POST.
    """
    is_macos = platform.system() == "Darwin"
    try:
        if is_macos:
            events = _collect_macos(cfg.security_lookback)
        else:
            events = _collect_linux(cfg.security_lookback)
        log.debug("Security collector: %d events fundet (%s)",
                  len(events), "macOS" if is_macos else "Linux")
        # Nginx access log
        nginx_log = getattr(cfg, 'nginx_access_log', '')
        if nginx_log:
            from pathlib import Path
            if Path(nginx_log).exists():
                events.extend(_collect_nginx(nginx_log, cfg.security_lookback))

        return events
    except Exception as e:
        log.warning("Security collector fejlede: %s", e)
        return []
