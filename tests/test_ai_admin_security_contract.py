"""Regression contracts for internet-exposed AI administration routes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vocabulary_and_review_routers_require_admin_role():
    source = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    assert 'app.include_router(vocab_router, dependencies=[require_role("super_admin", "admin")])' in source
    assert 'app.include_router(_rev_router, dependencies=[require_role("super_admin", "admin")])' in source


def test_tag_translations_remain_available_to_authenticated_viewers():
    main_source = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    routes_source = (ROOT / "headend/ai/vocabulary_routes.py").read_text(encoding="utf-8")
    assert 'app.include_router(vocab_read_router, dependencies=[require_role("viewer")])' in main_source
    assert '@vocab_read_router.get("/translations")' in routes_source


def test_similarity_normalizer_is_an_instance_method():
    source = (ROOT / "headend/ai/repositories.py").read_text(encoding="utf-8")
    assert "def _normalize_tag_for_similarity(self, tag: str)" in source
