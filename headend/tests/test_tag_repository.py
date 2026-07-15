from ai.repositories import TagRepository


class _Mappings:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _DB:
    def execute(self, *_args, **_kwargs):
        return _Mappings([
            {"id": 1, "tag": "clear_sky", "category": "weather", "count": 12, "approved": True, "rejected": False},
            {"id": 2, "tag": "clear_skies", "category": "weather", "count": 4, "approved": False, "rejected": False},
            {"id": 3, "tag": "construction_crane", "category": "objects", "count": 8, "approved": True, "rejected": False},
        ])


def test_similar_tag_suggestions_runs_without_bound_method_typeerror():
    result = TagRepository(_DB()).get_similar_tag_suggestions(threshold=0.6)
    assert result
    assert result[0]["canonical_tag"] == "clear_sky"
    assert {tag["tag"] for tag in result[0]["tags"]} == {"clear_sky", "clear_skies"}
