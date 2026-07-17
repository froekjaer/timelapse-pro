from ai import model_results


def test_extract_edge_payload_accepts_legacy_and_nested_shapes():
    legacy = {"source": "edge", "engine": "edge_cv_v1", "passed": True}
    nested = {"model": "qwen2.5vl:7b", "edge_ai": legacy}

    assert model_results.extract_edge_payload(legacy) is legacy
    assert model_results.extract_edge_payload(nested) is legacy
    assert model_results.extract_edge_payload({"engine": "local"}) is None


def test_upsert_edge_capture_results_separates_cv_and_npu(monkeypatch):
    calls = []

    def fake_upsert(_db, **kwargs):
        calls.append(kwargs)
        return len(calls)

    monkeypatch.setattr(model_results, "upsert_capture_model_result", fake_upsert)
    payload = {
        "source": "edge",
        "engine": "edge_cv_v1",
        "confidence": "0.82",
        "autonomous_optimizer": {"tags": ["clear_image", "daylight"]},
        "npu": {
            "engine": "edge_npu_contract_cpu_fallback",
            "available": False,
            "confidence": 0.61,
            "tags": ["clear_image"],
        },
    }

    row_ids = model_results.upsert_edge_capture_results(
        object(), capture_id=42, payload=payload, source="edge_file_upload"
    )

    assert row_ids == [1, 2]
    assert calls[0]["engine"] == model_results.ENGINE_EDGE_CV
    assert calls[0]["model"] == "edge_cv_v1"
    assert calls[0]["tags"] == ["clear_image", "daylight"]
    assert calls[0]["confidence"] == 0.82
    assert calls[1]["engine"] == model_results.ENGINE_EDGE_NPU
    assert calls[1]["model"] == "edge_npu_contract_cpu_fallback"
    assert calls[1]["result_json"]["available"] is False


def test_upsert_edge_capture_results_ignores_headend_only_payload(monkeypatch):
    monkeypatch.setattr(
        model_results,
        "upsert_capture_model_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected write")),
    )

    assert model_results.upsert_edge_capture_results(
        object(),
        capture_id=7,
        payload={"engine": "local", "model": "qwen2.5vl:7b"},
        source="legacy_backfill",
    ) == []
