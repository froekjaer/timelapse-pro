"""Contract tests for the Headend Generator API helpers.

Pure-function tests — no DB/FastAPI app required. Route-level auth is covered
by the global sweep in test_route_auth_coverage.py (the router uses the
reviewed _current_viewer/_require_platform_admin pattern).
"""

import pytest

from api.headend_generator_api import (
    _bundle_storage_dir,
    _render_commands,
    _render_conf,
    _render_readme,
    _safe_bundle_name,
    _validate_release_selection,
    _validate_request,
)


def _base_payload(**overrides):
    payload = {
        "environment": "staging",
        "domain": "staging.timelapse-pro.dk",
        "backend_port": 8443,
    }
    payload.update(overrides)
    return payload


def test_defaults_are_filled_in():
    spec = _validate_request(_base_payload())
    assert spec["device_id"] == "TL-HEADEND-STAGING-1"
    assert spec["backend_port"] == 8443
    assert spec["db_name"] == "timelapse_db"
    assert spec["service_user"] == "_timelapse"
    assert spec["service_home"] == "/var/lib/timelapse"
    assert spec["tunnel_host"] == "staging.timelapse-pro.dk"
    assert spec["tunnel_port"] == 22222
    assert spec["tunnel_user"] == "tunnel"
    assert spec["repo_dir"] == "/Users/Shared/TimeLapsePro/releases/staging"
    assert 1 <= spec["expires_hours"] <= 24 * 14


@pytest.mark.parametrize("port", [21, 22, 80, 443])
def test_crushftp_ports_are_rejected(port):
    """Coexistence rule (PORTS.md): CrushFTP owns 21/22/80/443 — never TimeLapse."""
    with pytest.raises(ValueError, match="CrushFTP"):
        _validate_request(_base_payload(backend_port=port))


@pytest.mark.parametrize("environment", ["rd", "", "production", None])
def test_only_staging_and_prod_are_allowed(environment):
    with pytest.raises(ValueError):
        _validate_request(_base_payload(environment=environment))


def test_device_id_must_use_tl_prefix():
    with pytest.raises(ValueError, match="TL-"):
        _validate_request(_base_payload(device_id="HEADEND-1"))


def test_invalid_domain_is_rejected():
    with pytest.raises(ValueError):
        _validate_request(_base_payload(domain="not a domain"))


def test_conf_renders_environment_and_forbidden_port_note():
    spec = _validate_request(_base_payload(environment="prod", domain="backend.timelapse-pro.dk"))
    conf = _render_conf(spec)
    assert "TL_ENV=prod" in conf
    assert "TL_BACKEND_PORT=8443" in conf
    assert "TL_SERVICE_USER=_timelapse" in conf
    assert "TL_SERVICE_HOME=/var/lib/timelapse" in conf
    assert "TL_TUNNEL_PORT=22222" in conf
    assert "21/22/80/443" in conf  # coexistence warning present


def test_release_selection_is_bound_to_trusted_full_commit():
    commit = "a" * 40
    spec = _validate_request(_base_payload(release_tag="v1.4.0", expected_commit=commit))
    selected = _validate_release_selection(
        spec,
        [{"tag": "v1.4.0", "commit": commit, "signature_status": "trusted"}],
    )
    assert selected["expected_commit"] == commit


@pytest.mark.parametrize(
    ("tag", "commit", "message"),
    [
        ("", "a" * 40, "release-tag"),
        ("v1.4.0", "abc", "40-tegns"),
        ("v9.9.9", "a" * 40, "betroede"),
        ("v1.4.0", "b" * 40, "matcher ikke"),
    ],
)
def test_release_selection_rejects_invalid_pairs(tag, commit, message):
    spec = _validate_request(_base_payload(release_tag=tag, expected_commit=commit))
    with pytest.raises(ValueError, match=message):
        _validate_release_selection(
            spec,
            [{"tag": "v1.4.0", "commit": "a" * 40, "signature_status": "trusted"}],
        )


def test_shell_values_are_quoted_in_conf_and_commands():
    spec = _validate_request(
        _base_payload(
            data_dir="/Users/Shared/TimeLapse Pro/data",
            repo_dir="/Users/Shared/TimeLapse Pro/release",
            repo_url="git@github.com:froekjaer/timelapse-pro.git",
            release_tag="v1.4.0",
            expected_commit="a" * 40,
        )
    )
    assert "TL_DATA_DIR='/Users/Shared/TimeLapse Pro/data'" in _render_conf(spec)
    command = _render_commands(spec)[1]
    assert "--destination '/Users/Shared/TimeLapse Pro/release'" in command


@pytest.mark.parametrize("field", ["service_user", "service_group", "tunnel_user"])
def test_invalid_local_account_names_are_rejected(field):
    with pytest.raises(ValueError, match=field):
        _validate_request(_base_payload(**{field: "bad;name"}))


@pytest.mark.parametrize("port", [21, 22, 80, 443, 8080])
def test_tunnel_rejects_reserved_ports(port):
    with pytest.raises(ValueError, match="tunnel_port"):
        _validate_request(_base_payload(tunnel_port=port))


def test_readme_flags_manual_sftp_step():
    """GEN-01/GEN-02: the bundle must warn that SFTP 22222 is still a manual step."""
    spec = _validate_request(_base_payload())
    readme = _render_readme(spec)
    assert "22222" in readme
    assert "CrushFTP" in readme
    assert "bootstrap-token" in readme


def test_safe_bundle_name_accepts_generated_names():
    name = "timelapse-headend-installer-staging-tl-headend-staging-1-20260718-120000.tar.gz"
    assert _safe_bundle_name(name) == name


@pytest.mark.parametrize("bad", [
    "../etc/passwd", "a/b.tar.gz", "..\\x.tar.gz", "x.tar", "", ".hidden.tar.gz",
    "navn med mellemrum.tar.gz", "x.tar.gz/../y.tar.gz",
])
def test_safe_bundle_name_rejects_traversal_and_junk(bad):
    with pytest.raises(ValueError):
        _safe_bundle_name(bad)


def test_bundle_storage_dir_honours_env_override(tmp_path, monkeypatch):
    """Env-varen styrer kataloget direkte — bruges bl.a. på staging/prod (GEN-11)."""
    target = tmp_path / "headend-images"
    monkeypatch.setenv("TIMELAPSE_HEADEND_IMAGE_DIR", str(target))
    resolved = _bundle_storage_dir(create=True)
    assert resolved == target
    assert target.is_dir()  # write-probe kørte uden fejl
