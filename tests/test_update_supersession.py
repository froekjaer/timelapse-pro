"""Unit tests for signed release candidate supersession."""

from types import SimpleNamespace

from headend.services.update_supersession import supersede_pending_app_updates


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        return self

    def all(self):
        return self.rows


class Db:
    def __init__(self, updates, targets=None):
        self.updates = updates
        self.targets = targets or []

    def query(self, model):
        if model is TargetModel:
            return Query(self.targets)
        return Query(self.updates)


class Column:
    def in_(self, values):
        return True

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return True


class Model:
    update_type = scope = scope_id = environment = status = version = Column()


class TargetModel:
    pending_update_id = device_id = status = Column()


def test_pending_candidates_are_superseded_with_evidence_note():
    older = SimpleNamespace(id=1, status="pending", version="old-commit", description="Older signed release")
    count = supersede_pending_app_updates(Db([older]), Model, "TL-1", "new-commit")
    assert count == 1
    assert older.status == "superseded"
    assert older.description.endswith("Superseded by signed release new-commit.")


def test_approved_candidate_target_is_superseded_with_evidence_note():
    older = SimpleNamespace(id=2, status="approved", version="old-commit", description="Older signed release")
    target = SimpleNamespace(
        pending_update_id=2,
        device_id="TL-1",
        status="queued",
        last_error=None,
        completed_at=None,
        last_report_at=None,
    )
    count = supersede_pending_app_updates(
        Db([older], [target]),
        Model,
        "TL-1",
        "new-commit",
        target_model=TargetModel,
    )
    assert count == 1
    assert older.status == "superseded"
    assert target.status == "superseded"
    assert target.last_error.endswith("Superseded by signed release new-commit.")
    assert target.completed_at is not None
    assert target.last_report_at is not None


def test_blocked_candidate_is_superseded_with_evidence_note():
    blocked = SimpleNamespace(id=4, status="blocked", version="old-commit", description="Blocked older release")
    count = supersede_pending_app_updates(Db([blocked]), Model, "TL-1", "new-commit")
    assert count == 1
    assert blocked.status == "superseded"
    assert blocked.description.endswith("Superseded by signed release new-commit.")


def test_deployed_candidate_is_preserved():
    deployed = SimpleNamespace(id=3, status="deployed", version="old-commit", description="Already deployed")
    count = supersede_pending_app_updates(Db([deployed]), Model, "TL-1", "new-commit")
    assert count == 0
    assert deployed.status == "deployed"


def test_empty_candidate_set_is_a_noop():
    assert supersede_pending_app_updates(Db([]), Model, "TL-1", "new-commit") == 0
