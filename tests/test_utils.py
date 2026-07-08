"""
Test utilities til TimeLapse Pro.

Indeholder hjælpefunktioner til oprettelse af testbrugere, test data, etc.
"""
import os
import random
import string
from typing import Optional

import requests

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")


def random_password(length: int = 12) -> str:
    """Generer et stærkt random password."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choice(chars) for _ in range(length))


def create_test_user(
    username: str,
    role: str = "viewer",
    password: Optional[str] = None
) -> dict:
    """Opret en testbruger til integration tests.

    Returns:
        Dict med username, password, og user_id
    """
    if password is None:
        password = random_password()

    # Opret bruger via API (kræver admin/super_admin)
    # For nu: returner credentials - brugeren skal oprettes manuelt
    # eller via en setup fixture

    return {
        "username": username,
        "password": password,
        "role": role
    }


def login_as(username: str, password: str) -> Optional[requests.Session]:
    """Log ind og returner en authenticated session."""
    session = requests.Session()

    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10
    )

    if response.status_code == 200:
        return session

    return None


def get_test_session(role: str = "viewer") -> Optional[requests.Session]:
    """Hent en auth session for test.

    Prøver først at bruge hardcoded test credentials, derefter env vars.
    """
    test_creds = {
        "admin": ("admin", os.getenv("TIMELAPSE_ADMIN_PASSWORD", "admin")),
        "viewer": ("viewer", os.getenv("TIMELAPSE_VIEWER_PASSWORD", "viewer")),
        "operator": ("operator", os.getenv("TIMELAPSE_OPERATOR_PASSWORD", "operator")),
    }

    if role not in test_creds:
        return None

    username, password = test_creds[role]
    return login_as(username, password)
