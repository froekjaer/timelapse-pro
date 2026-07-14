from pathlib import Path

from edge.ai.site_look_manager import _edge_storage_path


def test_legacy_site_look_path_maps_to_persistent_edge_volume():
    assert _edge_storage_path("/var/lib/timelapse/site_looks") == Path(
        "/data/timelapse/site_looks"
    )


def test_explicit_nonlegacy_site_look_path_is_preserved():
    assert _edge_storage_path("/custom/site-looks") == Path("/custom/site-looks")
