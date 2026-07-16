from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from backup_integrity import publish_tar_gzip_atomically, validate_plain_pg_dump


def test_rejects_truncated_postgres_dump(tmp_path):
    dump = tmp_path / "db.sql.partial"
    dump.write_bytes(b"CREATE TABLE example(id int);\n" * 100)
    with pytest.raises(RuntimeError, match="completion-marker"):
        validate_plain_pg_dump(dump)


def test_validates_complete_postgres_dump(tmp_path):
    dump = tmp_path / "db.sql.partial"
    dump.write_bytes(b"CREATE TABLE example(id int);\n" * 100 + b"-- PostgreSQL database dump complete\n")
    evidence = validate_plain_pg_dump(dump)
    assert evidence["bytes"] == dump.stat().st_size
    assert len(evidence["sha256"]) == 64


def test_archive_is_published_without_partial_file(tmp_path):
    source = tmp_path / "backup-stage"
    source.mkdir()
    (source / "BACKUP_MANIFEST.json").write_text('{"schema":"test"}')
    final = tmp_path / "backup.tar.gz"
    evidence = publish_tar_gzip_atomically(source, final)
    assert final.is_file()
    assert not (tmp_path / ".backup.tar.gz.partial").exists()
    assert evidence["bytes"] == final.stat().st_size
