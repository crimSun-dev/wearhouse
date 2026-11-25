"""Idempotent seeding of the synthetic demo data."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    ActivationAttempt,
    Garment,
    GarmentCode,
    InterfaceLog,
    Outfit,
    OutfitItem,
    Product,
    WearLog,
)
from .seed_data import DEMO_USER_ID, PRODUCTS, seed_garment_rows


def seed(session: Session) -> dict:
    """Insert missing products and seed garments. Safe to run any number of times;
    existing rows (and their wear statistics) are left untouched."""
    added_products = added_garments = 0
    for p in PRODUCTS:
        if session.get(Product, p["gtin"]) is None:
            session.add(Product(**p))
            added_products += 1
    session.flush()
    for row in seed_garment_rows():
        if session.get(Garment, row["id"]) is None:
            session.add(Garment(owner_id=DEMO_USER_ID, **row))
            added_garments += 1
    session.commit()
    return {"products_added": added_products, "garments_added": added_garments}


def reset_demo(session: Session) -> None:
    """Wipe outfits, wear history, registrations and logs, then re-seed (fresh demo run)."""
    for model in (WearLog, OutfitItem, Outfit, ActivationAttempt, InterfaceLog):
        session.execute(delete(model))
    session.execute(delete(Garment))
    session.execute(delete(GarmentCode))
    session.commit()
    seed(session)


def has_garments(session: Session) -> bool:
    return session.scalar(select(Garment.id).limit(1)) is not None
