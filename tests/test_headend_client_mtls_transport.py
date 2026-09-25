from pathlib import Path


def test_headend_client_transport_has_single_session_factory():
    source = Path("edge/upload/headend_client.py").read_text(encoding="utf-8")
    assert source.count("requests.Session()") == 1
    assert "requests.post(" not in source


def test_mtls_enrollment_keeps_separate_recovery_session():
    source = Path("edge/upload/headend_client.py").read_text(encoding="utf-8")
    start = source.index("    def _post(")
    end = source.index("    def download_artifact_file(", start)
    method = source[start:end]
    assert "/trust/headend-api-mtls/" in method
    assert "self._legacy_session" in method
    assert "else self._session" in method
