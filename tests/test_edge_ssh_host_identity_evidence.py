from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_headend_ssh_host_identity_report_is_device_authenticated_and_bound():
    source = (ROOT / "headend/api/ssh_host_identity_api.py").read_text(encoding="utf-8")
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    block = source.split('def report_ssh_host_identity(', 1)[1]

    assert 'router.post("/ssh-host-identity/{device_id}")' in source
    assert "create_ssh_host_identity_router(_verify_device_token, get_db, now_utc)" in main
    assert "_auth: None = Depends(verify_device_token)" in block
    assert "if req.device_id != device_id" in block
    assert "evidence device_id mismatch" in block
    assert "authenticated_edge_report" in block


def test_headend_ssh_host_identity_report_is_evidence_not_trust_mutation():
    source = (ROOT / "headend/api/ssh_host_identity_api.py").read_text(encoding="utf-8")
    block = source.split('def report_ssh_host_identity(', 1)[1]

    assert "EdgeSshHostIdentityEvidence(" in block
    assert 'trusted_state="untrusted_observed"' in block
    assert "known_hosts =" not in block
    assert "ssh-keygen -R" not in block
    assert "StrictHostKeyChecking" not in block


def test_migration_creates_read_only_evidence_store():
    migration = (ROOT / "headend/migrations/v31_edge_ssh_host_identity_evidence.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS edge_ssh_host_identity_evidence" in migration
    assert "evidence_source" in migration
    assert "trusted_state" in migration
    assert "untrusted_observed" in migration
    assert "ssh-keygen" not in migration.lower()


def test_edge_agent_reports_ssh_host_identity_over_authenticated_client():
    agent = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    client = (ROOT / "edge/upload/headend_client.py").read_text(encoding="utf-8")

    assert "trust.ssh_host_identity" in agent
    assert "report_ssh_host_identity" in agent
    assert "def report_ssh_host_identity" in client
    assert '"/trust/ssh-host-identity/{self._device_id}"' in client
