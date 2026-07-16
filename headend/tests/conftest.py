"""Global safety boundary for Headend unit/contract tests."""
from __future__ import annotations

import os
# Must run before test modules import database.py. Individual legacy modules use
# setdefault(), which is unsafe when launchd/shell already exports the live URL.
os.environ["DATABASE_URL"] = os.getenv(
    "TIMELAPSE_TEST_DATABASE_URL",
    "postgresql://timelapse@localhost/timelapse_test",
)
os.environ["TIMELAPSE_ENV"] = "test"
