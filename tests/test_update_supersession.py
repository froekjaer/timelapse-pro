"""Unit tests for signed release candidate supersession."""

from types import SimpleNamespace

from headend.services.update_supersession import supersede_pending_app_updates


class Query:
    def __init__(self, candidates):
        self.candidates = candidates

    def filter(self, *conditions):
        return self

    def all(self):
        return self.candidates


class Db:
    def __init__(self, candidates):
        self.candidates = candidates

    def query(self, model):
        return Query(self.candidates)


class Model:
    update_type = scope = scope_id = environment = status = version = SimpleNamespace()


def test_pending_candidates_are_superseded_with_evidence_note():
    older = SimpleNamespace(status="pending", description="Older signed release")
    count = supersede_pending_app_updates(Db([older]), Model, "TL-1", "new-commit")
    assert count == 1
    assert older.status == "superseded"
    assert older.description.endswith("Superseded by signed release new-commit.")


def test_empty_candidate_set_is_a_noop():
    assert supersede_pending_app_updates(Db([]), Model, "TL-1", "new-commit") == 0
