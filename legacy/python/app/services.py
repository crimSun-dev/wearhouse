"""Services: the only code that mutates state (via SQLAlchemy sessions = interface I3)."""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import domain
from .models import Garment, Outfit, OutfitItem, Product, WearLog
from .rules import Context
from .schemas import GarmentIn, OutfitIn
from .scoring import ScoredOutfit, recommend


class DomainError(Exception):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class InvalidError(DomainError):
    status_code = 422


# ------------------------------------------------------------------ mapping
def full_attrs(g: Garment) -> dict:
    return {**domain.ATTR_DEFAULTS, **(g.attrs or {})}


def garment_out(g: Garment) -> dict:
    return {
        "id": g.id, "name": g.name, "slot": g.slot, "attrs": full_attrs(g), "gtin": g.gtin, "serial": g.serial,
        "origin": "registered" if g.serial else "manual", "times_recommended": g.times_recommended,
        "times_chosen": g.times_chosen, "last_worn_at": g.last_worn_at,
    }


def to_domain(g: Garment) -> domain.Garment:
    a = full_attrs(g)
    return domain.Garment(
        id=str(g.id), name=g.name, slot=g.slot, color_hex=a["color_hex"], style=a["style"],
        rain_suitable=bool(a["rain_suitable"]), heavy=bool(a["heavy"]), long_sleeve=bool(a["long_sleeve"]),
        long_bottom=bool(a["long_bottom"]), formality=int(a["formality"]), times_recommended=g.times_recommended,
        times_chosen=g.times_chosen, last_worn_at=g.last_worn_at,
    )


# ----------------------------------------------------------------- wardrobe
def list_wardrobe(s: Session, user_id: uuid.UUID) -> list[Garment]:
    order = {slot: i for i, slot in enumerate(domain.SLOTS)}
    rows = s.scalars(select(Garment).where(Garment.owner_id == user_id)).all()
    return sorted(rows, key=lambda g: (order.get(g.slot, 99), g.name))


def add_garment(s: Session, user_id: uuid.UUID, body: GarmentIn) -> Garment:
    g = Garment(owner_id=user_id, name=body.name.strip(), slot=body.slot, attrs=body.attrs.model_dump())
    s.add(g)
    s.commit()
    return g


def delete_garment(s: Session, user_id: uuid.UUID, garment_id: uuid.UUID) -> None:
    g = s.get(Garment, garment_id)
    if g is None or g.owner_id != user_id:
        raise NotFoundError("garment not found")
    if s.scalar(select(OutfitItem.outfit_id).where(OutfitItem.garment_id == garment_id).limit(1)) is not None:
        raise ConflictError("garment is used in a saved outfit; delete or change that outfit first")
    s.delete(g)
    s.commit()


# ------------------------------------------------------------------ outfits
def _outfit_items(s: Session, outfit_id: uuid.UUID) -> list[Garment]:
    q = select(Garment).join(OutfitItem, OutfitItem.garment_id == Garment.id).where(OutfitItem.outfit_id == outfit_id)
    return s.scalars(q).all()


def outfit_out(s: Session, o: Outfit) -> dict:
    order = {slot: i for i, slot in enumerate(domain.SLOTS)}
    items = sorted(_outfit_items(s, o.id), key=lambda g: order.get(g.slot, 99))
    return {"id": o.id, "label": o.label, "planned_for": o.planned_for, "occasion": o.occasion,
            "items": [garment_out(g) for g in items]}


def create_outfit(s: Session, user_id: uuid.UUID, body: OutfitIn) -> Outfit:
    ids = list(dict.fromkeys(body.items))
    garments = s.scalars(select(Garment).where(Garment.id.in_(ids), Garment.owner_id == user_id)).all()
    if len(garments) != len(ids):
        raise InvalidError("unknown garment id(s) for this wardrobe")
    slots = [g.slot for g in garments]
    clash = sorted({x for x in slots if slots.count(x) > 1})
    if clash:
        raise ConflictError(f"slot clash: more than one item in {clash}")
    if "dress" in slots and ("top" in slots or "bottom" in slots):
        raise ConflictError("slot clash: a dress fills both the top and bottom slots")
    o = Outfit(owner_id=user_id, label=body.label, planned_for=body.planned_for, occasion=body.occasion)
    s.add(o)
    s.flush()
    for g in garments:
        s.add(OutfitItem(outfit_id=o.id, slot=g.slot, garment_id=g.id))
    s.commit()
    return o


WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def week_range(week: str) -> tuple[date, date]:
    m = WEEK_RE.match(week)
    if not m:
        raise InvalidError("week must look like 2026-W48")
    try:
        start = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError as exc:
        raise InvalidError(str(exc)) from exc
    return start, start + timedelta(days=6)


def list_outfits(s: Session, user_id: uuid.UUID, week: str | None = None) -> list[Outfit]:
    q = select(Outfit).where(Outfit.owner_id == user_id)
    if week:
        start, end = week_range(week)
        q = q.where(Outfit.planned_for >= start, Outfit.planned_for <= end)
    return s.scalars(q.order_by(Outfit.planned_for, Outfit.label)).all()


def get_outfit(s: Session, user_id: uuid.UUID, outfit_id: uuid.UUID) -> Outfit:
    o = s.get(Outfit, outfit_id)
    if o is None or o.owner_id != user_id:
        raise NotFoundError("outfit not found")
    return o


def delete_outfit(s: Session, user_id: uuid.UUID, outfit_id: uuid.UUID) -> None:
    o = get_outfit(s, user_id, outfit_id)
    s.delete(o)
    s.commit()


def wear_outfit(s: Session, user_id: uuid.UUID, outfit_id: uuid.UUID, worn_on: date) -> None:
    o = get_outfit(s, user_id, outfit_id)
    ids = [g.id for g in _outfit_items(s, o.id)]
    s.add(WearLog(outfit_id=o.id, worn_on=worn_on))
    if ids:
        s.execute(
            update(Garment)
            .where(Garment.id.in_(ids))
            .values(last_worn_at=worn_on, times_chosen=Garment.times_chosen + 1)
            .execution_options(synchronize_session=False)
        )
    s.commit()


# --------------------------------------------------------------- recommend
def recommend_and_record(s: Session, user_id: uuid.UUID, ctx: Context, today: date, k: int = 5) -> tuple[list[ScoredOutfit], dict]:
    rows = list_wardrobe(s, user_id)
    by_id = {str(g.id): g for g in rows}
    recs = recommend([to_domain(g) for g in rows], ctx, today, k)
    shown = {g.id for r in recs for g in r.outfit.items}
    if shown:  # feeds the "recommended" denominator of pref (Eq. 8)
        s.execute(
            update(Garment)
            .where(Garment.id.in_([uuid.UUID(x) for x in shown]))
            .values(times_recommended=Garment.times_recommended + 1)
            .execution_options(synchronize_session=False)
        )
        s.commit()
    return recs, by_id


# ------------------------------------------------------------------- avatar
DEFAULT_TEMPLATES = {
    "top": "top_shirt.glb", "dress": "dress.glb", "outer": "outer_jacket.glb",
    "footwear": "footwear_sneaker.glb", "accessory": None,
}


def avatar_for(s: Session, user_id: uuid.UUID, outfit_id: uuid.UUID, gender: str | None) -> dict:
    o = get_outfit(s, user_id, outfit_id)
    slots: dict[str, dict] = {}
    for g in _outfit_items(s, o.id):
        a = full_attrs(g)
        product = s.get(Product, g.gtin) if g.gtin else None
        if g.slot == "bottom":
            template = "bottom_pants.glb" if a["long_bottom"] else "bottom_skirt.glb"
        else:
            template = DEFAULT_TEMPLATES.get(g.slot)
        if product and product.glb_template:
            template = product.glb_template
        slots[g.slot] = {
            "garment_id": str(g.id), "name": g.name, "template": template,
            "texture": product.image_url if product else None, "tint": a["color_hex"],
        }
    body = "female_base.glb" if (gender or "female") == "female" else "male_base.glb"
    covers = {"dress": ["top", "bottom"]} if "dress" in slots else {}
    return {"outfit_id": str(o.id), "body": {"model": body, "gender": gender or "female"}, "slots": slots, "covers": covers}
