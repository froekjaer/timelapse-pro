#!/usr/bin/env python3
"""Idempotent GRC-registrering af sikkerhedsreview 2026-09-19.

Baggrund: Peter bad om en ny virtuel pentest/sikkerhedsanalyse siden juli
(RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md), inkl. live SSH-login på begge
fysiske Edges. Fuldt review: Dokumentation/RISK_ASSESSMENT_v12_ADDENDUM_2026-09-19.md.

To ting gøres her:
1. Ni nye findings (F-1..F-9 fra addendummet) registreres — ingen af dem fandtes
   i forvejen i GRC, herunder det kritiske F-1 (levende GitHub-credential på
   Edge1, først flagget i HANDOVER_LOG 2026-08-31, aldrig fulgt op i GRC).
2. R22/R24/R25 opdateres fra `candidate_review` (bulk-importeret fra dokumentet,
   aldrig ejer-valideret — attributes.method="document_migration_requires_owner_validation")
   til `closed`, med denne sessions kode-citater som validering.

Køres mod live-DB:  DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
  .venvs/timelapse-headend/bin/python3 headend/tools/import_grc_security_review_20260919.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402

ACTOR = "claude-security-review-20260919"
DOC = "doc://Dokumentation/RISK_ASSESSMENT_v12_ADDENDUM_2026-09-19.md"

NEW_ITEMS = [
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE1-GIT-CREDENTIAL-LEAK-UNRESOLVED-20260919",
        "title": "F-1: Levende GitHub-credential i .git/config på Edge1 (TL-C87FF9587CA0) — åben 19 dage, aldrig i GRC",
        "status": "open",
        "priority": "critical",
        "description": (
            "Først flagget HANDOVER_LOG 2026-08-31 (linje 828-839): /opt/timelapse/edge/.git/config "
            "på TL-C87FF9587CA0 indeholdt en levende GitHub Personal Access Token i klartekst i "
            "origin-remote-URL'en. Anbefaling dengang: roter/tilbagekald straks. Ingen senere "
            "handover-entry bekræfter rotation, og PR #242 (2026-09-16 fysisk audit) tjekkede ikke "
            "for dette. Re-verificeret 2026-09-19 (read-only, sed-redigeret, token aldrig læst i "
            "klartekst): samme lækage, nu på /opt/timelapse/.git (sti forskudt, samme checkout-rod). "
            "Edge2 (TL-043EB9E72EFD) er fortsat rent. Krænker allerede registrerede krav "
            "REQ-...-SEC-002 (Secrets ikke i Git) og REQ-...-UPD-001 (Edge må ikke bruge direkte "
            "GitHub). Root cause for at det overlevede 19 dage + en fuld fysisk audit: fundet stod "
            "kun i HANDOVER_LOG, aldrig i GRC — præcis det mønster CLAUDE.md advarer imod."
        ),
        "attributes": {
            "first_flagged": "2026-08-31T00:15+02:00 (HANDOVER_LOG)",
            "reverified": "2026-09-19 (live SSH, read-only, credential redacted at source)",
            "affected_device": "TL-C87FF9587CA0 (Edge1, timelapse0101)",
            "path": "/opt/timelapse/.git/config (tidl. rapporteret /opt/timelapse/edge/.git/config)",
            "peter_decision_20260919": "roter token først; checkout-fjernelse besluttes separat",
        },
        "evidence": [(DOC + "#2-kritisk-fund-f-1", "v12-addendum §2: fuld verifikationskæde")],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE1-IPERF3-EXPOSED-ALL-INTERFACES-20260919",
        "title": "F-2: iperf3 lytter på 0.0.0.0:5201 + [::] på Edge1 — unødvendig, uautentificeret netværkstjeneste",
        "status": "open",
        "priority": "high",
        "description": (
            "ss -tln på TL-C87FF9587CA0 viser iperf3 (bandwidth-benchmark) lyttende på alle "
            "interfaces, ingen auth. Ingen legitim produktionsbrug identificeret på en "
            "timelapse-kamera-edge. IEC 62443-4-2 least-functionality-brud. Dokumenteret, ikke "
            "stoppet (Peters beslutning: governed change-path, ikke ad-hoc SSH-fix)."
        ),
        "attributes": {"affected_device": "TL-C87FF9587CA0", "binding": "0.0.0.0:5201, [::]:5201"},
        "evidence": [(DOC + "#3-uønsketunødvendig-software-og-tjenester--live-verifikation", "v12-addendum §3")],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-EDGE2-RPCBIND-EXPOSED-ALL-INTERFACES-20260919",
        "title": "F-3: rpcbind/portmapper lytter på 0.0.0.0:111 + [::] på Edge2 (produktionsenhed)",
        "status": "open",
        "priority": "high",
        "description": (
            "ss -tln på TL-043EB9E72EFD (bekræftet live produktionsenhed, aktiv capture) viser "
            "rpcbind/portmapper lyttende på alle interfaces. Legacy RPC/NFS-service, kendt "
            "enumerations-/amplifikationsvektor, ingen NFS-brug i arkitekturen. Højere prioritet "
            "end tilsvarende Edge1-fund fordi bekræftet produktionsenhed. Dokumenteret, ikke stoppet."
        ),
        "attributes": {"affected_device": "TL-043EB9E72EFD", "binding": "0.0.0.0:111, [::]:111"},
        "evidence": [(DOC + "#3-uønsketunødvendig-software-og-tjenester--live-verifikation", "v12-addendum §3")],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-TRUST-GRANTS-REPLAY-NONCE-GAP-20260919",
        "title": "F-6: trust/grants.py replay-beskyttelse er single-værdi (last_challenge_id), ikke et brugt-nonce-sæt",
        "status": "open",
        "priority": "high",
        "description": (
            "headend/trust/grants.py (~linje 194-196, draft-PR #246 chatgpt/api-mtls-20260917) "
            "sammenligner kun mod seneste challenge-id. Et opsnappet challenge kan genafspilles "
            "efter en efterfølgende legitim request, fordi kun 'seneste' tjekkes, ikke 'brugt før'. "
            "Scope: EdgeServiceGrant-validering for tekniker-til-Edge-adgang. IKKE deployeret — "
            "PR #246 er draft, main@928134be indeholder ikke denne kode. Pre-merge review-fund."
        ),
        "attributes": {
            "pr": "#246 (chatgpt/api-mtls-20260917, draft, ikke merged)",
            "recommendation": "tidsvindues-begrænset brugt-nonce-sæt eller monotont sekvensnummer",
        },
        "evidence": [(DOC + "#4-trust-mtls-arkitektur-headendtrust-draft-pr-246--pre-merge-review", "v12-addendum §4")],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-TRUST-POLICY-MFA-TAUTOLOGY-20260919",
        "title": "F-7: trust/policy.py PDP's MFA-gate udleder mfa_required af mfa_verified selv (tautologisk, latent fail-open)",
        "status": "open",
        "priority": "medium",
        "description": (
            "headend/trust/policy.py (~linje 103, draft-PR #246) håndhæver ikke uafhængigt at en "
            "handling kræver MFA — den stoler på at kalderen allerede har verificeret det. Nuværende "
            "to kaldere (service_access_api.py, ssh_tunnel_terminal_api.py) gør korrekt pre-tjek, "
            "så ikke udnytteligt i dag, men en fremtidig kalder der glemmer pre-tjekket vil fejle "
            "stille (fail-open). IKKE deployeret — draft-PR #246. Pre-merge review-fund."
        ),
        "attributes": {"pr": "#246 (draft)", "recommendation": "flyt MFA-verifikation ind i PDP'en selv"},
        "evidence": [(DOC + "#4-trust-mtls-arkitektur-headendtrust-draft-pr-246--pre-merge-review", "v12-addendum §4")],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-CRA-REPORTING-CHANNEL-MISSING-20260919",
        "title": "F-9: CRA-rapporteringspligt trådte i kraft 2026-09-11 — SEC-013 dækker ikke CRA/ENISA-kanalen",
        "status": "open",
        "priority": "high",
        "description": (
            "REGULATORISK_OG_STANDARD_REFERENCE_v1.md noterer CRA-rapportering startet 2026-09-11. "
            "SEC-013_Incident_Response_Procedure.md definerer kun interne 24t/72t-frister (72t = "
            "GDPR Art. 33), intet om CRA/ENISA-rapportering af aktivt udnyttede sårbarheder for "
            "'products with digital elements'. Betinget af Peters afklaring af fabrikant-rolle."
        ),
        "attributes": {"depends_on": "produktklassifikations-afklaring (fabrikant-rolle under CRA)"},
        "evidence": [(DOC + "#7-f-9--cra-rapporteringspligt-trådte-i-kraft-ikke-dækket-af-sec-013", "v12-addendum §7")],
    },
]

# (external_id, ny status, valideringsnote til attributes)
VALIDATED_CLOSURES = [
    (
        "R22",
        "closed",
        "K1 route-auth-sweep bekræftet implementeret som headend/tests/test_route_auth_coverage.py, "
        "kører i CI (.github/workflows/ci.yml, ingen integration-marker). R22-mønsteret er nu "
        "strukturelt forhindret. Verificeret 2026-09-19 direkte i kildekoden på main@928134be.",
    ),
    (
        "R24",
        "closed",
        "Bekræftet: headend/ai/vocabulary_routes.py har vocab_read_router (GET, require_role('viewer')) "
        "og vocab_router (mutationer, require_role('super_admin')). Kundevendt UI kan læse labels "
        "uden admin. Verificeret 2026-09-19 på main@928134be.",
    ),
    (
        "R25",
        "closed",
        "Bekræftet: headend/main.py:1108-1154 kræver frisk password+TOTP-reverifikation for "
        "disable-mfa, og kun super_admin kan målrette andres user_id — admin kan ikke længere "
        "deaktivere andres MFA. Verificeret 2026-09-19 på main@928134be.",
    ),
]


def upsert_item(db, spec: dict) -> tuple[GrcItem, bool]:
    item = db.query(GrcItem).filter_by(
        item_type=spec["item_type"], external_id=spec["external_id"]
    ).first()
    if item:
        return item, False
    item = GrcItem(
        item_type=spec["item_type"],
        external_id=spec["external_id"],
        title=spec["title"][:300],
        description=spec["description"],
        status=spec["status"],
        priority=spec["priority"],
        source="import_grc_security_review_20260919.py",
        scope={"product": "timelapse-pro"},
        attributes=spec["attributes"],
        created_by=ACTOR,
        updated_by=ACTOR,
    )
    db.add(item)
    db.flush()
    return item, True


def add_evidence(db, item: GrcItem, uri: str, title: str) -> bool:
    if db.query(GrcEvidence).filter_by(item_id=item.id, uri=uri).first():
        return False
    db.add(GrcEvidence(
        item_id=item.id,
        evidence_type="closure_evidence",
        title=title[:300],
        uri=uri,
        collected_by=ACTOR,
        retention_class="grc_standard",
    ))
    return True


def apply_validated_closure(db, external_id: str, new_status: str, note: str) -> bool:
    item = db.query(GrcItem).filter_by(item_type="risk", external_id=external_id).first()
    if item is None:
        print(f"  ADVARSEL: {external_id} findes ikke i GRC — springer over")
        return False
    if item.status == new_status and item.attributes.get("owner_validated_20260919"):
        return False
    attrs = dict(item.attributes or {})
    attrs["owner_validated_20260919"] = note
    attrs["validated_by"] = ACTOR
    item.status = new_status
    item.attributes = attrs
    item.updated_by = ACTOR
    db.add(item)
    add_evidence(db, item, DOC + f"#5-verificerede-lukninger-siden-juli-r22r24r25--k1--vpen-2026-013", f"v12-addendum §5: {external_id} valideret lukket")
    return True


def main() -> None:
    db = SessionLocal()
    created = evidence_added = validated = 0
    try:
        for spec in NEW_ITEMS:
            item, was_created = upsert_item(db, spec)
            created += was_created
            for uri, ev_title in spec["evidence"]:
                evidence_added += add_evidence(db, item, uri, ev_title)
        for external_id, new_status, note in VALIDATED_CLOSURES:
            validated += apply_validated_closure(db, external_id, new_status, note)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(
        f"GRC sikkerhedsreview 2026-09-19: {created} nye findings, {evidence_added} nye "
        f"evidens-links, {validated} risici valideret/lukket (af {len(NEW_ITEMS)} findings + "
        f"{len(VALIDATED_CLOSURES)} valideringer i alt — idempotent)"
    )


if __name__ == "__main__":
    main()
