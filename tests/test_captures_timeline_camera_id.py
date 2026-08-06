"""Regression test (2026-08-06/07): Tidslinje-fanen krævede altid et fysisk
device_id, hvilket gjorde den permanent utilgængelig for en kamera-lokation
uden en aktiv Edge — netop det tilfælde camera_id-arkitekturen findes for
(Peter opdagede det da Travbyens kameraer, efter oprydning af TL-IMPORT-
placeholder-enhederne, faldt tilbage til den forenklede galleri-visning uden
Tidslinje/Statistik).

/api/admin/captures/timeline blev udvidet til at acceptere camera_id som
alternativ til device_id, og samtidig ekstraheret til sit eget modul (samme
lejlighed som fjernede kravet — arkitektur-ratchet-baseline'n tvang
udtrækningen, ikke omvendt).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "headend" / "api" / "captures_timeline_api.py").read_text(encoding="utf-8")
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def test_timeline_accepts_camera_id_as_alternative_to_device_id() -> None:
    assert "camera_id: Optional[str] = None" in SOURCE
    assert 'raise HTTPException(status_code=400, detail="device_id eller camera_id påkrævet")' in SOURCE
    assert "base_filter = Capture.camera_id == camera_id" in SOURCE


def test_timeline_enforces_access_control_for_camera_id() -> None:
    assert "_ensure_site_access(db, _user, cam.site_id)" in SOURCE
    assert "_ensure_customer_access(_user, cam.customer_id)" in SOURCE


def test_timeline_router_is_included_from_main() -> None:
    assert "from api.captures_timeline_api import router as _captures_timeline_router" in MAIN
    assert "app.include_router(_captures_timeline_router)" in MAIN
    assert 'def captures_timeline(' not in MAIN, (
        "captures_timeline() must live only in api/captures_timeline_api.py — "
        "a leftover duplicate in main.py would shadow or conflict with the router."
    )
