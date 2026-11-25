"""Wardrobe services: unified private wardrobe (verified + declared), care/slot state, shelves, looks with immutable
revisions, date plans with a truthful seven-day view, an idempotent wear log and heuristic outfit suggestions.

Ownership is checked on every referenced item: the caller's inventory is the only source of valid item ids.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta
from typing import Callable

from ..accounts.domain import RECOMMENDATION_WEIGHTS
from ..accounts.domain import effective_settings as account_settings
from ..catalogue.application import SizeIndex
from ..catalogue.domain import parse_size_param
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.errors import FieldError, conflict, not_found, validation_failed
from ..platform.idempotency import IdempotentExecutor, Outcome
from ..platform.ids import new_id
from ..recommendations.application import ItemStats, OutfitSuggester, WeatherContext
from ..recommendations.domain import ATTRIBUTES, OCCASIONS, attribute_errors, derive
from ..recommendations.ports import ItemFeatures
from ..weather.application import WeatherService, local_today
from . import domain as d
from .colours import colour_hex
from .ports import DeclaredRow, LookRevisionRow, PlanRow, WardrobeUoW, WearRow

ROUTE_WEAR = "POST /api/v2/me/wear"


def _iso(x):
    return x.isoformat() if x else None


class WardrobeService:
    def __init__(self, uow_factory: Callable[[], WardrobeUoW], ring: KeyRing, weather: WeatherService, *,
                 clock: Clock = utcnow, lease_s: float = 15.0):
        self.uow_factory = uow_factory
        self.weather = weather
        self.clock = clock
        self.suggester = OutfitSuggester()
        self.executor = IdempotentExecutor(uow_factory, ring, clock, lease_s=lease_s)

    def today(self) -> date:
        return local_today(self.clock())

    # ================================================================ inventory (the ownership source of truth)
    def _inventory(self, uow: WardrobeUoW, user: uuid.UUID, *, include_archived: bool = False) -> dict[uuid.UUID, dict]:
        states = uow.wardrobe.states(user)
        stats = uow.wardrobe.wear_stats(user)
        corrections = uow.wardrobe.sizes(user)
        overrides = uow.wardrobe.attrs(user)
        index = SizeIndex.load(uow.sizes)

        def size_of(item_id, purchased: dict | None) -> dict:
            if item_id in corrections:
                return {"size": index.out(*corrections[item_id]), "size_source": "owner"}
            if purchased:
                return {"size": index.out(purchased.get("system"), purchased.get("code"), purchased.get("label")),
                        "size_source": "purchase"}
            return {"size": None, "size_source": None}

        owned = uow.owned.active_items(user)  # revoked sandbox items leave the wardrobe
        notes = uow.revisions.annotations_for([o.acquisition_revision_id for o in owned])
        inv: dict[uuid.UUID, dict] = {}
        for o in owned:
            product = o.presentation.get("product", {})
            facts = product.get("facts", {}) or {}
            cat_slot = (notes.get(o.acquisition_revision_id, {}).get("slot") or {}).get("value")
            source = "catalogue"
            if cat_slot == "accessory" and d.accessory_position(product.get("category")):
                cat_slot, source = d.accessory_position(product.get("category")), "rule"  # accessory-subtypes@1
            inv[o.id] = self._item(o.id, "verified", name=product.get("name"), category=product.get("category"),
                                   colour=facts.get("colour"), base_slot=cat_slot, base_source=source,
                                   state=states.get(o.id), stats=stats.get(o.id), extra={
                                       "public_serial": o.public_serial, "product_id": product.get("id"),
                                       "claimed_at": _iso(o.claimed_at), "has_photo": False, "archived": False,
                                       **size_of(o.id, o.presentation.get("size"))})
            inv[o.id]["_text"] = " ".join(str(x) for x in (product.get("name"), product.get("category"),
                                                            facts.get("garment_group"), facts.get("description")) if x)
        for x in uow.wardrobe.declared(user):
            if x.archived_at is not None and not include_archived:
                continue
            inv[x.id] = self._item(x.id, "declared", name=x.name, category=x.category, colour=x.colour,
                                   base_slot=x.slot, base_source="declared", state=states.get(x.id),
                                   stats=stats.get(x.id), extra={"public_serial": None, "product_id": None,
                                                                 "claimed_at": None,
                                                                 "has_photo": x.photo_type is not None,
                                                                 "archived": x.archived_at is not None,
                                                                 **size_of(x.id, None)})
            inv[x.id]["_text"] = " ".join(v for v in (x.name, x.category) if v)
        for item_id, v in inv.items():  # thesis appendix lookup (origin rule) unless the owner corrected it
            derived = derive(v["slot"], v.pop("_text"))
            own = overrides.get(item_id, {})
            v["attributes"] = {k: {"value": own[k], "origin": "owner"} if k in own else
                               {"value": derived[k], "origin": "rule"} for k in ATTRIBUTES}
        return inv

    @staticmethod
    def _item(item_id, kind, *, name, category, colour, base_slot, base_source, state, stats, extra) -> dict:
        care, override = state or ("ready", None)
        slot, source = (override, "override") if override else ((base_slot, base_source) if base_slot
                                                                 else (d.UNKNOWN_SLOT, "unknown"))
        return {"id": str(item_id), "kind": kind, "verified": kind == "verified", "name": name,
                "category": category, "colour": colour, "colour_known": colour is not None, "slot": slot,
                "slot_source": source, "care_state": care, "wear_count": stats[0] if stats else 0,
                "last_worn_on": _iso(stats[1]) if stats else None, **extra}

    # ================================================================ items
    def items(self, principal, *, slot: str | None = None, care_state: str | None = None,
              shelf_id: uuid.UUID | None = None, size: str | None = None, sort: str | None = None) -> dict:
        if sort not in (None, "size", "name", "worn"):
            raise validation_failed([FieldError("query.sort", "invalid", "sort must be size, name or worn.")])
        want = parse_size_param(size, "query.size") if size else None
        with self.uow_factory() as uow:
            inv = self._inventory(uow, principal.user_id)
            positions = {x.code: x.position for x in uow.sizes.systems()}
            order = list(inv)
            if shelf_id is not None:
                shelf = uow.wardrobe.shelf(principal.user_id, shelf_id)
                if shelf is None:
                    raise not_found("Shelf not found.")
                order = [i for i in shelf["item_ids"] if i in inv]
        items = [inv[i] for i in order]
        if slot:
            items = [i for i in items if i["slot"] == slot]
        if care_state:
            items = [i for i in items if i["care_state"] == care_state]
        if want:
            items = [i for i in items if i["size"] and (i["size"]["system"], i["size"]["code"]) == want]
        if sort == "size":  # system position, then rank; unsized last; ties by name (design D6)
            items.sort(key=lambda i: ((positions.get(i["size"]["system"], 10**9 - 1), i["size"]["rank"]) if i["size"]
                                      else (10**9, 10**9), (i["name"] or "").lower()))
        elif sort == "name":
            items.sort(key=lambda i: ((i["name"] or "").lower(), i["id"]))
        elif sort == "worn":
            items.sort(key=lambda i: (-i["wear_count"], (i["name"] or "").lower()))
        return {"items": items}

    def item(self, principal, item_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            inv = self._inventory(uow, principal.user_id, include_archived=True)
        if item_id not in inv:
            raise not_found("Item not found.")
        return inv[item_id]

    def declare(self, principal, *, name: str, slot: str, category: str | None, colour: str | None,
                size: dict | None = None) -> dict:
        name = d.check_name(name, "body.name", 80)
        if slot not in d.SLOTS:
            raise validation_failed([FieldError("body.slot", "unknown_slot", "Choose a slot from the registry.")])
        category = (category or "").strip()[:60] or None
        colour = (colour or "").strip()[:40] or None
        with self.uow_factory() as uow:
            if len(uow.wardrobe.declared(principal.user_id)) >= d.MAX_DECLARED:
                raise conflict("WARDROBE_FULL", f"At most {d.MAX_DECLARED} declared items.")
            item_id = new_id()
            if size is not None:
                SizeIndex.load(uow.sizes).require(size["system"], size["code"], "body.size")
            uow.wardrobe.insert_declared(principal.user_id, DeclaredRow(item_id, name, slot, category, colour, None,
                                                                        None, None, self.clock()))
            if size is not None:
                uow.wardrobe.set_size(principal.user_id, item_id, size["system"], size["code"], self.clock())
            uow.commit()
        return self.item(principal, item_id)

    def update_item(self, principal, item_id: uuid.UUID, changes: dict) -> dict:
        with self.uow_factory() as uow:
            inv = self._inventory(uow, principal.user_id, include_archived=True)
            cur = inv.get(item_id)
            if cur is None:
                raise not_found("Item not found.")
            states = uow.wardrobe.states(principal.user_id)
            care, override = states.get(item_id, ("ready", None))
            if "care_state" in changes:
                if changes["care_state"] not in d.CARE_STATES:
                    raise validation_failed([FieldError("body.care_state", "invalid", "Unknown care state.")])
                care = changes["care_state"]
            if "slot_override" in changes:
                if changes["slot_override"] is not None and changes["slot_override"] not in d.SLOTS:
                    raise validation_failed([FieldError("body.slot_override", "unknown_slot", "Unknown slot.")])
                override = changes["slot_override"]
            uow.wardrobe.set_state(principal.user_id, item_id, care, override, self.clock())
            if "attributes" in changes:  # owner corrections; a null value returns that attribute to the rule
                patch = changes["attributes"] or {}
                problems = attribute_errors(patch)
                if problems:
                    raise validation_failed([FieldError("body.attributes", "invalid", "; ".join(problems))])
                current = dict(uow.wardrobe.attrs(principal.user_id).get(item_id, {}))
                for k, v in patch.items():
                    if v is None:
                        current.pop(k, None)
                    else:
                        current[k] = v
                uow.wardrobe.set_attrs(principal.user_id, item_id, current, self.clock())
            if "size" in changes:  # the owner's correction; null returns to the purchased size (or unknown)
                ref = changes["size"]
                if ref is not None:
                    SizeIndex.load(uow.sizes).require(ref["system"], ref["code"], "body.size")
                uow.wardrobe.set_size(principal.user_id, item_id, ref["system"] if ref else None,
                                      ref["code"] if ref else None, self.clock())
            declared_changes = {}
            if cur["kind"] == "declared":
                if "name" in changes:
                    declared_changes["name"] = d.check_name(changes["name"], "body.name", 80)
                if "archived" in changes:
                    declared_changes["archived_at"] = self.clock() if changes["archived"] else None
            elif {"name", "archived"} & set(changes):
                raise validation_failed([FieldError("body", "verified_item", "Verified items keep their catalogue "
                                                                             "name and cannot be archived.")])
            if declared_changes:
                uow.wardrobe.update_declared(principal.user_id, item_id, declared_changes)
            uow.commit()
        return self.item(principal, item_id)

    def put_photo(self, principal, item_id: uuid.UUID, data: bytes) -> dict:
        if len(data) > d.MAX_PHOTO_BYTES:
            raise validation_failed([FieldError("body", "too_large", "Photos are at most 2 MB.")])
        ctype = d.sniff_photo(data)
        if ctype is None:
            raise validation_failed([FieldError("body", "not_an_image", "Upload a JPEG, PNG or WebP image.")])
        with self.uow_factory() as uow:
            inv = self._inventory(uow, principal.user_id, include_archived=True)
            if item_id not in inv:
                raise not_found("Item not found.")
            if inv[item_id]["kind"] != "declared":
                raise validation_failed([FieldError("body", "verified_item", "Verified items use catalogue media.")])
            uow.wardrobe.set_photo(principal.user_id, item_id, data, ctype, hashlib.sha256(data).hexdigest())
            uow.commit()
        return self.item(principal, item_id)

    def photo(self, principal, item_id: uuid.UUID) -> tuple[bytes, str]:
        with self.uow_factory() as uow:
            out = uow.wardrobe.get_photo(principal.user_id, item_id)
        if out is None:
            raise not_found("Photo not found.")
        return out

    # ================================================================ shelves
    def shelves(self, principal) -> list[dict]:
        with self.uow_factory() as uow:
            return [self._shelf_view(s) for s in uow.wardrobe.shelves(principal.user_id)]

    @staticmethod
    def _shelf_view(s: dict) -> dict:
        return {"id": str(s["id"]), "name": s["name"], "item_ids": [str(i) for i in s["item_ids"]],
                "count": len(s["item_ids"])}

    def _check_items(self, inv: dict, item_ids: list[uuid.UUID], field: str) -> None:
        unknown = [i for i in item_ids if i not in inv]
        if unknown:
            raise validation_failed([FieldError(field, "unknown_item", "Some items are not in your wardrobe.")])
        if len(set(item_ids)) != len(item_ids):
            raise validation_failed([FieldError(field, "duplicate_item", "An item appears twice.")])

    def create_shelf(self, principal, name: str, item_ids: list[uuid.UUID]) -> dict:
        name = d.check_name(name, "body.name", 40)
        if len(item_ids) > d.MAX_SHELF_ITEMS:
            raise validation_failed([FieldError("body.item_ids", "too_many", f"At most {d.MAX_SHELF_ITEMS} items.")])
        with self.uow_factory() as uow:
            self._check_items(self._inventory(uow, principal.user_id), item_ids, "body.item_ids")
            if len(uow.wardrobe.shelves(principal.user_id)) >= d.MAX_SHELVES:
                raise conflict("SHELVES_FULL", f"At most {d.MAX_SHELVES} shelves.")
            shelf_id = new_id()
            if not uow.wardrobe.create_shelf(principal.user_id, shelf_id, name, self.clock()):
                raise conflict("SHELF_NAME_TAKEN", "You already have a shelf with that name.")
            uow.wardrobe.replace_shelf_items(shelf_id, item_ids)
            uow.commit()
            return self._shelf_view(uow.wardrobe.shelf(principal.user_id, shelf_id))

    def update_shelf(self, principal, shelf_id: uuid.UUID, *, name: str | None,
                     item_ids: list[uuid.UUID] | None) -> dict:
        with self.uow_factory() as uow:
            shelf = uow.wardrobe.shelf(principal.user_id, shelf_id)
            if shelf is None:
                raise not_found("Shelf not found.")
            if name is not None:
                if not uow.wardrobe.rename_shelf(principal.user_id, shelf_id, d.check_name(name, "body.name", 40)):
                    raise conflict("SHELF_NAME_TAKEN", "You already have a shelf with that name.")
            if item_ids is not None:
                if len(item_ids) > d.MAX_SHELF_ITEMS:
                    raise validation_failed([FieldError("body.item_ids", "too_many",
                                                        f"At most {d.MAX_SHELF_ITEMS} items.")])
                self._check_items(self._inventory(uow, principal.user_id), item_ids, "body.item_ids")
                uow.wardrobe.replace_shelf_items(shelf_id, item_ids)
            uow.commit()
            return self._shelf_view(uow.wardrobe.shelf(principal.user_id, shelf_id))

    def delete_shelf(self, principal, shelf_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            if not uow.wardrobe.delete_shelf(principal.user_id, shelf_id):
                raise not_found("Shelf not found.")
            uow.commit()

    # ================================================================ looks
    def _parse_slots(self, slots: dict) -> dict[str, list[uuid.UUID]]:
        out = {}
        for slot, ids in slots.items():
            try:
                out[slot] = [uuid.UUID(str(i)) for i in ids]
            except ValueError:
                raise validation_failed([FieldError(f"body.slots.{slot}", "unknown_item", "Bad item id.")]) from None
        return out

    def _revision_view(self, rev: LookRevisionRow, inv: dict) -> dict:
        return {"id": str(rev.id), "look_id": str(rev.look_id), "revision_no": rev.revision_no, "name": rev.name,
                "created_at": _iso(rev.created_at), "slots": rev.slots,
                "items": [{"slot": s, **({"item": inv[uuid.UUID(i)]} if uuid.UUID(i) in inv else
                                          {"item": None, "missing_item_id": i})}
                          for s, ids in rev.slots.items() for i in ids]}

    def _look_view(self, uow: WardrobeUoW, look, inv: dict) -> dict:
        rev = uow.wardrobe.revision_by_no(look.id, look.current_revision_no)
        return {"id": str(look.id), "name": look.name, "current_revision_no": look.current_revision_no,
                "deleted": look.deleted_at is not None, "current": self._revision_view(rev, inv)}

    def _save_revision(self, uow: WardrobeUoW, user, look_id, no: int, name: str, slots: dict) -> LookRevisionRow:
        inv = self._inventory(uow, user)
        parsed = self._parse_slots(slots)
        d.check_slots(parsed, {i: v["slot"] for i, v in inv.items()})
        rev = LookRevisionRow(new_id(), look_id, no, name, {s: [str(i) for i in ids] for s, ids in parsed.items() if ids},
                              self.clock())
        uow.wardrobe.insert_revision(rev)
        uow.wardrobe.update_look(look_id, name=name, revision_no=no)
        return rev

    def create_look(self, principal, name: str, slots: dict) -> dict:
        name = d.check_name(name, "body.name", 60)
        with self.uow_factory() as uow:
            if len(uow.wardrobe.looks(principal.user_id)) >= d.MAX_LOOKS:
                raise conflict("LOOKS_FULL", f"At most {d.MAX_LOOKS} looks.")
            look_id = new_id()
            uow.wardrobe.insert_look(principal.user_id, look_id, name, self.clock())
            self._save_revision(uow, principal.user_id, look_id, 1, name, slots)
            uow.commit()
            return self._look_view(uow, uow.wardrobe.look(principal.user_id, look_id),
                                   self._inventory(uow, principal.user_id, include_archived=True))

    def edit_look(self, principal, look_id: uuid.UUID, name: str | None, slots: dict | None) -> dict:
        with self.uow_factory() as uow:
            lk = uow.wardrobe.look(principal.user_id, look_id, lock=True)
            if lk is None or lk.deleted_at is not None:
                raise not_found("Look not found.")
            cur = uow.wardrobe.revision_by_no(look_id, lk.current_revision_no)
            new_name = d.check_name(name, "body.name", 60) if name is not None else lk.name
            self._save_revision(uow, principal.user_id, look_id, lk.current_revision_no + 1, new_name,
                                slots if slots is not None else cur.slots)
            uow.commit()
            return self._look_view(uow, uow.wardrobe.look(principal.user_id, look_id),
                                   self._inventory(uow, principal.user_id, include_archived=True))

    def looks(self, principal) -> list[dict]:
        with self.uow_factory() as uow:
            inv = self._inventory(uow, principal.user_id, include_archived=True)
            return [self._look_view(uow, lk, inv) for lk in uow.wardrobe.looks(principal.user_id)]

    def look(self, principal, look_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            lk = uow.wardrobe.look(principal.user_id, look_id)
            if lk is None:
                raise not_found("Look not found.")
            inv = self._inventory(uow, principal.user_id, include_archived=True)
            view = self._look_view(uow, lk, inv)
            view["revisions"] = [{"id": str(r.id), "revision_no": r.revision_no, "name": r.name,
                                  "created_at": _iso(r.created_at)} for r in uow.wardrobe.revisions_of(look_id)]
            return view

    def revision(self, principal, revision_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            rev = uow.wardrobe.revision(principal.user_id, revision_id)
            if rev is None:
                raise not_found("Look revision not found.")
            return self._revision_view(rev, self._inventory(uow, principal.user_id, include_archived=True))

    def delete_look(self, principal, look_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            lk = uow.wardrobe.look(principal.user_id, look_id, lock=True)
            if lk is None or lk.deleted_at is not None:
                raise not_found("Look not found.")
            uow.wardrobe.soft_delete_look(look_id, self.clock())  # revisions stay for plans and wear history
            uow.commit()

    # ================================================================ planner
    def set_plan(self, principal, plan_date: date, *, look_revision_id: uuid.UUID, occasion: str | None,
                 note: str | None) -> dict:
        d.check_plan_date(plan_date, self.today())
        if occasion is not None and occasion not in d.OCCASIONS:
            raise validation_failed([FieldError("body.occasion", "invalid", "Unknown occasion.")])
        if note is not None and len(note) > 200:
            raise validation_failed([FieldError("body.note", "too_long", "Notes are at most 200 characters.")])
        with self.uow_factory() as uow:
            if uow.wardrobe.revision(principal.user_id, look_revision_id) is None:
                raise validation_failed([FieldError("body.look_revision_id", "unknown_look", "Unknown look revision.")])
            uow.wardrobe.set_plan(principal.user_id, PlanRow(plan_date, look_revision_id, occasion, note or None),
                                  self.clock())
            uow.commit()
        return self.planner(principal, plan_date)["days"][0]

    def clear_plan(self, principal, plan_date: date) -> None:
        with self.uow_factory() as uow:
            uow.wardrobe.clear_plan(principal.user_id, plan_date)
            uow.commit()

    def planner(self, principal, start: date | None) -> dict:
        start = start or self.today()
        dates = [start + timedelta(days=i) for i in range(d.PLANNER_DAYS)]
        with self.uow_factory() as uow:
            inv = self._inventory(uow, principal.user_id, include_archived=True)
            plans = {p.plan_date: p for p in uow.wardrobe.plans(principal.user_id, dates[0], dates[-1])}
            wear: dict[date, list] = {}
            for w in uow.wardrobe.wear(principal.user_id, dates[0], dates[-1]):
                wear.setdefault(w.worn_on, []).append(self._wear_view(w))
            revs = {p.look_revision_id: uow.wardrobe.revision(principal.user_id, p.look_revision_id)
                    for p in plans.values()}
        weather = self.weather.day_summaries(principal.user_id, dates)
        today = self.today()
        days = []
        for day in dates:
            p = plans.get(day)
            days.append({"date": day.isoformat(), "is_today": day == today, "past": day < today,
                         "plan": None if p is None else {
                             "look_revision": self._revision_view(revs[p.look_revision_id], inv),
                             "occasion": p.occasion, "note": p.note},
                         "worn": wear.get(day, []), "weather": weather[day]})
        return {"from": dates[0].isoformat(), "days": days}

    # ================================================================ wear
    @staticmethod
    def _wear_view(w: WearRow) -> dict:
        return {"id": str(w.id), "worn_on": w.worn_on.isoformat(),
                "look_revision_id": str(w.look_revision_id) if w.look_revision_id else None,
                "item_ids": [str(i) for i in w.item_ids], "created_at": _iso(w.created_at)}

    def log_wear(self, principal, *, worn_on: date, look_revision_id: uuid.UUID | None,
                 item_ids: list[uuid.UUID] | None, idem_key: str) -> Outcome:
        d.check_wear_date(worn_on, self.today())
        if (look_revision_id is None) == (not item_ids):
            raise validation_failed([FieldError("body", "one_of", "Send either look_revision_id or item_ids.")])
        user = principal.user_id
        body = {"worn_on": worn_on.isoformat(), "look_revision_id": str(look_revision_id) if look_revision_id else None,
                "item_ids": sorted(str(i) for i in item_ids or [])}

        def execute(uow: WardrobeUoW, rec):
            inv = self._inventory(uow, user, include_archived=True)
            ids = list(item_ids or [])
            if look_revision_id is not None:
                rev = uow.wardrobe.revision(user, look_revision_id)
                if rev is None:
                    raise validation_failed([FieldError("body.look_revision_id", "unknown_look",
                                                        "Unknown look revision.")])
                ids = [uuid.UUID(i) for slot_ids in rev.slots.values() for i in slot_ids]
            self._check_items(inv, ids, "body.item_ids")
            row = WearRow(new_id(), worn_on, look_revision_id, tuple(sorted(set(ids))), self.clock())
            uow.wardrobe.insert_wear(user, row)
            return 201, self._wear_view(row)

        return self.executor.run(actor_id=user, route=ROUTE_WEAR, key=idem_key, body=body, execute=execute)

    def wear_log(self, principal, start: date | None, end: date | None) -> dict:
        end = end or self.today()
        start = start or end - timedelta(days=30)
        if start > end or (end - start).days > 366:
            raise validation_failed([FieldError("query", "bad_range", "Use a range of at most one year.")])
        with self.uow_factory() as uow:
            return {"entries": [self._wear_view(w) for w in uow.wardrobe.wear(principal.user_id, start, end)]}

    def delete_wear(self, principal, wear_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            if not uow.wardrobe.delete_wear(principal.user_id, wear_id):
                raise not_found("Wear entry not found.")
            uow.commit()

    # ================================================================ suggestions
    def suggestions(self, principal, *, on: date | None, limit: int, rain: bool | None, hot: bool | None,
                    occasion: str | None = None) -> dict:
        on = on or self.today()
        occasion = occasion or "casual"
        if not 1 <= limit <= 5:
            raise validation_failed([FieldError("query.limit", "out_of_range", "limit must be 1-5.")])
        if occasion not in OCCASIONS:
            raise validation_failed([FieldError("query.occasion", "invalid", "occasion must be one of: "
                                                + ", ".join(OCCASIONS) + ".")])
        with self.uow_factory() as uow:
            prefs = account_settings(uow.accounts.settings(principal.user_id)[0])
            if not prefs["style_suggestions"]:  # turned off in Settings (add-wearhouse-settings-security)
                return {"enabled": False, "date": on.isoformat(), "suggestions": [], "reasons": ["turned_off_in_settings"],
                        "candidates_considered": 0, "ready_items": 0, "occasion_used": False,
                        "style": prefs["recommendation_style"], "weights": None, "model": None,
                        "weather": {"source": "DISABLED", "rain": None, "hot": None}}
            inv = self._inventory(uow, principal.user_id)
            worn = uow.wardrobe.wear_stats(principal.user_id)
            feedback = uow.reco_events.counts(principal.user_id)
        ready = [v for v in inv.values() if v["care_state"] == "ready" and v["slot"] != d.UNKNOWN_SLOT]
        if not prefs["weather_in_suggestions"]:  # off in Settings: weather unknown, so no weather rule applies
            weather = WeatherContext(None, None, "DISABLED")
        elif rain is not None or hot is not None:
            weather = WeatherContext(rain, hot, "MANUAL")
        else:
            day = self.weather.day_summaries(principal.user_id, [on])[on]  # within the forecast horizon only
            weather = (WeatherContext(day["rain"], day["hot"], day["source"]) if day["status"] == "forecast"
                       else WeatherContext(None, None, "NONE"))
        features = [ItemFeatures(item_id=v["id"], slot=v["slot"], colour_hex=colour_hex(v["colour"])) for v in ready]
        style = prefs["recommendation_style"]
        stats = {}
        for v in ready:
            iid = uuid.UUID(v["id"])
            chosen, shown = feedback.get(iid, (0, 0))
            last = worn.get(iid, (0, None))[1]
            stats[v["id"]] = ItemStats(chosen=chosen, recommended=shown,
                                       days_since_worn=float((on - last).days) if last and last <= on else None)
        attrs = {v["id"]: {k: a["value"] for k, a in v["attributes"].items()} for v in ready}
        out = self.suggester.suggest(features, attrs=attrs, stats=stats, weather=weather, occasion=occasion,
                                     limit=limit, weights=RECOMMENDATION_WEIGHTS[style], style=style)
        run_id = new_id()
        with self.uow_factory() as uow:  # the run is private to its owner; nothing is counted until it is displayed
            uow.reco_events.create_run(run_id=run_id, user_id=principal.user_id, now=self.clock(),
                                       context={"date": on.isoformat(), "occasion": occasion, "weather": out["weather"],
                                                "style": style, "weights": out["weights"], "ruleset": out["ruleset"]},
                                       suggestions=[s["item_ids"] for s in out["suggestions"]])
            uow.commit()
        out.update({"enabled": True, "run_id": str(run_id), "date": on.isoformat(), "occasion_used": True,
                    "ready_items": len(ready)})
        for s in out["suggestions"]:
            s["items"] = [inv[uuid.UUID(i)] for i in s["item_ids"]]
        return out

    def suggestion_event(self, principal, run_id: uuid.UUID, *, kind: str, index: int | None) -> dict:
        """`displayed`: count each shown item once per run. `chosen`: once per run (same choice again is a no-op)."""
        now = self.clock()
        with self.uow_factory() as uow:
            run = uow.reco_events.run(principal.user_id, run_id)
            if run is None:
                raise not_found("Recommendation run not found.")
            shown = run["suggestions"]
            if kind == "chosen":
                if index is None or not 0 <= index < len(shown):
                    raise validation_failed([FieldError("body.index", "out_of_range",
                                                        f"index must be 0-{max(len(shown) - 1, 0)}.")])
                existing = uow.reco_events.choice(run_id)
                if existing is not None and existing["suggestion_index"] != index:
                    raise conflict("ALREADY_CHOSEN", "A different suggestion from this run was already chosen.")
                if existing is None:
                    uow.reco_events.record_choice(principal.user_id, run_id, index,
                                                  [uuid.UUID(i) for i in shown[index]], now)
            # choosing implies the suggestions were seen; displaying twice never counts twice
            uow.reco_events.record_displayed(principal.user_id, run_id,
                                             sorted({uuid.UUID(i) for s in shown for i in s}), now)
            choice = uow.reco_events.choice(run_id)
            uow.commit()
        return {"run_id": str(run_id), "displayed": True,
                "chosen_index": choice["suggestion_index"] if choice else None}

    # ================================================================ safe projections (social sharing, design D2)
    def projection(self, uow: WardrobeUoW, owner: uuid.UUID, revision_id: uuid.UUID) -> dict | None:
        """What OTHER people may see of a look revision: slot, name, category, colour, verified and a store link for
        verified items whose product is on sale. Never serials, item ids, photos, care state or wear data."""
        rev = uow.wardrobe.revision(owner, revision_id)
        if rev is None:
            return None
        inv = self._inventory(uow, owner, include_archived=True)
        pids = {uuid.UUID(v["product_id"]) for v in inv.values() if v["product_id"]}
        on_sale = uow.revisions.on_sale(list(pids))
        items = []
        for slot, ids in rev.slots.items():
            for raw in ids:
                v = inv.get(uuid.UUID(raw))
                if v is None:
                    items.append({"slot": slot, "name": None, "category": None, "colour": None, "verified": False,
                                  "product_id": None})
                    continue
                pid = v["product_id"]
                items.append({"slot": slot, "name": v["name"], "category": v["category"], "colour": v["colour"],
                              "verified": v["verified"],
                              "product_id": pid if pid and uuid.UUID(pid) in on_sale else None})
        return {"look_name": rev.name, "revision_no": rev.revision_no, "items": items}

    def week_projection(self, uow: WardrobeUoW, owner: uuid.UUID, start: date) -> list[dict]:
        """Seven dates of planned looks (projections only): no wear, weather or location."""
        dates = [start + timedelta(days=i) for i in range(d.PLANNER_DAYS)]
        plans = {p.plan_date: p for p in uow.wardrobe.plans(owner, dates[0], dates[-1])}
        out = []
        for day in dates:
            p = plans.get(day)
            out.append({"date": day.isoformat(), "occasion": p.occasion if p else None,
                        "look": self.projection(uow, owner, p.look_revision_id) if p else None})
        return out

    # ================================================================ accounts integration
    def export_data(self, uow: WardrobeUoW, user_id: uuid.UUID) -> dict:
        """Account export: everything except photo bytes (sha256 + type only)."""
        inv = self._inventory(uow, user_id, include_archived=True)
        feedback = uow.reco_events.export(user_id)
        declared = {x.id: x for x in uow.wardrobe.declared(user_id)}
        looks = []
        for lk in uow.wardrobe.looks(user_id):
            looks.append({"id": str(lk.id), "name": lk.name, "revisions": [
                {"revision_no": r.revision_no, "name": r.name, "slots": r.slots, "created_at": _iso(r.created_at)}
                for r in uow.wardrobe.revisions_of(lk.id)]})
        far = self.today() + timedelta(days=d.PLAN_AHEAD_DAYS)
        return {"items": [{**v, "photo_sha256": declared[uuid.UUID(v["id"])].photo_sha256
                           if uuid.UUID(v["id"]) in declared else None} for v in inv.values()],
                "shelves": [self._shelf_view(s) for s in uow.wardrobe.shelves(user_id)],
                "looks": looks, "recommendation_feedback": feedback,
                "plans": [{"date": p.plan_date.isoformat(), "look_revision_id": str(p.look_revision_id),
                           "occasion": p.occasion, "note": p.note}
                          for p in uow.wardrobe.plans(user_id, date(2000, 1, 1), far)],
                "wear": [self._wear_view(w) for w in uow.wardrobe.wear(user_id, date(2000, 1, 1), far)]}
