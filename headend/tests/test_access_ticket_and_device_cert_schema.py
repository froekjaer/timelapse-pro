"""
Kontrakt-test for de to skema-forberedende delskridt af #62 (break-glass support-
adgang) og #52 (intern CA/mTLS), begge udført 2026-07-06 (Claude) som "laveste
risiko, ingen nøglegenerering"-første-skridt, jf. Peters "kør bare på i den
rækkefølge der er bedst for dig".

1. `AccessTicket` (headend/database.py) — ny, SEPARAT tabel fra `ChangeTicket` for
   break-glass support-adgangs-tickets. Se modellens egen docstring for den fulde
   begrundelse (periodisk tjek #80's analyse: feltmisforhold + inkompatibelt
   status-vokabular mellem en godkendelses-livscyklus og en tids-baseret livscyklus).
   Denne testfil dækker KUN at modellen kan oprettes/forespørges korrekt — INGEN
   udstedelses-endpoint, script eller Support-CA-nøgle findes endnu (bevidst,
   se Claude_Support_Access_Model_2026-07-06.md §8).

2. `KeyCredential.key_type = "mtls_device_cert"` (headend/database.py) — GENBRUG af
   den eksisterende, allerede aktive credential-lifecycle-tabel til device-
   certifikater (modsat #62's AccessTicket, som bevidst IKKE genbruger ChangeTicket
   — se KeyCredential-docstringen for hvorfor DENNE genbrug derimod giver mening:
   status/expires_at/revoked_at/rotated_from_id matcher §7's certifikat-livscyklus
   næsten felt-for-felt). Denne testfil dækker at (a) en KeyCredential-række med
   dette key_type kan oprettes/forespørges, og (b) `_key_scopes()` kender den nye
   værdi. Den bevidst IKKE udvidede `/api/admin/key-management/credentials`-
   validering (stadig kun api|ssh|signing|bootstrap) er ikke en fejl — den manuelle
   admin-oprettelses-endpoint er ikke det rette sted at udstede device-certifikater
   (det bliver en fremtidig, dedikeret CSR-signerings-endpoint, §9 trin 3 i CA/mTLS-
   designet), så denne testfil dokumenterer/låser IKKE den grænse fast med en
   eksplicit "afvises stadig"-test — kun de to nye skema-stykker testes positivt.

Kør (fra headend/):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \\
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \\
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest
    /tmp/hvenv/bin/python3 -m pytest tests/test_access_ticket_and_device_cert_schema.py -v
"""
import os
import sys
import json
import tempfile
import pathlib
from datetime import timedelta

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


# ── AccessTicket (#62 skema) ────────────────────────────────────────────────────

def test_access_ticket_can_be_created_and_queried(db_session):
    now = database.now_utc()
    ticket = database.AccessTicket(
        ticket_id="AT-2026-07-06-0001",
        agent="claude",
        machine="staging",
        purpose="Installationsverifikation af headend v10",
        customer_scope="Kirkbi A/S",
        customer_consent_basis="implicit_dpa",
        customer_consent_reference="DPA 2026-06-xx, generel support-adgangs-klausul",
        valid_from=now,
        valid_until=now + timedelta(hours=2),
        granted_by="peter",
        content_sha256="a" * 64,
        signature="-----BEGIN PGP SIGNATURE-----\n...",
        signed_by="peter@froekjaer.dk",
        signed_at=now,
    )
    db_session.add(ticket)
    db_session.commit()

    fetched = db_session.query(database.AccessTicket).filter_by(ticket_id="AT-2026-07-06-0001").first()
    assert fetched is not None
    assert fetched.agent == "claude"
    assert fetched.machine == "staging"
    assert fetched.status == "active"  # default
    assert fetched.customer_consent_basis == "implicit_dpa"
    assert fetched.credential_id is None  # ikke koblet endnu — fremtidigt felt


