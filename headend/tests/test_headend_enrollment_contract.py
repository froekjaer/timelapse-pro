from pathlib import Path


MAIN = Path(__file__).resolve().parents[1] / "main.py"


def test_enrollment_supports_explicit_headend_credentials():
    source = MAIN.read_text(encoding="utf-8")

    assert 'node_type:       Literal["edge", "headend"] = "edge"' in source
    assert "entity_type=req.node_type" in source
    assert '"node_type":        req.node_type' in source
    assert source.count('api_token = f"tk-{_secrets.token_urlsafe(32)}"') >= 2
    assert "strftime('%Y%m%d%H%M%S')" not in source[source.index("def enroll_device("):source.index("def list_unassigned_devices(")]


def test_inventory_ingest_requires_device_auth():
    source = MAIN.read_text(encoding="utf-8")
    route = source[source.index('@app.post("/api/inventory/{device_id}")'):]
    route = route[: route.index("\n\n@app.get", 1)]

    assert "Depends(_verify_device_token)" in route
