from pathlib import Path


def test_main_delegates_edge_mtls_identity_to_api_boundary():
    main_source = Path("headend/main.py").read_text(encoding="utf-8")
    api_source = Path("headend/api/edge_api_mtls_api.py").read_text(encoding="utf-8")

    assert "enforce_edge_api_mtls_identity(" in main_source
    assert "verify_edge_api_mtls_identity(" not in main_source
    assert "verify_edge_api_mtls_identity(" in api_source
    assert "allow_legacy_enrollment=" in api_source