def test_access_ticket_id_is_unique(db_session):
    now = database.now_utc()

    def _make(ticket_id):
        return database.AccessTicket(
            ticket_id=ticket_id, agent="codex", machine="prod-mini",
            valid_from=now, valid_until=now + timedelta(hours=1), granted_by="peter",
        )

    db_session.add(_make("AT-DUP-0001"))
    db_session.commit()
    db_session.add(_make("AT-DUP-0001"))
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_access_ticket_supports_revocation_fields(db_session):
    """§5 punkt 6 (tidlig tilbagekaldelse) — modellen skal kunne repræsentere en
    revoked-status uden at kræve udløb (tid-baseret, IKKE godkendelses-baseret)."""
    now = database.now_utc()
    ticket = database.AccessTicket(
        ticket_id="AT-REVOKED-0001", agent="claude", machine="staging",
        valid_from=now, valid_until=now + timedelta(hours=4), granted_by="peter",
    )
    db_session.add(ticket)
    db_session.commit()

    ticket.status = "revoked"
    ticket.revoked_at = database.now_utc()
    ticket.revoked_by = "peter"
    ticket.revoked_reason = "Session afsluttet tidligere end planlagt"
    db_session.commit()

    fetched = db_session.query(database.AccessTicket).filter_by(ticket_id="AT-REVOKED-0001").first()
    assert fetched.status == "revoked"
    assert fetched.revoked_by == "peter"


# ── KeyCredential key_type="mtls_device_cert" (#52 skema) ───────────────────────

def test_mtls_device_cert_credential_can_be_created_and_queried(db_session):
    metadata = {
        "serial_number": "01A2B3C4",
        "not_before": "2026-07-06T00:00:00Z",
        "issuer_cn": "TimeLapse Issuing CA",
        "lifetime_days_at_issuance": 3650,
        "expiry_grace_policy_at_issuance": "block",
    }
    cred = database.KeyCredential(
        credential_id="TL-KEY-20260706-devicecert01",
        entity_type="edge",
        entity_id="TL-C87FF9587CA0",
        key_type="mtls_device_cert",
        label="Device mTLS-certifikat",
        status="active",
        public_key="-----BEGIN CERTIFICATE-----\n...",
        fingerprint="SHA256:abcdef1234567890",
        algorithm="ECDSA-P256",
        metadata_json=json.dumps(metadata),
    )
    db_session.add(cred)
    db_session.commit()

    fetched = db_session.query(database.KeyCredential).filter_by(
        entity_type="edge", entity_id="TL-C87FF9587CA0", key_type="mtls_device_cert",
    ).first()
    assert fetched is not None
    assert fetched.status == "active"
    assert fetched.algorithm == "ECDSA-P256"
    parsed_meta = json.loads(fetched.metadata_json)
    assert parsed_meta["serial_number"] == "01A2B3C4"
    assert parsed_meta["lifetime_days_at_issuance"] == 3650


def test_mtls_device_cert_lifecycle_states_match_existing_status_vocabulary(db_session):
    """§7: udstedelse->active, rotation->rotated, udløb->expired, revokering->revoked
    — samme `status`-vokabular som allerede understøttes for api/ssh/signing, ingen
    ny statusværdi krævet."""
    cred = database.KeyCredential(
        credential_id="TL-KEY-20260706-devicecert02",
        entity_type="edge", entity_id="TL-DEVICE-002",
        key_type="mtls_device_cert", status="active",
    )
    db_session.add(cred)
    db_session.commit()

    cred.status = "rotated"
    cred.rotated_from_id = "TL-KEY-20260706-devicecert02"
    db_session.commit()
    assert cred.status == "rotated"

    cred.status = "revoked"
    cred.revoked_at = database.now_utc()
    cred.revoked_by = "system:crl"
    cred.revoke_reason = "Device fysisk kompromitteret (R05)"
    db_session.commit()
    assert cred.status == "revoked"
    assert cred.revoke_reason == "Device fysisk kompromitteret (R05)"


def test_key_scopes_knows_mtls_device_cert():
    assert main._key_scopes("mtls_device_cert") == ["device:mtls-auth"]


def test_key_scopes_unknown_type_still_returns_empty_list_not_crash():
    """Regressionsværn: _key_scopes() må aldrig kaste en exception for en ukendt
    key_type — samme robusthed skal gælde efter denne udvidelse som før."""
    assert main._key_scopes("noget-helt-ukendt") == []
