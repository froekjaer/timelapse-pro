from __future__ import annotations

from pathlib import Path

from ai.tag_vocabulary import TagVocabulary


HEADEND_DIR = Path(__file__).resolve().parents[1]


def _fake_vocab(captured_params: list[dict]):
    class FakeDB:
        def execute(self, _statement, params=None):
            if params is not None:
                captured_params.append(dict(params))

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    db = FakeDB()

    def get_db():
        yield db

    vocab = object.__new__(TagVocabulary)
    vocab._get_db = get_db
    return vocab


def test_translation_source_tracks_provider_when_ai_translation_exists():
    captured: list[dict] = []
    vocab = _fake_vocab(captured)

    vocab.record_usage(
        [],
        ["new_site_object"],
        {"new_site_object": "nyt byggeobjekt"},
        translation_source="apple_foundation",
    )

    insert_params = captured[-1]
    assert insert_params["status"] == "ai_suggested"
    assert insert_params["source"] == "apple_foundation"


def test_translation_source_is_system_when_translation_is_pending():
    captured: list[dict] = []
    vocab = _fake_vocab(captured)

    vocab.record_usage(
        [],
        ["new_site_object"],
        {},
        translation_source="ollama",
    )

    insert_params = captured[-1]
    assert insert_params["status"] == "pending"
    assert insert_params["source"] == "system"


def test_apple_raw_response_is_preserved_before_adapter_mutation():
    source = (HEADEND_DIR / "ai" / "apple_foundation_service.py").read_text(encoding="utf-8")

    assert "provider_response = asdict(generated)" in source
    assert "parsed = deepcopy(provider_response)" in source
    assert '"response": provider_response' in source
    assert '"adapter_response": parsed' in source


def test_worker_records_provider_specific_vocabulary_provenance():
    source = (HEADEND_DIR / "ai" / "integration.py").read_text(encoding="utf-8")

    assert '"apple_foundation" if provider_used == "apple" else provider_used' in source
    assert 'payload["provider"] = provider_used' in source
    assert 'translation_source=translation_source' in source
    assert '"apple_foundation" if provider_used == "apple" else provider_used' in source
