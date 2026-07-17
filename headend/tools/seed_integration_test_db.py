#!/usr/bin/env python3
"""Reset and seed the dedicated PostgreSQL integration-test database."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import bcrypt
from sqlalchemy import text


EXPECTED_DATABASE = "timelapse_test"


def _password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def main() -> None:
    database_url = os.environ.get("TIMELAPSE_TEST_DATABASE_URL", "")
    if urlparse(database_url).path.lstrip("/") != EXPECTED_DATABASE:
        raise SystemExit(
            "Refusing to seed anything except the dedicated timelapse_test database"
        )

    os.environ["DATABASE_URL"] = database_url
    os.environ["TIMELAPSE_ENV"] = "test"

    from database import (
        Base,
        Capture,
        ConfigDefaults,
        Customer,
        Device,
        SessionLocal,
        Site,
        User,
        engine,
    )

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        tables = connection.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
        """)).scalars().all()
        if tables:
            quoted = ", ".join(f'"{name}"' for name in tables)
            connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))

    db = SessionLocal()
    try:
        users = (
            ("admin", "TestAdmin123!", "super_admin"),
            ("test-super-admin", "TestSuperAdmin123!", "super_admin"),
            ("test-admin", "TestAdmin123!", "admin"),
            ("test-operator", "TestOperator123!", "operator"),
            ("test-viewer", "TestViewer123!", "viewer"),
            ("test-mfa-user", "TestMFA123!", "admin"),
        )
        for username, password, role in users:
            db.add(User(
                username=username,
                email=f"{username}@integration.invalid",
                password_hash=_password_hash(password),
                role=role,
                is_active=True,
                mfa_enabled=False,
                totp_secret=None,
            ))

        # Privileged test principals exercise authorization separately from MFA.
        # test-mfa-user is deliberately not exempt and owns the MFA workflow tests.
        db.add(ConfigDefaults(session_policy=json.dumps({
            "mfa_exempt_usernames": ["admin", "test-super-admin", "test-admin"],
        })))

        customer_id = "qa-integration-customer"
        site_id = "qa-integration-site"
        device_id = "TL-QA-INTEGRATION"
        db.add(Customer(id=customer_id, name="QA Integration Customer"))
        db.add(Site(id=site_id, customer_id=customer_id, name="QA Integration Site"))
        db.add(Device(
            device_id=device_id,
            customer_id=customer_id,
            site_id=site_id,
            customer_name="QA Integration Customer",
            site_name="QA Integration Site",
            camera_name="QA Integration Camera",
            status="online",
            last_seen=datetime.now(timezone.utc),
            device_config="{}",
        ))
        db.add(Capture(
            device_id=device_id,
            customer_id=customer_id,
            site_id=site_id,
            filename="qa-integration-capture.jpg",
            captured_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            uploaded=True,
            quality_passed=True,
            quality_flag="ok",
        ))
        db.commit()
    finally:
        db.close()

    print("Integration database reset and seeded")


if __name__ == "__main__":
    main()
