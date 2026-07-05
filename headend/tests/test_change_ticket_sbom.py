"""
Kontrakt-test for change ticket-dokumentet (§K "Change ticket med artifact/
SBOM/rollback") — `_build_change_ticket()` og `bind_artifact_to_update()` i
`headend/main.py`.

Baggrund (2026-07-05, Claude periodisk tjek): `ChangeTicket.sbom_ref` og
`.test_evidence_ref` blev gemt i DB og eksponeret via `_ticket_to_dict()`
(API-svaret), men optrådte ALDRIG i det faktiske signerede dokument
(`machine_json`/`human_readable_md`) — hverken ved oprettelse eller når et
artifact blev bundet til en allerede-eksisterende ticket. I sidstnævnte
tilfælde blev `ticket.sbom_ref`/`.test_evidence_ref`-kolonnerne opdateret
direkte UDEN at gensignere dokumentet, så `content_sha256`/`signature` kunne
tavst komme ud af trit med ticketens faktiske indhold — et reelt
integritetshul i et dokument hvis formål er at være en troværdig,
signeret audit-post. Logikken er nu samlet i `_render_change_ticket_document()`,
brugt begge steder.

Kører direkte mod den faktiske kode i `headend/main.py` med en frisk SQLite-
database (samme mønster som `test_report_update_rollup.py`) — ingen live
Postgres/headend rørt.

Kør (fra headend/):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest httpx
    /tmp/hvenv/bin/python3 -m pytest tests/test_change_ticket_sbom.py -v
"""
import json
import os
import sys
import tempfile
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture()
def db_session():
    database.create_tables()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


def _make_user(session, username="admin1", role="admin"):
    user = database.User(
        username=username,
        email=f"{username}@example.test",
        password_hash="x",
        role=role,
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
    artifact = database.UpdateArtifact(
        artifact_id=artifact_id,
        artifact_type="app",
        version="1.2.3",
        source_commit="deadbeef",
        source_ref="ci-run-1",
        sha256="a" * 64,
        sbom_ref=sbom_ref,
        signed_by="ci-signer",
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

    assert ticket.sbom_ref is None
    assert "artifact" not in json.loads(ticket.machine_json)
    assert "Ingen artifact er bundet endnu" in ticket.human_readable_md


def test_bind_artifact_to_existing_ticket_resigns_document_with_sbom(db_session):
    """Kernescenariet for buggen: en ticket oprettes FØR artifactet findes
    (fx via /api/updates/{id}/create-change-ticket), og artifactet bindes
    BAGEFTER via bind-artifact. Det signerede dokument skal opdateres til at
    indeholde SBOM-referencen, og content_sha256/signature skal ændre sig
    tilsvarende (ikke blive stående og pege på et forældet dokument)."""
    user = _make_user(db_session)
    update = _make_update(db_session, update_type="app_updates")

    # Ticket oprettes uden artifact (matcher create_change_ticket_for_update).
    ticket = main._build_change_ticket(update, main.ChangeTicketPayload(), user, None)
    db_session.add(ticket)
    db_session.commit()

    original_sha = ticket.content_sha256
    original_sig = ticket.signature
    assert "artifact" not in json.loads(ticket.machine_json)

    artifact = _make_artifact(db_session, artifact_id="art-late", sbom_ref="sbom:late-bound")

    main.bind_artifact_to_update(
        update.id,
        {"artifact_id": artifact.artifact_id},
        current_user=user,
        db=db_session,
    )

    db_session.refresh(ticket)
    machine = json.loads(ticket.machine_json)
    assert machine["artifact"]["sbom_ref"] == "sbom:late-bound"
    assert ticket.sbom_ref == "sbom:late-bound"
    assert "sbom:late-bound" in ticket.human_readable_md
    # Dokumentet er reelt et andet nu (SBOM tilføjet) -> hash/signatur SKAL
    # være genberegnet, ikke stå og pege på det gamle (artifact-løse) indhold.
    assert ticket.content_sha256 != original_sha
    assert ticket.signature != original_sig


def test_bind_artifact_preserves_original_creator_and_ticket_id(db_session):
    """Re-signering ved sen artifact-binding må ikke ændre hvem/hvornår
    ticketen oprindeligt blev oprettet af, eller dens ticket_id — kun
    dokumentets indhold og signaturen opdateres."""
    user = _make_user(db_session, username="creator1")
    other_user = _make_user(db_session, username="binder1")
    update = _make_update(db_session, update_type="app_updates")

    ticket = main._build_change_ticket(update, main.ChangeTicketPayload(), user, None)
    db_session.add(ticket)
    db_session.commit()
    original_ticket_id = ticket.ticket_id
    original_created_by = ticket.created_by
    original_created_at = ticket.created_at

    artifact = _make_artifact(db_session, artifact_id="art-late2", sbom_ref="sbom:late2")
    main.bind_artifact_to_update(
        update.id,
        {"artifact_id": artifact.artifact_id},
        current_user=other_user,
        db=db_session,
    )

    db_session.refresh(ticket)
    assert ticket.ticket_id == original_ticket_id
    assert ticket.created_by == original_created_by
    assert ticket.created_at == original_created_at
