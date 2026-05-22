"""
TimeLapse Pro — System Settings Helper
Læser/skriver system_settings tabellen.
Bruges af backfill, ai_router og headend til at hente API-nøgler fra DB.
"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import text


def _ensure_table(db):
    """Opret system_settings hvis den ikke findes (SQLite + PostgreSQL)."""
    try:
        from sqlalchemy import text
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                is_secret BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        """))
        db.commit()
    except Exception:
        db.rollback()


def get_setting(db, key: str, default: str = "") -> str:
    """Hent én indstilling fra system_settings."""
    _ensure_table(db)
    try:
        row = db.execute(
            text("SELECT value FROM system_settings WHERE key = :k"),
            {"k": key}
        ).fetchone()
        return row[0] if row and row[0] else default
    except Exception:
        return default


def set_setting(db, key: str, value: str, updated_by: str = "system"):
    """Gem én indstilling i system_settings."""
    db.execute(text("""
        INSERT INTO system_settings (key, value, updated_by, updated_at)
        VALUES (:k, :v, :by, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_by = EXCLUDED.updated_by,
            updated_at = NOW()
    """), {"k": key, "v": value, "by": updated_by})
    db.commit()


def get_all_settings(db) -> list[dict]:
    """Hent alle indstillinger (til UI — secrets maskeres)."""
    _ensure_table(db)
    rows = db.execute(text("""
        SELECT key, value, description, is_secret, updated_at, updated_by
        FROM system_settings
        ORDER BY key
    """)).mappings().all()
    return [{
        "key":         r["key"],
        "value":       "••••••••" if r["is_secret"] and r["value"] else r["value"],
        "description": r["description"],
        "is_secret":   r["is_secret"],
        "updated_at":  str(r["updated_at"]) if r["updated_at"] else None,
        "updated_by":  r["updated_by"],
    } for r in rows]
