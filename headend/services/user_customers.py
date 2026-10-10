"""User ↔ customer membership administration (many-to-many, Peter 2026-10-10).

All writes go through set_user_customers() so the legacy mirror
`users.customer_id` always equals the sole membership (or NULL). That
invariant is what makes the startup backfill below safe to run on every
start: it only ever re-inserts a membership the mirror says exists, so it can
never resurrect a membership that was removed.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Customer, User, UserCustomer

log = logging.getLogger("headend")


def normalise_customer_ids(db: Session, customer_ids) -> list[str]:
    """Unique, existing customer ids; unknown ids are refused, not dropped."""
    wanted = sorted({str(c).strip() for c in (customer_ids or []) if c is not None and str(c).strip()})
    if not wanted:
        return []
    known = {row[0] for row in db.query(Customer.id).filter(Customer.id.in_(wanted)).all()}
    unknown = [c for c in wanted if c not in known]
    if unknown:
        raise HTTPException(status_code=400, detail="Ukendt kunde i kundetilknytning")
    return wanted


def set_user_customers(db: Session, user: User, customer_ids, actor: str | None = None) -> list[str]:
    """Replace the user's memberships with exactly `customer_ids`."""
    wanted = normalise_customer_ids(db, customer_ids)
    current = {link.customer_id: link for link in user.customer_links}
    for customer_id, link in current.items():
        if customer_id not in wanted:
            user.customer_links.remove(link)
    for customer_id in wanted:
        if customer_id not in current:
            user.customer_links.append(UserCustomer(customer_id=customer_id, created_by=actor))
    user.customer_id = wanted[0] if len(wanted) == 1 else None
    return wanted


def user_customer_list(user: User) -> list[str]:
    return sorted({link.customer_id for link in user.customer_links})


def backfill_user_customers(engine) -> int:
    """Idempotent: one membership per user whose legacy customer_id is set
    and points at an existing customer. Run at startup after create_tables()."""
    with engine.begin() as conn:
        result = conn.execute(text(
            "INSERT INTO user_customers (user_id, customer_id, created_by) "
            "SELECT u.id, u.customer_id, 'backfill:users.customer_id' FROM users u "
            "WHERE u.customer_id IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM customers c WHERE c.id = u.customer_id) "
            "AND NOT EXISTS (SELECT 1 FROM user_customers m "
            "                WHERE m.user_id = u.id AND m.customer_id = u.customer_id)"
        ))
        inserted = result.rowcount or 0
    if inserted:
        log.info("user_customers backfill: %d medlemskab(er) oprettet fra users.customer_id", inserted)
    return inserted
