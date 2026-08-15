"""
TimeLapse Pro — pytest konfiguration

Indeholder fixtures til integration tests med authenticated sessions.
"""
import os
import sys
from pathlib import Path

# Pytest resolves this repository through /Volumes/data-fast while operators use
# the stable /Users/peter/projects symlink. Put the canonical repository root on
# sys.path so package imports are independent of the entry path.
REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT, REPO_ROOT / "headend"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

# Establish the isolated database boundary before any test imports Headend
# modules. Integration tests may target a separately started test Headend only
# through an explicit TIMELAPSE_TEST_BASE_URL; fixtures must never mutate the
# operational timelapse_db directly.
os.environ["DATABASE_URL"] = os.getenv(
    "TIMELAPSE_TEST_DATABASE_URL",
    "postgresql://timelapse@localhost/timelapse_test",
)
os.environ.setdefault("TIMELAPSE_ENV", "test")

import pytest
import requests

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "").rstrip("/")
TEST_TARGET_ACK = os.getenv("TIMELAPSE_TEST_TARGET_ACK", "")
_REQUIRED_TEST_TARGET_ACK = "I_UNDERSTAND_THIS_IS_A_TEST_TARGET"


def require_explicit_test_target() -> str:
    """Return the integration-test target only after explicit operator opt-in.

    There is deliberately no localhost/port default. A missing variable must
    fail before any HTTP request so pytest cannot accidentally discover and
    exercise an operational Headend listening on a developer machine.
    """
    if not BASE_URL:
        raise RuntimeError(
            "Integration test target is unset; set TIMELAPSE_TEST_BASE_URL explicitly"
        )
    if not BASE_URL.startswith(("http://", "https://")):
        raise RuntimeError("TIMELAPSE_TEST_BASE_URL must be an absolute HTTP(S) URL")
    if TEST_TARGET_ACK != _REQUIRED_TEST_TARGET_ACK:
        raise RuntimeError(
            "Integration HTTP disabled; set TIMELAPSE_TEST_TARGET_ACK="
            + _REQUIRED_TEST_TARGET_ACK
        )
    return BASE_URL


# Test credentials — only valid in a deliberately prepared isolated test target.
TEST_CREDENTIALS = {
    "admin": {
        "username": "admin",
        "password": "TestAdmin123!"
    },
    "super_admin": {
        "username": "test-super-admin",
        "password": "TestSuperAdmin123!"
    },
    "viewer": {
        "username": "test-viewer",
        "password": "TestViewer123!"
    },
    "operator": {
        "username": "test-operator",
        "password": "TestOperator123!"
    }
}


class AuthenticatedSession:
    """Custom session that manually handles authentication cookies."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = require_explicit_test_target()
        self.session_token = None
        self._login()

    def _login(self):
        """Login og gem session token."""
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"Login fejlede: {response.status_code}")

        for cookie in response.cookies:
            if cookie.name == "tl_session":
                self.session_token = cookie.value
                break

        if not self.session_token:
            raise Exception("Ingen session token i login response")

    def request(self, method, path, **kwargs):
        """Make authenticated request."""
        # Re-evaluate the explicit gate before every network operation. This
        # prevents a test from mutating the module-global target after login.
        base_url = require_explicit_test_target()
        url = f"{base_url}{path}" if not path.startswith("http") else path

        headers = kwargs.pop("headers", {})
        headers["Cookie"] = f"tl_session={self.session_token}"

        return requests.request(method, url, headers=headers, timeout=kwargs.pop("timeout", 10), **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture(scope="session")
def admin_session():
    """Authenticated session med admin adgang (bruger operator rolle)."""
    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["operator"]["username"],
            TEST_CREDENTIALS["operator"]["password"]
        )
    except Exception as e:
        pytest.skip(f"Kunne ikke oprette admin session: {e}")


@pytest.fixture(scope="session")
def viewer_session():
    """Authenticated session med viewer rolle."""
    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["viewer"]["username"],
            TEST_CREDENTIALS["viewer"]["password"]
        )
    except Exception as e:
        pytest.skip(f"Kunne ikke oprette viewer session: {e}")


@pytest.fixture(scope="session")
def operator_session():
    """Authenticated session med operator rolle."""
    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["operator"]["username"],
            TEST_CREDENTIALS["operator"]["password"]
        )
    except Exception as e:
        pytest.skip(f"Kunne ikke oprette operator session: {e}")


@pytest.fixture(scope="session")
def super_admin_session():
    """Authenticated session med super_admin adgang på det eksplicitte test-target."""
    from database import get_db, User

    # Fail before any HTTP or DB mutation unless the operator explicitly opted
    # into a test target for this pytest process.
    require_explicit_test_target()

    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["super_admin"]["username"],
            TEST_CREDENTIALS["super_admin"]["password"]
        )
    except Exception:
        pass

    db = None
    try:
        db_gen = get_db()
        db = next(db_gen)

        existing = db.query(User).filter_by(
            username=TEST_CREDENTIALS["super_admin"]["username"]
        ).first()

        if existing:
            db.delete(existing)
            db.commit()

        from headend.main import _hash_password
        new_user = User(
            username=TEST_CREDENTIALS["super_admin"]["username"],
            password_hash=_hash_password(TEST_CREDENTIALS["super_admin"]["password"]),
            role="super_admin",
            email="test-super-admin@timelapse.local",
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return AuthenticatedSession(
            TEST_CREDENTIALS["super_admin"]["username"],
            TEST_CREDENTIALS["super_admin"]["password"]
        )

    except Exception as e:
        pytest.skip(f"Kunne ikke oprette super_admin session: {e}")
    finally:
        if db is not None:
            db.close()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: kræver eksplicit TIMELAPSE_TEST_BASE_URL + test-target acknowledgement"
    )
    config.addinivalue_line(
        "markers", "smoke: hurtig daglig/CI smoke-test for kernefunktionalitet"
    )
    config.addinivalue_line(
        "markers", "unit: unit test der ikke kræver ekstern dependencies"
    )
