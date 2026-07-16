from headend.runtime_environment import background_jobs_enabled, rate_limits_enabled


def test_test_environment_disables_background_jobs_by_default(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "test")
    monkeypatch.delenv("TIMELAPSE_TEST_BACKGROUND_JOBS", raising=False)

    assert background_jobs_enabled() is False


def test_test_background_jobs_require_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "test")
    monkeypatch.setenv("TIMELAPSE_TEST_BACKGROUND_JOBS", "true")

    assert background_jobs_enabled() is True


def test_non_test_environments_keep_background_jobs_enabled(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "production")
    monkeypatch.delenv("TIMELAPSE_TEST_BACKGROUND_JOBS", raising=False)

    assert background_jobs_enabled() is True


def test_test_environment_disables_rate_limits_by_default(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "test")
    monkeypatch.delenv("TIMELAPSE_TEST_RATE_LIMITS", raising=False)

    assert rate_limits_enabled() is False


def test_test_environment_can_enable_rate_limits_explicitly(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "test")
    monkeypatch.setenv("TIMELAPSE_TEST_RATE_LIMITS", "true")

    assert rate_limits_enabled() is True


def test_non_test_environments_keep_rate_limits_enabled(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "production")
    monkeypatch.setenv("TIMELAPSE_TEST_RATE_LIMITS", "false")

    assert rate_limits_enabled() is True
