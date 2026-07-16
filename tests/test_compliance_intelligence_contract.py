"""Contract tests for the regulatory registry and truthful audit claims."""

from headend.compliance_intelligence import AUDIT_CATALOGS, INSTRUMENTS


def test_regulatory_instrument_ids_and_sources_are_unique():
    ids = [item["id"] for item in INSTRUMENTS]
    assert len(ids) == len(set(ids))
    assert all(item["source_url"].startswith("https://") for item in INSTRUMENTS)


def test_required_eu_danish_and_global_instruments_are_present():
    ids = {item["id"] for item in INSTRUMENTS}
    assert {
        "EU-2024-1689",
        "EU-2024-2847",
        "EU-2023-2854",
        "DK-LOV-434-2025",
        "DK-TV-2023-182",
        "US-NERC-CIP",
    } <= ids


def test_no_incomplete_catalog_is_claimed_as_full_audit():
    for catalog in AUDIT_CATALOGS:
        if catalog["catalog_status"] != "complete_verified":
            assert catalog["full_audit_available"] is False
            assert catalog["reason"]


def test_proprietary_catalogs_require_a_license():
    proprietary = {item["id"] for item in AUDIT_CATALOGS if item["license"] == "proprietary"}
    assert {"ISO27001-2022", "IEC62443", "ISO42001"} <= proprietary
