"""Regression contracts for z.ai update-flow E-2.

Every executable update type that Headend requires an artifact for must also
pass through the Edge cryptographic artifact gate.  Missing artifacts therefore
fail closed before any install path can run.
"""

from edge.security import verify_update_artifact


EXECUTABLE_UPDATE_TYPES = {
    "app_security",
    "app_updates",
    "app_update",
    "timelapse_update",
    "timelapse_pro_update",
    "timelapse_security",
    "timelapse_pro_security",
    "application_security",
    "application_update",
    "application_updates",
    "dependency_security",
    "dependency_updates",
    "third_party_security",
    "third_party_updates",
    "os_security",
    "os_updates",
}


def test_all_executable_update_aliases_fail_closed_without_artifact():
    for update_type in sorted(EXECUTABLE_UPDATE_TYPES):
        allowed, reason = verify_update_artifact(
            {"update_type": update_type},
            {"artifact_verification_required": True},
        )
        assert allowed is False, update_type
        assert "artifact" in reason.lower(), (update_type, reason)


def test_verification_policy_cannot_be_disabled_for_any_executable_alias():
    for update_type in sorted(EXECUTABLE_UPDATE_TYPES):
        allowed, reason = verify_update_artifact(
            {"update_type": update_type},
            {"artifact_verification_required": False},
        )
        assert allowed is False, update_type
        assert "deaktiveres" in reason.lower(), (update_type, reason)


def test_non_code_update_remains_outside_code_artifact_gate():
    allowed, reason = verify_update_artifact(
        {"update_type": "camera_metadata_refresh"},
        {"artifact_verification_required": True},
    )
    assert allowed is True
    assert reason == "non-code update"
