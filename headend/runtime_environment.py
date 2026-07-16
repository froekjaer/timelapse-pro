"""Runtime environment gates shared by Headend startup handlers."""

import os


def background_jobs_enabled() -> bool:
    """Disable mutating/external background jobs in tests unless explicitly opted in."""
    if os.getenv("TIMELAPSE_ENV", "rd").strip().lower() != "test":
        return True
    return os.getenv("TIMELAPSE_TEST_BACKGROUND_JOBS", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def rate_limits_enabled() -> bool:
    """Keep rate limits out of broad test runs unless explicitly requested."""
    if os.getenv("TIMELAPSE_ENV", "rd").strip().lower() != "test":
        return True
    return os.getenv("TIMELAPSE_TEST_RATE_LIMITS", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
