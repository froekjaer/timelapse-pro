"""Regression test (2026-08-06): timelapse video rendering silently 404'ed for
every camera location whose captures use a mixed-case device_id (the
"TL-IMPORT-{Customer}-{Site}-{Camera}" virtual devices headend/importer.py
creates for historical image imports — see headend/importer.py:492-523).

Root cause: _sanitize_device_id() force-uppercases its input (correct for real,
MAC-derived hardware IDs like TL-C87FF9587CA0, which are always already
uppercase). create_timelapse() was the only caller in headend/main.py that
reassigned device_id to that uppercased return value before using it in an
exact-match Postgres query (Capture.device_id == device_id) — Postgres string
comparison is case-sensitive, so this silently matched zero captures for any
mixed-case device_id and raised a misleading "images not found" 404, even
though the images existed. get_thumbnail()/get_timelapse_frames() were
already correct: they call _sanitize_device_id() only to validate format,
then continue using the original, un-mangled device_id string.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def test_create_timelapse_does_not_reassign_device_id_to_the_uppercased_sanitize_result() -> None:
    start = MAIN.index("def create_timelapse(")
    end = MAIN.index("\n@app.", start + 1)
    section = MAIN[start:end]

    assert "_sanitize_device_id(payload.get(\"device_id\"))" in section, (
        "create_timelapse must still validate the device_id format/reject path traversal"
    )
    assert "device_id  = _sanitize_device_id(payload.get(\"device_id\"))" not in section, (
        "create_timelapse must NOT use the uppercased _sanitize_device_id() return value for "
        "the capture lookup — mixed-case virtual import device_ids (TL-IMPORT-...) would silently "
        "match zero captures against the case-sensitive Postgres comparison, producing a "
        "misleading 404 even though the images exist. Validate the format, then use the "
        "original device_id string, exactly like get_thumbnail()/get_timelapse_frames() already do."
    )
