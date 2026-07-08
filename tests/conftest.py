"""
TimeLapse Pro — pytest konfiguration

Indeholder fixtures til integration tests med authenticated sessions.
"""
import os
import pytest
import requests

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# Test credentials
TEST_CREDENTIALS = {
    "admin": {
        "username": "admin",
        "password": "TestAdmin123!"
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
    """Custom session that manually handles authentication cookies.

    Workaround for cookie domain mismatch between localhost and 127.0.0.1
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session_token = None
        self._login()

    def _login(self):
        """Login og gem session token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"Login fejlede: {response.status_code}")

        # Hent cookie fra response
        for cookie in response.cookies:
            if cookie.name == "tl_session":
                self.session_token = cookie.value
                break

        if not self.session_token:
            raise Exception("Ingen session token i login response")

    def request(self, method, path, **kwargs):
        """Make authenticated request."""
        url = f"{BASE_URL}{path}" if not path.startswith("http") else path

        # Send cookie som Cookie header i stedet for at rely på cookie jar
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
    """Authenticated session med admin adgang (bruger operator rolle).

    Bruger: test-operator / TestOperator123!
    """
    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["operator"]["username"],
            TEST_CREDENTIALS["operator"]["password"]
        )
    except Exception as e:
        pytest.skip(f"Kunne ikke oprette admin session: {e}")


@pytest.fixture(scope="session")
def viewer_session():
    """Authenticated session med viewer rolle.

    Bruger: test-viewer / TestViewer123!
    """
    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["viewer"]["username"],
            TEST_CREDENTIALS["viewer"]["password"]
        )
    except Exception as e:
        pytest.skip(f"Kunne ikke oprette viewer session: {e}")


@pytest.fixture(scope="session")
def operator_session():
    """Authenticated session med operator rolle.

    Bruger: test-operator / TestOperator123!
    """
    try:
        return AuthenticatedSession(
            TEST_CREDENTIALS["operator"]["username"],
            TEST_CREDENTIALS["operator"]["password"]
        )
    except Exception as e:
        pytest.skip(f"Kunne ikke oprette operator session: {e}")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: kræver live headend på TIMELAPSE_TEST_BASE_URL"
    )
    config.addinivalue_line(
        "markers", "smoke: hurtig daglig/CI smoke-test for kernefunktionalitet"
    )
    config.addinivalue_line(
        "markers", "unit: unit test der ikke kræver ekstern dependencies"
    )
