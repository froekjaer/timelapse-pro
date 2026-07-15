"""Versioned customer commercial inputs for future FAIR quantification."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import Customer, CustomerRiskInput, CustomerRiskProfile, get_db


router = APIRouter(prefix="/api/customer-risk", tags=["GRC"])
log = logging.getLogger(__name__)


def _require_platform_admin(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user, _is_platform_admin, _mfa_required_for_user, _session_is_mfa_verified, _session_payload

    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if not _is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Kræver platformadministrator")
    if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
        raise HTTPException(status_code=403, detail="MFA kræves")
    return user


def _require_risk_admin(request: Request, db: Session = Depends(get_db)):
    from main import _ROLE_HIERARCHY, _mfa_required_for_user, _session_is_mfa_verified, _session_payload, get_current_user

    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if "admin" not in _ROLE_HIERARCHY.get(user.role, {user.role}):
        raise HTTPException(status_code=403, detail="Kræver administrator")
    if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
        raise HTTPException(status_code=403, detail="MFA kræves")
    return user


def _ensure_customer_scope(user, customer_id: str) -> None:
    from main import _is_platform_admin

    if _is_platform_admin(user):
        return
    if not user.customer_id or str(user.customer_id) != customer_id:
        raise HTTPException(status_code=404, detail="Kunde ikke fundet")


def _serialize(row: CustomerRiskInput) -> dict:
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "monthly_service_price": float(row.monthly_service_price),
        "currency": row.currency,
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "source": row.source,
        "note": row.note,
        "validated_by": row.validated_by,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
    }


def _serialize_profile(row: CustomerRiskProfile) -> dict:
    money_fields = ("product_value_dkk", "daily_downtime_cost_dkk", "recreation_cost_dkk", "contractual_penalty_dkk")
    result = {
        "id": row.id, "customer_id": row.customer_id, "version": row.version, "status": row.status,
        "business_dependency": row.business_dependency, "availability_impact": row.availability_impact,
        "integrity_impact": row.integrity_impact, "confidentiality_impact": row.confidentiality_impact,
        "recovery_objective_hours": row.recovery_objective_hours,
        "max_tolerable_downtime_hours": row.max_tolerable_downtime_hours,
        "personal_data_level": row.personal_data_level, "assumptions": row.assumptions,
        "submitted_by": row.submitted_by,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "validated_by": row.validated_by,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
        "validation_note": row.validation_note,
    }
    result.update({field: float(getattr(row, field)) if getattr(row, field) is not None else None for field in money_fields})
    return result


def _optional_nonnegative_decimal(payload: dict, field: str):
    value = payload.get(field)
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"{field} skal være et tal") from exc
    if number < 0:
        raise HTTPException(status_code=422, detail=f"{field} må ikke være negativ")
    return number.quantize(Decimal("0.01"))


def _rating(payload: dict, field: str) -> int:
    try:
        value = int(payload.get(field))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field} skal være 1-5") from exc
    if value < 1 or value > 5:
        raise HTTPException(status_code=422, detail=f"{field} skal være 1-5")
    return value


@router.get("/{customer_id}")
def get_customer_risk_inputs(
    customer_id: str,
    _user=Depends(_require_platform_admin),
    db: Session = Depends(get_db),
):
    if not db.query(Customer).filter_by(id=customer_id).first():
        raise HTTPException(status_code=404, detail="Kunde ikke fundet")
    rows = (db.query(CustomerRiskInput).filter_by(customer_id=customer_id)
            .order_by(CustomerRiskInput.effective_from.desc(), CustomerRiskInput.id.desc()).all())
    today = date.today()
    current = (db.query(CustomerRiskInput).filter(
        CustomerRiskInput.customer_id == customer_id,
        CustomerRiskInput.effective_from <= today,
        or_(CustomerRiskInput.effective_to.is_(None), CustomerRiskInput.effective_to >= today),
    ).order_by(CustomerRiskInput.effective_from.desc()).first())
    return {"current": _serialize(current) if current else None,
            "history": [_serialize(row) for row in rows]}


@router.post("/{customer_id}")
def create_customer_risk_input(
    customer_id: str,
    payload: dict,
    user=Depends(_require_platform_admin),
    db: Session = Depends(get_db),
):
    if not db.query(Customer).filter_by(id=customer_id).first():
        raise HTTPException(status_code=404, detail="Kunde ikke fundet")
    try:
        price = Decimal(str(payload.get("monthly_service_price")))
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=422, detail="Månedspris skal være et tal")
    if price <= 0:
        raise HTTPException(status_code=422, detail="Månedspris skal være større end 0")
    currency = str(payload.get("currency", "DKK")).upper()
    if currency != "DKK":
        raise HTTPException(status_code=422, detail="Kun DKK understøttes i første version")
    try:
        effective_from = date.fromisoformat(str(payload.get("effective_from") or date.today().isoformat()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Ugyldig ikrafttrædelsesdato") from exc

    current = (db.query(CustomerRiskInput).filter_by(customer_id=customer_id, effective_to=None)
               .with_for_update().first())
    if current:
        if effective_from <= current.effective_from:
            raise HTTPException(status_code=409, detail="Ny version skal træde i kraft efter den aktive version")
        current.effective_to = effective_from - timedelta(days=1)
    row = CustomerRiskInput(
        customer_id=customer_id,
        monthly_service_price=price.quantize(Decimal("0.01")),
        currency=currency,
        effective_from=effective_from,
        source=str(payload.get("source") or "customer_contract")[:100],
        note=str(payload.get("note") or "")[:2000] or None,
        validated_by=user.username,
        validated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log.info("Kommercielt risikoinput versioneret: customer=%s id=%s validator=%s",
             customer_id, row.id, user.username)
    return {"status": "ok", "current": _serialize(row)}


@router.get("/profile/{customer_id}")
def get_customer_risk_profile(
    customer_id: str,
    user=Depends(_require_risk_admin),
    db: Session = Depends(get_db),
):
    _ensure_customer_scope(user, customer_id)
    if not db.query(Customer).filter_by(id=customer_id).first():
        raise HTTPException(status_code=404, detail="Kunde ikke fundet")
    rows = (db.query(CustomerRiskProfile).filter_by(customer_id=customer_id)
            .order_by(CustomerRiskProfile.version.desc()).all())
    validated = next((row for row in rows if row.status == "validated"), None)
    pending = next((row for row in rows if row.status == "submitted"), None)
    return {"validated": _serialize_profile(validated) if validated else None,
            "pending": _serialize_profile(pending) if pending else None,
            "history": [_serialize_profile(row) for row in rows]}


@router.post("/profile/{customer_id}")
def submit_customer_risk_profile(
    customer_id: str,
    payload: dict,
    user=Depends(_require_risk_admin),
    db: Session = Depends(get_db),
):
    _ensure_customer_scope(user, customer_id)
    if not db.query(Customer).filter_by(id=customer_id).first():
        raise HTTPException(status_code=404, detail="Kunde ikke fundet")
    pending = db.query(CustomerRiskProfile).filter_by(customer_id=customer_id, status="submitted").first()
    if pending:
        raise HTTPException(status_code=409, detail="Der findes allerede en profil til validering")
    latest = (db.query(CustomerRiskProfile).filter_by(customer_id=customer_id)
              .order_by(CustomerRiskProfile.version.desc()).with_for_update().first())
    personal_data_level = str(payload.get("personal_data_level") or "none")
    if personal_data_level not in {"none", "limited", "significant", "special_category"}:
        raise HTTPException(status_code=422, detail="Ugyldigt persondataniveau")
    def optional_hours(field: str):
        value = payload.get(field)
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{field} skal være et tal") from exc
        if number < 0:
            raise HTTPException(status_code=422, detail=f"{field} må ikke være negativ")
        return number
    row = CustomerRiskProfile(
        customer_id=customer_id, version=(latest.version + 1 if latest else 1), status="submitted",
        product_value_dkk=_optional_nonnegative_decimal(payload, "product_value_dkk"),
        daily_downtime_cost_dkk=_optional_nonnegative_decimal(payload, "daily_downtime_cost_dkk"),
        recreation_cost_dkk=_optional_nonnegative_decimal(payload, "recreation_cost_dkk"),
        contractual_penalty_dkk=_optional_nonnegative_decimal(payload, "contractual_penalty_dkk"),
        business_dependency=_rating(payload, "business_dependency"),
        availability_impact=_rating(payload, "availability_impact"),
        integrity_impact=_rating(payload, "integrity_impact"),
        confidentiality_impact=_rating(payload, "confidentiality_impact"),
        recovery_objective_hours=optional_hours("recovery_objective_hours"),
        max_tolerable_downtime_hours=optional_hours("max_tolerable_downtime_hours"),
        personal_data_level=personal_data_level,
        assumptions=str(payload.get("assumptions") or "")[:5000] or None,
        submitted_by=user.username,
    )
    db.add(row); db.commit(); db.refresh(row)
    log.info("Kunderisikoprofil indsendt: customer=%s version=%s by=%s", customer_id, row.version, user.username)
    return {"status": "submitted", "profile": _serialize_profile(row)}


@router.post("/profile/{customer_id}/{profile_id}/decision")
def decide_customer_risk_profile(
    customer_id: str,
    profile_id: int,
    payload: dict,
    user=Depends(_require_platform_admin),
    db: Session = Depends(get_db),
):
    decision = str(payload.get("decision") or "")
    if decision not in {"validated", "rejected"}:
        raise HTTPException(status_code=422, detail="decision skal være validated eller rejected")
    row = db.query(CustomerRiskProfile).filter_by(id=profile_id, customer_id=customer_id).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="Risikoprofil ikke fundet")
    if row.status != "submitted":
        raise HTTPException(status_code=409, detail="Profilen er allerede behandlet")
    if decision == "validated":
        db.query(CustomerRiskProfile).filter(
            CustomerRiskProfile.customer_id == customer_id,
            CustomerRiskProfile.status == "validated",
        ).update({CustomerRiskProfile.status: "superseded"}, synchronize_session=False)
    row.status = decision
    row.validated_by = user.username
    row.validated_at = datetime.now(timezone.utc)
    row.validation_note = str(payload.get("note") or "")[:2000] or None
    db.commit()
    log.info("Kunderisikoprofil %s: customer=%s version=%s by=%s", decision, customer_id, row.version, user.username)
    return {"status": decision, "profile": _serialize_profile(row)}
