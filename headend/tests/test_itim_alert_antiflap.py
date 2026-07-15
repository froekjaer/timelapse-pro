from datetime import datetime, timedelta, timezone

from itim import _breach_sustained


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _DB:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return _Rows(self.rows)


def test_single_high_sample_does_not_satisfy_duration(monkeypatch):
    monkeypatch.setattr("itim._now", lambda: NOW)
    db = _DB([(93.0, NOW - timedelta(seconds=5))])
    assert _breach_sustained(db, 1, "mem_pct", lambda a, b: a > b, 92, 60) is False


def test_continuous_breach_fires_after_duration(monkeypatch):
    monkeypatch.setattr("itim._now", lambda: NOW)
    db = _DB([
        (94.0, NOW - timedelta(seconds=5)),
        (93.0, NOW - timedelta(seconds=35)),
        (92.5, NOW - timedelta(seconds=65)),
        (80.0, NOW - timedelta(seconds=95)),
    ])
    assert _breach_sustained(db, 1, "mem_pct", lambda a, b: a > b, 92, 60) is True


def test_non_breach_breaks_the_continuous_window(monkeypatch):
    monkeypatch.setattr("itim._now", lambda: NOW)
    db = _DB([
        (94.0, NOW - timedelta(seconds=5)),
        (90.0, NOW - timedelta(seconds=35)),
        (94.0, NOW - timedelta(seconds=95)),
    ])
    assert _breach_sustained(db, 1, "mem_pct", lambda a, b: a > b, 92, 60) is False
