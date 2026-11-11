from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import siem


ROOT = Path(__file__).parents[1]
SIEM_SOURCE = (ROOT / "headend" / "siem.py").read_text(encoding="utf-8")


def test_launchd_pre_reboot_noise_is_narrowly_downgraded() -> None:
    noise = siem._normalize_event({
        "event_type": "service_crash",
        "severity": "critical",
        "raw_message": (
            "2026-11-11 03:00:05.738622+0100 localhost launchd[1]: "
            "pre-reboot: non-boot task posix_spawn() failed: 2: "
            "No such file or directory"
        ),
    })
    assert noise["event_type"] == "planned_reboot_launchd_noise"
    assert noise["severity"] == "info"
    assert noise["category"] == "maintenance"


def test_real_service_crash_remains_critical() -> None:
    event = siem._normalize_event({
        "event_type": "service_crash",
        "severity": "critical",
        "raw_message": "timelapse-headend exited with status 1",
    })
    assert event["event_type"] == "service_crash"
    assert event["severity"] == "critical"
    assert event["category"] == "security"


def test_launchd_fragments_embedded_in_another_failure_are_not_downgraded() -> None:
    event = siem._normalize_event({
        "event_type": "service_crash",
        "severity": "critical",
        "raw_message": (
            "application failed; launchd[1]: pre-reboot: non-boot task "
            "posix_spawn() failed: 2: No such file or directory"
        ),
    })
    assert event["event_type"] == "service_crash"
    assert event["severity"] == "critical"


def test_notifications_only_iterate_newly_inserted_batch_members() -> None:
    start = SIEM_SOURCE.index("async def ingest_events(")
    end = SIEM_SOURCE.index("return result", start)
    section = SIEM_SOURCE[start:end]

    assert 'for event_index in result.get("inserted_indexes", [])' in section
    assert "ev = events[event_index]" in section
    assert "for ev in events:" not in section


def test_duplicate_savepoint_cannot_rollback_prior_batch_inserts() -> None:
    start = SIEM_SOURCE.index("def record_events(")
    end = SIEM_SOURCE.index("\n\ndef prune_old_events", start)
    section = SIEM_SOURCE[start:end]

    assert "with db.begin_nested():" in section
    assert "db.rollback()" not in section
    assert '"inserted_indexes": inserted_indexes' in section


def test_mixed_replay_batch_reports_only_the_new_row(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    siem.SecurityEvent.__table__.create(engine)
    monkeypatch.setattr(siem, "_ensure_schema", lambda _db: None)
    duplicate = {
        "event_type": "service_crash",
        "severity": "critical",
        "occurred_at": "2026-11-11T03:00:05+01:00",
        "raw_message": "real failure A",
    }
    fresh = {
        "event_type": "service_crash",
        "severity": "critical",
        "occurred_at": "2026-11-11T03:00:06+01:00",
        "raw_message": "real failure B",
    }

    with Session(engine) as db:
        first = siem.record_events(db, "HEADEND", [duplicate])
        replay = siem.record_events(db, "HEADEND", [duplicate, fresh])
        count = db.scalar(select(func.count()).select_from(siem.SecurityEvent))

    assert first == {
        "inserted": 1, "duplicates": 0, "errors": 0, "inserted_indexes": [0]
    }
    assert replay == {
        "inserted": 1, "duplicates": 1, "errors": 0, "inserted_indexes": [1]
    }
    assert count == 2


def test_launchd_managed_scripts_do_not_double_append_their_output() -> None:
    for relative in (
        "deploy/scripts/timelapse-nightly-maintenance",
        "deploy/scripts/timelapse-post-reboot-verify",
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert "tee -a" not in script
