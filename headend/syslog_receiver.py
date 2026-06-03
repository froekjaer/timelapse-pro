#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — syslog_receiver.py
# ───────────────────────────────────────────────────────────────────────────
# Separate SIEM syslog ingress for network equipment.
# Default lab port is 5514 (UDP + TCP) to avoid privileged TCP/UDP 514.
# ═══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import re
import selectors
import signal
import socket
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from database import SessionLocal
from siem import record_events

LOG = logging.getLogger("syslog_receiver")

FACILITY_NAMES = {
    0: "kernel", 1: "user", 2: "mail", 3: "daemon", 4: "auth", 5: "syslog",
    6: "lpr", 7: "news", 8: "uucp", 9: "clock", 10: "authpriv", 11: "ftp",
    12: "ntp", 13: "security", 14: "console", 15: "cron", 16: "local0",
    17: "local1", 18: "local2", 19: "local3", 20: "local4", 21: "local5",
    22: "local6", 23: "local7",
}

SEVERITY_NAMES = {
    0: "critical",
    1: "critical",
    2: "critical",
    3: "error",
    4: "warning",
    5: "warning",
    6: "info",
    7: "debug",
}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _local_tz():
    return datetime.now().astimezone().tzinfo


def _parse_allowlist(raw: str) -> list[ipaddress._BaseNetwork]:
    networks = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            LOG.warning("Ignoring invalid syslog allowlist entry: %s", item)
    return networks


def _source_allowed(source_ip: str, allowlist: list[ipaddress._BaseNetwork], lab_accept_all: bool) -> bool:
    if lab_accept_all:
        return True
    if not allowlist:
        return False
    try:
        ip = ipaddress.ip_address(source_ip)
    except ValueError:
        return False
    return any(ip in network for network in allowlist)


def _parse_ts(value: str) -> datetime:
    now = datetime.now(_local_tz())
    for fmt in ("%b %d %H:%M:%S", "%b  %d %H:%M:%S"):
        try:
            parsed = datetime.strptime(f"{now.year} {value}", f"%Y {fmt}").replace(tzinfo=_local_tz())
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _classify_message(message: str, app_name: str = "") -> tuple[str, str]:
    lowered = f"{app_name} {message}".lower()
    if any(term in lowered for term in ("deny", "denied", "drop", "blocked", "reject")):
        return "network_connection_denied", "network"
    if any(term in lowered for term in ("login failed", "authentication failure", "auth failed", "invalid user")):
        return "network_auth_failed", "identity"
    if any(term in lowered for term in ("login", "logged in", "accepted password", "accepted publickey")):
        return "network_auth_success", "identity"
    if any(term in lowered for term in ("config changed", "configuration changed", "commit complete")):
        return "network_config_changed", "change"
    if any(term in lowered for term in ("link down", "port down", "interface down")):
        return "network_link_down", "network"
    if any(term in lowered for term in ("link up", "port up", "interface up")):
        return "network_link_up", "network"
    if any(term in lowered for term in ("vpn", "ipsec", "wireguard")):
        return "network_vpn_event", "network"
    if any(term in lowered for term in ("threat", "ids", "ips", "malware", "attack")):
        return "network_security_alert", "security"
    return "syslog_event", "network"


