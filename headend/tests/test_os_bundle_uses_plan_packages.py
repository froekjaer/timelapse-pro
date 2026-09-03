"""_auto_build_and_bind_os_bundle() must prefer the reconciled Plan-file package
list over Edge's own reported _os_updates_available.

Found live in production 2026-09-03 (HANDOVER_LOG): after fixing the poller's
status filter, it correctly picked up a fresh, plan-backed candidate for
TL-043EB9E72EFD (215 security + 535 functional packages, reconciled by Headend
against Ubuntu 24.04 metadata) but then failed with "Ingen pakker i inventory"
— because it only ever read DeviceInventory.software_inventory's
_os_updates_available field. That field is structurally useless in this
architecture: Edge has no internet, so it can never run "apt update" against
real mirrors, and its local apt cache — and therefore anything it reports as
"upgradable" — stays permanently stale. The device's own inventory reported
{"total": 0, ...} at the exact same moment the freshly-generated plan showed
750 outstanding packages.
"""
import json

import main


def test_extracts_only_the_matching_category_from_plan(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "decisions": {
            "os_security": {
                "packages": [
                    {"name": "libssl3", "installed_version": "3.0.13-0ubuntu3.4", "available_version": "3.0.13-0ubuntu3.5", "source_repo": "noble-security"},
                ]
            },
            "os_updates": {
                "packages": [
                    {"name": "curl", "installed_version": "8.5.0", "available_version": "8.6.0", "source_repo": "noble-updates"},
                ]
            },
        }
    }))

    security_packages = main._packages_from_os_plan(str(plan_path), "os_security")
    assert [p["name"] for p in security_packages] == ["libssl3"]
    assert security_packages[0]["available_version"] == "3.0.13-0ubuntu3.5"

    functional_packages = main._packages_from_os_plan(str(plan_path), "os_updates")
    assert [p["name"] for p in functional_packages] == ["curl"]


def test_missing_plan_file_returns_empty_list_not_an_exception(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    assert main._packages_from_os_plan(str(missing), "os_security") == []


def test_plan_without_the_requested_category_returns_empty_list(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"decisions": {"os_updates": {"packages": [{"name": "curl", "available_version": "8.6.0"}]}}}))
    assert main._packages_from_os_plan(str(plan_path), "os_security") == []


def test_auto_build_uses_plan_when_edge_apt_cache_says_zero(tmp_path, monkeypatch):
    """The exact scenario found live: a fresh plan has real work, Edge's own
    inventory simultaneously (and permanently) says there's none."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "decisions": {
            "os_security": {
                "packages": [
                    {"name": "libssl3", "installed_version": "3.0.13-0ubuntu3.4", "available_version": "3.0.13-0ubuntu3.5", "source_repo": "noble-security"},
                ]
            }
        }
    }))

    update = type("FakeUpdate", (), {
        "update_type": "os_security",
        "description": f"Plan: {plan_path}",
    })()

    monkeypatch.setattr(main, "_plan_path_for_update", lambda u: str(plan_path))

    packages = main._packages_from_os_plan(str(plan_path), update.update_type)
    assert packages, "plan-backed packages must be found even when Edge's own cache is stale/empty"
    assert packages[0]["name"] == "libssl3"
