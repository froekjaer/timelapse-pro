"""resolution_reason field + target/parent status harmonization on (re-)block.

Diagnosed 2026-09-01 (Dokumentation/UPDATE_GOVERNANCE_DIAGNOSIS_2026-09-01.md):
live PendingUpdate rows could sit at status="blocked" while their UpdateTarget
rows stayed "queued" (set while briefly approved), because nothing reset the
target when cmdb.py's inventory sync flipped the parent back to blocked. These
tests cover the shared cascade helpers directly (behavioural) and confirm the
call sites that must invoke them are present (contract, matching this repo's
existing style for headend/main.py and headend/cmdb.py).
"""

from pathlib import Path
from types import SimpleNamespace

from headend.services.update_supersession import (
    close_targets_for_superseded_updates,
    reset_stale_targets_on_block,
)


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        return self

    def all(self):
        return self.rows


class Db:
    def __init__(self, targets):
        self.targets = targets

    def query(self, model):
        return Query(self.targets)


class Column:
    def in_(self, values):
        return True

    def __eq__(self, other):
        return True


class TargetModel:
    pending_update_id = device_id = status = Column()


def _target(**kwargs):
    defaults = dict(
        pending_update_id=1,
        device_id="TL-1",
        status="queued",
        last_error=None,
        completed_at=None,
        last_report_at=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_reset_stale_targets_on_block_moves_queued_target_to_failed():
    target = _target(status="queued")
    moved = reset_stale_targets_on_block(Db([target]), TargetModel, 1, "Parent update blocked.")
    assert moved == 1
    assert target.status == "failed"
    assert target.last_error.endswith("Parent update blocked.")
    assert target.completed_at is not None
    assert target.last_report_at is not None


def test_reset_stale_targets_on_block_leaves_terminal_target_alone():
    target = _target(status="deployed")
    moved = reset_stale_targets_on_block(Db([target]), TargetModel, 1, "Parent update blocked.")
    assert moved == 0
    assert target.status == "deployed"


def test_close_targets_for_superseded_updates_moves_active_targets():
    target = _target(status="approved")
    moved = close_targets_for_superseded_updates(
        Db([target]), TargetModel, [1], "Superseded by CMDB inventory.", device_id="TL-1",
    )
    assert moved == 1
    assert target.status == "superseded"


def test_cmdb_reblock_sites_reset_stale_targets():
    source = _source("headend/cmdb.py")
    app_block = source[
        source.index("def _sync_managed_application_updates("):source.index("def _sync_edge_os_updates(")
    ]
    os_block = source[
        source.index("def _sync_edge_os_updates("):source.index("\n\n# ── Kryptering")
    ]
    assert "reset_stale_targets_on_block(" in app_block
    assert 'exists.status = "blocked"' in app_block
    assert "reset_stale_targets_on_block(" in os_block
    assert 'existing.status = "blocked"' in os_block


def test_app_update_reblock_sets_resolution_reason_even_when_already_blocked():
    """Regression: an already-blocked row (not just the pending/approved -> blocked
    transition) must also get resolution_reason set on every re-sync — otherwise a row
    blocked before this field existed stays NULL forever, since CMDB re-observes the
    same outdated package as still-blocked, not as a fresh transition. Shipped once
    without this (2026-09-03): #228/#230/#231 self-healed their targets on the next
    sync but resolution_reason stayed NULL.
    """
    source = _source("headend/cmdb.py")
    app_block = source[
        source.index("def _sync_managed_application_updates("):source.index("def _sync_edge_os_updates(")
    ]
    reblock = app_block[app_block.index("if exists.status in"):]
    assert 'if exists.status == "blocked":' in reblock
    assert "exists.resolution_reason = " in reblock
    # resolution_reason assignment must be reachable outside the pending/approved-only
    # transition branch, not nested inside it.
    transition_branch = reblock[reblock.index('if exists.status in'):reblock.index('if exists.status == "blocked":')]
    assert "exists.resolution_reason" not in transition_branch


def test_cmdb_supersession_cascades_to_targets():
    source = _source("headend/cmdb.py")
    block = source[
        source.index("def _supersede_active_device_updates("):source.index("def _parse_version_gap(")
    ]
    assert "close_targets_for_superseded_updates(" in block


def test_pending_update_has_resolution_reason_column():
    source = _source("headend/database.py")
    block = source[source.index("class PendingUpdate("):source.index("class ChangeTicket(")]
    assert "resolution_reason" in block


def test_missing_artifact_withheld_update_resets_stale_target():
    source = _source("headend/main.py")
    assert "reset_stale_targets_on_block(" in source
    assert "from services.update_supersession import" in source
    import_line = next(
        line for line in source.splitlines() if line.startswith("from services.update_supersession import")
    )
    assert "reset_stale_targets_on_block" in import_line