def parse_syslog(raw: bytes, source_ip: str) -> dict:
    text = raw.decode("utf-8", errors="replace").strip("\x00\r\n ")
    pri = None
    facility = None
    severity = "info"
    pri_match = re.match(r"^<(\d{1,3})>(.*)$", text, flags=re.S)
    if pri_match:
        pri = int(pri_match.group(1))
        facility = pri // 8
        severity = SEVERITY_NAMES.get(pri % 8, "info")
        text = pri_match.group(2).strip()

    hostname = source_ip
    app_name = ""
    message = text
    occurred = datetime.now(timezone.utc)
    protocol = "unknown"

    # RFC5424: 1 2026-06-03T08:00:00Z host app proc msgid [sd] message
    m5424 = re.match(
        r"^(?P<version>\d+)\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+(?P<app>\S+)\s+(?P<proc>\S+)\s+(?P<msgid>\S+)\s+(?P<rest>.*)$",
        text,
        flags=re.S,
    )
    if m5424 and m5424.group("version") == "1":
        protocol = "rfc5424"
        occurred = _parse_ts(m5424.group("ts"))
        hostname = m5424.group("host") if m5424.group("host") != "-" else source_ip
        app_name = "" if m5424.group("app") == "-" else m5424.group("app")
        message = m5424.group("rest")
        if message.startswith("- "):
            message = message[2:]
    else:
        # RFC3164: Jun  3 10:00:00 host app[pid]: message
        m3164 = re.match(
            r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<rest>.*)$",
            text,
            flags=re.S,
        )
        if m3164:
            protocol = "rfc3164"
            occurred = _parse_ts(m3164.group("ts"))
            hostname = m3164.group("host")
            rest = m3164.group("rest")
            app_match = re.match(r"^(?P<app>[\w./-]+)(?:\[\d+\])?:\s*(?P<msg>.*)$", rest, flags=re.S)
            if app_match:
                app_name = app_match.group("app")
                message = app_match.group("msg")
            else:
                message = rest

    event_type, category = _classify_message(message, app_name)
    device_id = f"SYSLOG-{re.sub(r'[^A-Za-z0-9_-]+', '_', hostname)[:42] or source_ip}"
    return {
        "device_id": device_id,
        "event": {
            "event_type": event_type,
            "severity": severity,
            "category": category,
            "source": "syslog",
            "logger": app_name or "syslog",
            "process": FACILITY_NAMES.get(facility, "syslog") if facility is not None else "syslog",
            "source_ip": source_ip,
            "raw_message": message,
            "occurred_at": occurred.isoformat(),
            "syslog": {
                "protocol": protocol,
                "pri": pri,
                "facility": facility,
                "facility_name": FACILITY_NAMES.get(facility) if facility is not None else None,
                "hostname": hostname,
            },
        },
    }


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = max(1, per_minute)
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._events[key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.per_minute:
            return False
        bucket.append(now)
        return True


class SyslogReceiver:
    def __init__(self, host: str, port: int, protocols: set[str], allowlist: list[ipaddress._BaseNetwork],
                 lab_accept_all: bool, rate_per_source_per_minute: int):
        self.host = host
        self.port = port
        self.protocols = protocols
        self.allowlist = allowlist
        self.lab_accept_all = lab_accept_all
        self.rate = RateLimiter(rate_per_source_per_minute)
        self.selector = selectors.DefaultSelector()
        self.running = True

    def start(self) -> None:
        if "udp" in self.protocols:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind((self.host, self.port))
            udp.setblocking(False)
            self.selector.register(udp, selectors.EVENT_READ, self._read_udp)
        if "tcp" in self.protocols:
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp.bind((self.host, self.port))
            tcp.listen(100)
            tcp.setblocking(False)
            self.selector.register(tcp, selectors.EVENT_READ, self._accept_tcp)
        LOG.info(
            "Syslog receiver started host=%s port=%s protocols=%s lab_accept_all=%s allowlist=%s",
            self.host, self.port, ",".join(sorted(self.protocols)), self.lab_accept_all, self.allowlist,
        )
        while self.running:
            for key, _ in self.selector.select(timeout=1):
                key.data(key.fileobj)

    def stop(self, *_args) -> None:
        self.running = False

    def _read_udp(self, sock: socket.socket) -> None:
        data, addr = sock.recvfrom(65535)
        self._handle(data, addr[0])

    def _accept_tcp(self, sock: socket.socket) -> None:
        conn, addr = sock.accept()
        conn.settimeout(3)
        try:
            chunks = []
            while True:
                chunk = conn.recv(65535)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
            for line in b"".join(chunks).splitlines():
                self._handle(line, addr[0])
        finally:
            conn.close()

    def _handle(self, data: bytes, source_ip: str) -> None:
        if not _source_allowed(source_ip, self.allowlist, self.lab_accept_all):
            LOG.warning("Dropped syslog from non-allowlisted source=%s", source_ip)
            return
        if not self.rate.allow(source_ip):
            LOG.warning("Rate limited syslog source=%s", source_ip)
            return
        try:
            parsed = parse_syslog(data, source_ip)
            db = SessionLocal()
            try:
                record_events(db, parsed["device_id"], [parsed["event"]])
            finally:
                db.close()
        except Exception as exc:
            LOG.warning("Syslog ingest failed source=%s error=%s", source_ip, exc)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="TimeLapse Pro SIEM syslog receiver")
    parser.add_argument("--host", default=os.getenv("TIMELAPSE_SYSLOG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("TIMELAPSE_SYSLOG_PORT", "5514")))
    parser.add_argument("--protocols", default=os.getenv("TIMELAPSE_SYSLOG_PROTOCOLS", "udp,tcp"))
    parser.add_argument("--allowlist", default=os.getenv("TIMELAPSE_SYSLOG_ALLOWLIST", ""))
    parser.add_argument("--lab-accept-all", action="store_true", default=_env_bool("TIMELAPSE_SYSLOG_LAB_ACCEPT_ALL", True))
    parser.add_argument(
        "--rate-per-source-per-minute",
        type=int,
        default=int(os.getenv("TIMELAPSE_SYSLOG_RATE_PER_SOURCE_PER_MINUTE", "600")),
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    protocols = {p.strip().lower() for p in args.protocols.split(",") if p.strip()}
    if not protocols <= {"udp", "tcp"} or not protocols:
        raise SystemExit("protocols must contain udp and/or tcp")

    receiver = SyslogReceiver(
        host=args.host,
        port=args.port,
        protocols=protocols,
        allowlist=_parse_allowlist(args.allowlist),
        lab_accept_all=args.lab_accept_all,
        rate_per_source_per_minute=args.rate_per_source_per_minute,
    )
    signal.signal(signal.SIGTERM, receiver.stop)
    signal.signal(signal.SIGINT, receiver.stop)
    receiver.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
