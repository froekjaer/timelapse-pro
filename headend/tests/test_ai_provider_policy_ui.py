from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
AI_PAGE = ROOT_DIR / "timelapse-ui" / "src" / "pages" / "AIPage.tsx"
POLICY_PANEL = ROOT_DIR / "timelapse-ui" / "src" / "components" / "AIProviderPolicyPanel.tsx"


def test_ai_page_uses_visual_provider_policy_editor():
    source = AI_PAGE.read_text(encoding="utf-8")

    assert "AIProviderPolicyPanel" in source
    assert "fields.filter(field => field.type === 'provider_order')" in source
    assert "fields.filter(field => field.type !== 'provider_order')" in source
    assert "/api/settings/ai-providers?probe=true" in source
    assert "const saveProviderPolicies = async () => {" in source
    assert "fields.filter(field => field.type === 'provider_order')" in source
    assert "onSave={saveProviderPolicies}" in source


def test_provider_policy_editor_supports_order_fallback_and_minimum_one_provider():
    source = POLICY_PANEL.read_text(encoding="utf-8")

    assert "Vælg hvilken provider hver tekst/structured-funktion prøver først" in source
    assert "Primær" in source
    assert "Fallback" in source
    assert "Flyt" in source
    assert "Tilføj fallback" in source
    assert "if (!next.length) return" in source
    assert "if (order.length <= 1) return" in source


def test_provider_policy_editor_has_all_supported_product_policies():
    source = POLICY_PANEL.read_text(encoding="utf-8")

    for setting_key in (
        "ai_provider_search_order",
        "ai_provider_siem_order",
        "ai_provider_aiops_order",
        "ai_provider_cmdb_order",
        "ai_provider_summarization_order",
    ):
        assert setting_key in source

    for provider in ("apple", "ollama", "gemini"):
        assert provider in source


def test_provider_policy_editor_surfaces_runtime_probe_state():
    source = POLICY_PANEL.read_text(encoding="utf-8")

    assert "Test forbindelser" in source
    assert "availability?.available" in source
    assert "Ikke tilgængelig" in source
    assert "Routeren fortsætter til næste fallback" in source
