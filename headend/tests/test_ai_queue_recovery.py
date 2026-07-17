from ai import integration


def test_recover_pending_captures_requeues_database_ids(monkeypatch):
    class _Query:
        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def limit(self, value):
            assert value == 50
            return self

        def all(self):
            return [(7,), (11,), (19,)]

    class _Db:
        def query(self, *_args):
            return _Query()

    def get_db():
        yield _Db()

    queued = []
    monkeypatch.setattr(
        integration,
        "queue_capture_for_analysis",
        lambda capture_id: queued.append(capture_id) is None,
    )

    recovered = integration.recover_pending_captures(get_db, limit=50)

    assert recovered == 3
    assert queued == [7, 11, 19]
