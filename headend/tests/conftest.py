"""Global safety boundary for Headend unit/contract tests."""
from __future__ import annotations

import os
import sys
# Must run before test modules import database.py. Individual legacy modules use
# setdefault(), which is unsafe when launchd/shell already exports the live URL.
os.environ["DATABASE_URL"] = os.getenv(
    "TIMELAPSE_TEST_DATABASE_URL",
    "postgresql://timelapse@localhost/timelapse_test",
)
os.environ["TIMELAPSE_ENV"] = "test"

# Keep timelapse_test's schema current the same way timelapse_db is kept
# current: by running the app's own additive migrations
# (main.py::startup(), plus commissioning_key.py/technician_keys.py/cmdb.py's
# migrate_*() helpers it calls). Production gets this for free on every
# Headend boot; pytest never boots the ASGI app (no test here uses
# TestClient), so without this call a timelapse_test created before some
# later ADD COLUMN migration was written stays permanently behind it —
# exactly the drift previously hit with users.field_role (see
# Dokumentation/HANDOVER_LOG.md, 2026-08-19/21) and, locally, with
# devices.commissioning_key_disabled and cameras.reported_model. All of
# startup()'s migration blocks are try/except-per-statement idempotent, and
# background_jobs_enabled() (TIMELAPSE_ENV=test, set above) keeps it from
# starting any thread or touching anything outside this DB.
HERE = os.path.dirname(os.path.abspath(__file__))
_HEADEND_ROOT = os.path.dirname(HERE)
if _HEADEND_ROOT not in sys.path:
    sys.path.insert(0, _HEADEND_ROOT)
import main as _main  # noqa: E402

_main.startup()
