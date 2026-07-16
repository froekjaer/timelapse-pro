"""Regulatory intelligence registry and audit-catalog readiness API.

The registry contains metadata and authoritative links, not copied legal or
licensed standards text. Future source collectors must publish reviewed,
hashed snapshots before a change can become an audit baseline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query


router = APIRouter(prefix="/api/compliance/intelligence", tags=["Compliance Intelligence"])


INSTRUMENTS = [
    {"id": "EU-2016-679", "title": "General Data Protection Regulation (GDPR)", "short_name": "GDPR", "jurisdiction": "EU", "kind": "regulation", "category": "privacy", "status": "in_force", "applicability": "direct_or_conditional", "effective_from": "2018-05-25", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj", "relevance": "Personal data in images, access logs, AI tags and cloud processing."},
    {"id": "EU-2024-1689", "title": "Artificial Intelligence Act", "short_name": "AI Act", "jurisdiction": "EU", "kind": "regulation", "category": "ai", "status": "phased_in", "applicability": "direct_or_conditional", "effective_from": "2024-08-01", "next_deadline": "2026-08-02", "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj", "relevance": "AI provider/deployer roles, prohibited practices, transparency, oversight and post-market evidence."},
    {"id": "EU-AI-OMNIBUS", "title": "Digital Omnibus - AI Act amendments", "short_name": "AI Omnibus", "jurisdiction": "EU", "kind": "proposal", "category": "ai", "status": "political_agreement", "applicability": "horizon", "effective_from": None, "next_deadline": None, "source_url": "https://digital-strategy.ec.europa.eu/en/library/digital-omnibus-ai-regulation-proposal", "relevance": "May change AI Act high-risk timelines and implementation details; final Official Journal text must govern."},
    {"id": "EU-2024-2847", "title": "Cyber Resilience Act", "short_name": "CRA", "jurisdiction": "EU", "kind": "regulation", "category": "product_security", "status": "phased_in", "applicability": "likely_direct", "effective_from": "2024-12-10", "next_deadline": "2026-09-11", "source_url": "https://eur-lex.europa.eu/eli/reg/2024/2847/oj", "relevance": "Secure product lifecycle, SBOM, CVD, support period, reporting, conformity and CE."},
    {"id": "EU-2023-2854", "title": "Data Act", "short_name": "Data Act", "jurisdiction": "EU", "kind": "regulation", "category": "data", "status": "in_force", "applicability": "direct_or_conditional", "effective_from": "2025-09-12", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/reg/2023/2854/oj", "relevance": "Connected-product data access, metadata, portability, contracts and secure export."},
    {"id": "EU-2022-2555", "title": "Network and Information Systems Directive 2", "short_name": "NIS2", "jurisdiction": "EU", "kind": "directive", "category": "cybersecurity", "status": "transposed", "applicability": "customer_driven_or_conditional", "effective_from": "2023-01-16", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/dir/2022/2555/oj", "relevance": "Risk governance, incident reporting, continuity, supply chain, vulnerability handling and management accountability."},
    {"id": "DK-LOV-434-2025", "title": "Lov om foranstaltninger til sikring af et højt cybersikkerhedsniveau", "short_name": "Dansk NIS 2-lov", "jurisdiction": "DK", "kind": "law", "category": "cybersecurity", "status": "in_force", "applicability": "customer_driven_or_conditional", "effective_from": "2025-07-01", "next_deadline": None, "source_url": "https://www.retsinformation.dk/eli/lta/2025/434/dan", "relevance": "Danish scope, section 6 controls, management duties, supervision and reporting."},
    {"id": "EU-2022-2557", "title": "Critical Entities Resilience Directive", "short_name": "CER", "jurisdiction": "EU", "kind": "directive", "category": "resilience", "status": "transposed_by_sector", "applicability": "customer_driven", "effective_from": "2023-01-16", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/dir/2022/2557/oj", "relevance": "Physical and operational resilience requirements for critical customers and dependencies."},
    {"id": "EU-2024-2853", "title": "Directive on liability for defective products", "short_name": "Product Liability Directive", "jurisdiction": "EU", "kind": "directive", "category": "product", "status": "transposition_pending", "applicability": "likely_direct", "effective_from": None, "next_deadline": "2026-12-09", "source_url": "https://eur-lex.europa.eu/eli/dir/2024/2853/oj", "relevance": "Software and AI product liability, updates, related services and preservation of technical evidence."},
    {"id": "EU-2019-881", "title": "EU Cybersecurity Act", "short_name": "Cybersecurity Act", "jurisdiction": "EU", "kind": "regulation", "category": "certification", "status": "in_force", "applicability": "market_or_customer_driven", "effective_from": "2019-06-27", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/reg/2019/881/oj", "relevance": "European certification framework for ICT products, services, processes and managed security services."},
    {"id": "EU-2025-38", "title": "Cyber Solidarity Act", "short_name": "Cyber Solidarity Act", "jurisdiction": "EU", "kind": "regulation", "category": "resilience", "status": "in_force", "applicability": "horizon_or_customer_driven", "effective_from": "2025-02-04", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/reg/2025/38/oj", "relevance": "EU preparedness, cyber reserve, coordinated response and post-incident review."},
    {"id": "DK-TV-2023-182", "title": "Bekendtgørelse af lov om tv-overvågning", "short_name": "TV-overvågningsloven", "jurisdiction": "DK", "kind": "law", "category": "privacy", "status": "in_force", "applicability": "site_conditional", "effective_from": "2023-02-24", "next_deadline": None, "source_url": "https://www.retsinformation.dk/eli/lta/2023/182", "relevance": "Repeated camera monitoring of persons, public areas, workplaces, signage and disclosure."},
    {"id": "EU-2022-2554", "title": "Digital Operational Resilience Act", "short_name": "DORA", "jurisdiction": "EU", "kind": "regulation", "category": "financial", "status": "in_force", "applicability": "sector_conditional", "effective_from": "2025-01-17", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/reg/2022/2554/oj", "relevance": "Financial-customer ICT third-party risk, contracts, registers, testing and exit."},
    {"id": "EU-2023-1230", "title": "Machinery Regulation", "short_name": "Machinery Regulation", "jurisdiction": "EU", "kind": "regulation", "category": "safety", "status": "future_application", "applicability": "vertical_conditional", "effective_from": "2027-01-20", "next_deadline": "2027-01-20", "source_url": "https://eur-lex.europa.eu/eli/reg/2023/1230/oj", "relevance": "Future OT payloads that control machinery or become safety components."},
    {"id": "EU-2014-53", "title": "Radio Equipment Directive", "short_name": "RED", "jurisdiction": "EU", "kind": "directive", "category": "product", "status": "in_force", "applicability": "hardware_conditional", "effective_from": "2016-06-13", "next_deadline": None, "source_url": "https://eur-lex.europa.eu/eli/dir/2014/53/oj", "relevance": "Relevant if TimeLapse Pro becomes manufacturer/integrator of marketed radio equipment."},
    {"id": "US-NERC-CIP", "title": "Critical Infrastructure Protection Standards", "short_name": "NERC CIP", "jurisdiction": "US", "kind": "mandatory_sector_standard", "category": "energy", "status": "in_force_and_evolving", "applicability": "market_or_customer_driven", "effective_from": None, "next_deadline": None, "source_url": "https://www.nerc.com/pa/Stand/Pages/CIPStandards.aspx", "relevance": "North American bulk electric system cyber controls; relevant for energy market readiness and supplier evidence."},
    {"id": "US-FERC-ORDER-887", "title": "FERC Order No. 887 - Internal Network Security Monitoring", "short_name": "FERC 887", "jurisdiction": "US", "kind": "regulatory_order", "category": "energy", "status": "implementation", "applicability": "market_or_customer_driven", "effective_from": None, "next_deadline": None, "source_url": "https://www.ferc.gov/", "relevance": "NERC CIP evolution for internal network security monitoring; track final standards and implementation dates."},
    {"id": "US-IOT-CYBER-LABEL", "title": "U.S. Cyber Trust Mark program", "short_name": "Cyber Trust Mark", "jurisdiction": "US", "kind": "voluntary_program", "category": "iot", "status": "rolling_out", "applicability": "market_optional", "effective_from": None, "next_deadline": None, "source_url": "https://www.fcc.gov/cybertrustmark", "relevance": "Consumer IoT market signal; not a substitute for industrial/OT assurance."},
]


AUDIT_CATALOGS = [
    {"id": "SABSA", "title": "SABSA", "catalog_status": "methodology_reference", "license": "licensed_methodology", "full_audit_available": False, "reason": "A complete audit requires an agreed SABSA scope, business attributes and licensed methodology content."},
    {"id": "ISO27001-2022", "title": "ISO/IEC 27001:2022", "catalog_status": "license_required", "license": "proprietary", "full_audit_available": False, "reason": "Import a legitimately licensed control catalog before a clause-complete audit can be claimed."},
    {"id": "IEC62443", "title": "IEC 62443 series", "catalog_status": "license_required_and_profile_needed", "license": "proprietary", "full_audit_available": False, "reason": "Select applicable parts and roles, then import licensed requirements and requirement enhancements."},
    {"id": "ISO42001", "title": "ISO/IEC 42001", "catalog_status": "license_required", "license": "proprietary", "full_audit_available": False, "reason": "AI management-system clauses and controls require licensed source content."},
    {"id": "NIST-CSF-2", "title": "NIST Cybersecurity Framework 2.0", "catalog_status": "public_import_pending", "license": "public", "full_audit_available": False, "reason": "The official full Core is public; a hashed source snapshot and mappings must be imported and reviewed."},
    {"id": "NIST-800-82R3", "title": "NIST SP 800-82 Rev. 3", "catalog_status": "public_import_pending", "license": "public", "full_audit_available": False, "reason": "Import the complete OT overlay with source provenance before full assessment."},
    {"id": "NIST-AI-RMF", "title": "NIST AI RMF", "catalog_status": "public_import_pending", "license": "public", "full_audit_available": False, "reason": "Import the complete AI RMF Core and selected profiles with provenance."},
    {"id": "NERC-CIP", "title": "NERC CIP", "catalog_status": "public_import_pending", "license": "public_reference", "full_audit_available": False, "reason": "Select the effective NERC standards set and applicability before importing all requirements/subrequirements."},
    {"id": "EU-AI-ACT", "title": "EU AI Act", "catalog_status": "legal_obligation_decomposition_pending", "license": "official_public_text", "full_audit_available": False, "reason": "Role, use case and risk class must be selected before all applicable obligations can be assessed."},
    {"id": "EU-CRA", "title": "EU Cyber Resilience Act", "catalog_status": "legal_obligation_decomposition_pending", "license": "official_public_text", "full_audit_available": False, "reason": "Manufacturer role, product class and conformity route must be fixed before a complete audit."},
    {"id": "EU-NIS2-DK", "title": "Danish NIS 2 Act", "catalog_status": "legal_obligation_decomposition_pending", "license": "official_public_text", "full_audit_available": False, "reason": "Entity/sector scope and applicable executive orders must be established first."},
]


@router.get("/instruments")
def list_instruments(
    jurisdiction: str | None = Query(default=None, max_length=20),
    category: str | None = Query(default=None, max_length=40),
    search: str | None = Query(default=None, max_length=120),
):
    rows = INSTRUMENTS
    if jurisdiction:
        rows = [row for row in rows if row["jurisdiction"].lower() == jurisdiction.lower()]
    if category:
        rows = [row for row in rows if row["category"].lower() == category.lower()]
    if search:
        needle = search.casefold()
        rows = [row for row in rows if needle in " ".join(str(value) for value in row.values()).casefold()]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": "versioned_reviewed_registry",
        "update_policy": "authoritative allowlist -> hash/diff -> admin review -> active baseline",
        "count": len(rows),
        "instruments": rows,
    }


@router.get("/audit-catalogs")
def list_audit_catalogs():
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_policy": "No full-audit claim unless the complete applicable catalog is loaded, versioned and provenance-verified.",
        "catalogs": AUDIT_CATALOGS,
    }
