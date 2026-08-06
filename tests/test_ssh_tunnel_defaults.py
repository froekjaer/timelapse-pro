"""Regression test (2026-08-06): Peter asked why activating the SSH tunnel
in Settings -> System Administration required manually typing in a key file
path, remote port and endpoint that the system already knows. Investigation
found two disconnected mechanisms:

  1. _ensure_device_provisioning_credentials() (headend/main.py) already
     auto-generates a per-device SSH keypair and allocates a unique
     reverse_tunnel_port at zero-touch enrollment. inject_edge_image.py
     already bakes this same key into flashable images at
     /etc/timelapse/device_keys/id_ed25519, alongside a static
     timelapse-ssh-tunnel.service using TIMELAPSE_TUNNEL_HOST/_PORT/_USER
     (resolved via edge_provisioning_security.resolve_tunnel_settings()).
  2. SystemAdminPage.tsx's manual "SSH Tunnel" panel — a SEPARATE, dynamic
     mechanism (device_config.ssh_tunnel, read by edge/tunnel/ssh_manager.py)
     — required the SAME values typed in by hand, defaulting remote_port to
     a hardcoded "2201" for every device (a real cross-device port collision
     risk, since ssh_manager.py's own docstring says the port must be unique
     per device).

Fixed by exposing device.reverse_tunnel_port on get_device_detail() and
adding /api/admin/ssh-tunnel/defaults (reusing resolve_tunnel_settings() and
the same key path already used by the image-build pipeline), so the frontend
pre-fills instead of requiring re-entry of already-known values.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = MAIN.index(f"def {name}(")
    end = MAIN.index("\n@app.", start + 1)
    return MAIN[start:end]


def test_get_device_detail_exposes_reverse_tunnel_port() -> None:
    section = _function_source("get_device_detail")
    assert '"reverse_tunnel_port": getattr(device, "reverse_tunnel_port", None)' in section


def test_ssh_tunnel_defaults_endpoint_reuses_the_provisioning_resolver() -> None:
    section = _function_source("ssh_tunnel_defaults")
    assert "_edge_provisioning.resolve_tunnel_settings(" in section, (
        "must reuse edge_provisioning_security.resolve_tunnel_settings() — the same "
        "function that already resolves TIMELAPSE_TUNNEL_HOST/_PORT/_USER for the "
        "flashable image-build pipeline — rather than re-deriving the endpoint with "
        "separate, possibly-diverging logic."
    )
    assert "/etc/timelapse/device_keys/id_ed25519" in section, (
        "the suggested key_file path must match exactly where inject_edge_image.py "
        "actually writes the device's private key on a flashed image."
    )
    assert 'require_role("admin")' in MAIN[MAIN.index('def ssh_tunnel_defaults(') - 80:MAIN.index('def ssh_tunnel_defaults(') + 80]
