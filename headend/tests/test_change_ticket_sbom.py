import json
import os
import pathlib
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ.setdefault("TIMELAPSE_ENV", "test")

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture()
def db_session():
    database.create_tables()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


def _make_user(session):
    user = database.User(
        username="sbom-admin",
        email="sbom-admin@example.invalid",
        password_hash="unused",
        role="super_admin",
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def _make_update(session, update_type="app_security", severity="high", status="pending"):
    update = database.PendingUpdate(
        update_type=update_type,
        version="1.2.3",
        description="Test update",
        severity=severity,
        scope="device",
        scope_id="dev-1",
        status=status,
    )
    session.add(update)
    session.commit()
    return update


def _make_artifact(session, artifact_id="art-1", sbom_ref="sbom:dev-1:2026-07-05T00:00:00Z"):
    """Create a structurally deployable test artifact.

    These tests exercise change-ticket/SBOM binding rather than crypto. Real
    OpenPGP verification is covered by tests/test_artifact_openpgp_verification.py.
    The fixture therefore uses PGP-shaped test evidence so the stricter
    deployability gate does not mistake an unsigned dummy for a release.
    """
    artifact = database.UpdateArtifact(
        artifact_id=artifact_id,
        artifact_type="app",
        version="1.2.3",
        source_commit="deadbeef",
        source_ref="ci-run-1",
        sha256="a" * 64,
        sbom_ref=sbom_ref,
        signature="-----BEGIN PGP SIGNATURE-----\nci-test-signature\n-----END PGP SIGNATURE-----",
        signed_by="ci-test-release-signer",
        manifest_json=json.dumps({
            "schema": "timelapse.update_artifact.v1",
            "source": {"commit": "deadbeef", "dirty_worktree": False},
        }),
    )
    session.add(artifact)
    session.commit()
    return artifact


def test_build_change_ticket_includes_sbom_ref_when_artifact_known(db_session):
    """SBOM-referencen skal med i BÅDE machine_json og human_readable_md når
    et artifact allerede kendes ved ticket-oprettelse — ikke kun i API-dict."""
    user = _make_user(db_session)
    update = _make_update(db_session)
    artifact = _make_artifact(db_session)

    ticket = main._build_change_ticket(update, main.ChangeTicketPayload(), user, artifact)

    machine = json.loads(ticket.machine_json)
    assert machine["artifact"]["sbom_ref"] == artifact.sbom_ref
    assert artifact.sbom_ref in ticket.human_readable_md
    assert ticket.sbom_ref == artifact.sbom_ref


def test_build_change_ticket_without_artifact_has_no_stale_sbom_claim(db_session):
    """Uden artifact skal dokumentet sige det tydeligt, ikke lade som om SBOM
    findes."""
    user = _make_user(db_session)
    update = _make_update(db_session)

    ticket = main._build_change_ticket(update, main.ChangeTicketPayload(), user, None)

    machine = json.loads(ticket.machine_json)
    assert machine["artifact"] is None
    assert ticket.sbom_ref is None


def test_bind_artifact_to_existing_ticket_resigns_document_with_sbom(db_session):
    user = _make_user(db_session)
    update = _make_update(db_session)
    ticket = main._build_change_ticket(update, main.ChangeTicketPayload(), user, None)
    db_session.add(ticket)
    db_session.commit()
    artifact = _make_artifact(db_session)

    main.bind_artifact_to_update(
        update.id,
        artifact.artifact_id,
        _user=user,
        db=db_session,
    )

    db_session.refresh(ticket)
    machine = json.loads(ticket.machine_json)
    assert ticket.artifact_id == artifact.artifact_id
    assert ticket.sbom_ref == artifact.sbom_ref
    assert machine["artifact"]["sbom_ref"] == artifact.sbom_ref
    assert artifact.sbom_ref in ticket.human_readable_md
    assert ticket.signature


def test_bind_artifact_preserves_original_creator_and_ticket_id(db_session):
    creator = _make_user(db_session)
    update = _make_update(db_session)
    ticket = main._build_change_ticket(update, main.ChangeTicketPayload(), creator, None)
    original_ticket_id = ticket.ticket_id
    original_creator = ticket.created_by
    db_session.add(ticket)
    db_session.commit()
    artifact = _make_artifact(db_session)

    main.bind_artifact_to_update(
        update.id,
        artifact.artifact_id,
        _user=creator,
        db=db_session,
    )

    db_session.refresh(ticket)
    assert ticket.ticket_id == original_ticket_id
    assert ticket.created_by == original_creator
    assert ticket.artifact_id == artifact.artifact_id
