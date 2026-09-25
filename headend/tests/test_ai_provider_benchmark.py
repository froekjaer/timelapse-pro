from __future__ import annotations

import importlib.util
from pathlib import Path


HEADEND_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = HEADEND_DIR / "tools" / "compare_ai_providers.py"


def _benchmark_module():
    spec = importlib.util.spec_from_file_location("compare_ai_providers_test", BENCHMARK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readonly_vocabulary_loader_never_commits():
    from ai.tag_vocabulary import load_approved_vocabulary_readonly

    state = {"closed": False, "execute": 0}

    class Result:
        def fetchall(self):
            return [
                ("roof", "structures"),
                ("person_visible", "gdpr_safe"),
            ]

    class FakeDB:
        def execute(self, _statement):
            state["execute"] += 1
            return Result()

        def commit(self):
            raise AssertionError("read-only vocabulary loader must not commit")

    db = FakeDB()

    def get_db():
        try:
            yield db
        finally:
            state["closed"] = True

    by_category, approved = load_approved_vocabulary_readonly(get_db)

    assert by_category == {
        "structures": ["roof"],
        "gdpr_safe": ["person_visible"],
    }
    assert approved == {"roof", "person_visible"}
    assert state["execute"] == 1
    assert state["closed"] is True


def test_benchmark_predefined_vocabulary_is_nonempty():
    benchmark = _benchmark_module()
    by_category, approved, meta = benchmark._load_vocabulary_context("predefined", None)

    assert by_category
    assert approved
    assert meta["effective_source"] == "predefined"
    assert meta["tag_count"] == len(approved)


def test_benchmark_auto_fallback_does_not_expose_exception_text():
    benchmark = _benchmark_module()

    def failing_db():
        raise RuntimeError("do-not-leak-this-secret-like-value")

    by_category, approved, meta = benchmark._load_vocabulary_context("auto", failing_db)

    assert by_category
    assert approved
    assert meta["effective_source"] == "predefined"
    assert meta["fallback_reason"] == "RuntimeError"
    assert "do-not-leak" not in str(meta)


def test_benchmark_uses_shared_authoritative_gemini_config():
    source = BENCHMARK_PATH.read_text(encoding="utf-8")
    integration_source = (HEADEND_DIR / "ai" / "integration.py").read_text(encoding="utf-8")

    assert "from ai.provider_config import build_gemini_vision_service" in source
    assert "from ai.provider_config import build_gemini_vision_service" in integration_source
    assert "--vocabulary-source" in source
    assert "benchmark_version\": 3" in source
