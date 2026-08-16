from pathlib import Path


def _method_slice(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}(")
    end = source.index(f"    def {next_name}(", start)
    return source[start:end]


def test_edge_backup_upload_uses_retry_aware_session():
    source = Path("edge/upload/headend_client.py").read_text(encoding="utf-8")
    method = _method_slice(source, "upload_edge_backup", "notify_tunnel_ready")
    assert "session = _build_session(self._cfg_mgr.api_token)" in method
    assert "session = requests.Session()" not in method
    assert 'session.headers.pop("Content-Type", None)' in method


def test_ping_does_not_duplicate_api_prefix():
    source = Path("edge/upload/headend_client.py").read_text(encoding="utf-8")
    method = _method_slice(source, "ping", "_post")
    assert 'f"{self._base_url}/health"' in method
    assert 'f"{self._base_url}/api/health"' not in method
