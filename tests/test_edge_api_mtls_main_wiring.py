from pathlib import Path


def test_main_calls_edge_mtls_identity_verifier():
    source = Path("headend/main.py").read_text(encoding="utf-8")
    assert "verify_edge_api_mtls_identity(" in source
    assert "allow_legacy_enrollment=" in source
