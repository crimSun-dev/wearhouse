"""Sizes (add-wearhouse-sizes): the size registry as managed objects, product sizes (rule-generated mock data or
staff-set; H&M supplies none), and each person's usual sizes.
"""
from __future__ import annotations

import re
import uuid
from typing import Callable

from ..identity.domain import Capability, Principal, require
from ..platform.clock import Clock, utcnow
from ..platform.errors import FieldError, conflict, not_found, unauthenticated, validation_failed
from .application import SizeIndex
from .ports import ProductSize, SizeSystem, SizeValue

MAX_ASSIGN = 20_000
SYSTEM_CODE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SIZE_CODE = re.compile(r"^[A-Za-z0-9.]{1,8}$")
SLOTS = ("top", "outer", "bottom", "dress", "footwear", "underwear", "bag", "headwear", "eyewear", "earrings", "necklace", "tie",
         "scarf", "belt", "wrist", "ring", "accessory")


class SizingService:
    def __init__(self, uow_factory: Callable, *, clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.clock = clock

    # ================================================================ registry
    def registry(self, *, staff: Principal | None = None) -> dict:
        """Active systems and sizes (public). Staff with catalogue:ingest also see retired ones."""
        if staff is not None:
            require(staff, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            systems, values = uow.sizes.systems(), uow.sizes.values()
        everything = staff is not None
        out = []
        for s in systems:
            if not (s.active or everything):
                continue
            sizes = [{"code": v.code, "label": v.label, "rank": v.rank, "common": v.common,
                      **({"active": v.active} if everything else {})}
                     for v in values if v.system == s.code and (v.active or everything)]
            out.append({"code": s.code, "label": s.label, "position": s.position, "slots": list(s.slots),
                        **({"active": s.active} if everything else {}), "sizes": sizes})
        return {"systems": out}

    def put_system(self, principal: Principal, code: str, *, label: str, position: int, slots: list[str],
                   active: bool) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        errors = []
        if not SYSTEM_CODE.fullmatch(code):
            errors.append(FieldError("path.code", "invalid", "Use 2-32 lowercase letters, digits or _."))
        if not 1 <= len(label.strip()) <= 60:
            errors.append(FieldError("body.label", "invalid", "Label must be 1-60 characters."))
        if any(s not in SLOTS for s in slots):
            errors.append(FieldError("body.slots", "unknown_slot", "Slots must come from the wardrobe registry."))
        if errors:
            raise validation_failed(errors)
        with self.uow_factory() as uow:
            others = [s for s in uow.sizes.systems() if s.code != code and s.active]
            taken = sorted({x for s in others for x in s.slots} & set(slots)) if active else []
            if taken:
                raise validation_failed([FieldError("body.slots", "slot_taken",
                                                    "Another active system is already the default for: "
                                                    + ", ".join(taken) + ".")])
            uow.sizes.put_system(SizeSystem(code, label.strip(), position, tuple(dict.fromkeys(slots)), active),
                                 self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.size_system_saved",
                             target_type="size_system", target_id=code,
                             details={"label": label.strip(), "position": position, "slots": slots, "active": active})
            uow.commit()
        return self.registry(staff=principal)

    def put_size(self, principal: Principal, system: str, code: str, *, label: str, rank: int, common: bool,
                 active: bool) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        errors = []
        if not SIZE_CODE.fullmatch(code):
            errors.append(FieldError("path.size_code", "invalid", "Use 1-8 letters, digits or dots."))
        if not 1 <= len(label.strip()) <= 20:
            errors.append(FieldError("body.label", "invalid", "Label must be 1-20 characters."))
        if not 1 <= rank <= 100_000:
            errors.append(FieldError("body.rank", "out_of_range", "Rank must be 1-100,000."))
        if errors:
            raise validation_failed(errors)
        with self.uow_factory() as uow:
            if system not in {s.code for s in uow.sizes.systems()}:
                raise not_found("Size system not found.")
            uow.sizes.put_value(SizeValue(system, code, label.strip(), rank, common, active), self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.size_saved", target_type="size_value",
                             target_id=f"{system}:{code}",
                             details={"label": label.strip(), "rank": rank, "common": common, "active": active})
            uow.commit()
        return self.registry(staff=principal)

    # ================================================================ product sizes
    @staticmethod
    def sizes_view(index: SizeIndex, sizes: list[ProductSize]) -> list[dict]:
        return [{**index.out(s.system, s.code), "origin": s.origin} for s in sizes]

    def product_sizes(self, product_id: uuid.UUID, *, staff: Principal | None = None) -> dict:
        if staff is not None:
            require(staff, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            ident = uow.publishing.product_identity(product_id)
            if ident is None or (staff is None and ident["publication_state"] != "published"):
                raise not_found("Product not found.")
            index = SizeIndex.load(uow.sizes)
            sizes = uow.sizes.product_sizes([product_id]).get(product_id, [])
        return {"product_id": str(product_id), "one_size": not sizes, "sizes": self.sizes_view(index, sizes)}

    def set_product_sizes(self, principal: Principal, product_id: uuid.UUID, refs: list[dict]) -> dict:
        """Replace a product's sizes (one system). An empty list makes it one-size."""
        require(principal, Capability.INGEST_PRODUCTS)
        if len(refs) > 40:
            raise validation_failed([FieldError("body.sizes", "too_many", "At most 40 sizes.")])
        with self.uow_factory() as uow:
            if uow.publishing.product_identity(product_id) is None:
                raise not_found("Product not found.")
            index = SizeIndex.load(uow.sizes)
            values = [index.require(r["system"], r["code"], f"body.sizes.{i}") for i, r in enumerate(refs)]
            if len({v.system for v in values}) > 1:
                raise validation_failed([FieldError("body.sizes", "mixed_systems",
                                                    "A product's sizes must come from one size system.")])
            unique = list({(v.system, v.code): v for v in values}.values())
            before = uow.sizes.product_sizes([product_id]).get(product_id, [])
            uow.sizes.set_product_sizes(product_id, [ProductSize(v.system, v.code, "staff") for v in unique],
                                        self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.product_sizes_saved", target_type="product",
                             target_id=str(product_id),
                             details={"sizes": [f"{v.system}:{v.code}" for v in unique],
                                      "previous": [f"{s.system}:{s.code}" for s in before]})
            uow.commit()
        return self.product_sizes(product_id, staff=principal)

    def assign_missing(self, principal: Principal, *, limit: int = 5000) -> dict:
        """Mock sizes for published products without any: the common active sizes of the active system whose default
        slots include the product's slot (origin `rule`). Accessories and unknown slots stay one-size."""
        require(principal, Capability.INGEST_PRODUCTS)
        if not 1 <= limit <= MAX_ASSIGN:
            raise validation_failed([FieldError("query.limit", "out_of_range", f"limit must be 1-{MAX_ASSIGN}.")])
        with self.uow_factory() as uow:
            systems = [s for s in uow.sizes.systems() if s.active]
            values = [v for v in uow.sizes.values() if v.active and v.common]
            by_slot = {}
            for s in systems:
                sizes = [v for v in values if v.system == s.code]
                for slot in s.slots:
                    if sizes:
                        by_slot.setdefault(slot, sizes)
            todo = uow.sizes.unsized_published(sorted(by_slot), limit + 1)
            more, todo = len(todo) > limit, todo[:limit]
            rows = [(pid, ProductSize(v.system, v.code, "rule")) for pid, slot in todo for v in by_slot[slot]]
            uow.sizes.add_product_sizes(rows, self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.product_sizes_assigned",
                             target_type="product", target_id="*",
                             details={"products": len(todo), "rows": len(rows), "origin": "rule",
                                      "by_slot": {k: f"{v[0].system}:{v[0].code}-{v[-1].code}"
                                                  for k, v in by_slot.items()}})
            uow.commit()
        return {"assigned": len(todo), "more_remaining": more}

    # ================================================================ usual sizes
    def usual_sizes(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            index = SizeIndex.load(uow.sizes)
            prefs = uow.sizes.preferences(principal.user_id)
        out = []
        for s in sorted(index.systems.values(), key=lambda s: (s.position, s.code)):
            if not s.active and s.code not in prefs:
                continue
            out.append({"system": s.code, "label": s.label, "usual": index.out(s.code, prefs.get(s.code))})
        return {"systems": out}

    def set_usual_sizes(self, principal: Principal, usual: dict[str, str | None]) -> dict:
        if len(usual) > 20:
            raise validation_failed([FieldError("body.usual", "too_many", "Too many systems.")])
        with self.uow_factory() as uow:
            index = SizeIndex.load(uow.sizes)
            now = self.clock()
            for system, code in usual.items():
                if code is None:
                    if system not in index.systems:
                        raise validation_failed([FieldError(f"body.usual.{system}", "unknown_system",
                                                            "Unknown size system.")])
                else:
                    index.require(system, code, f"body.usual.{system}")
                uow.sizes.set_preference(principal.user_id, system, code, now)
            uow.commit()
        return self.usual_sizes(principal)

    def browse_refs(self, viewer: Principal | None) -> tuple[tuple[str, str], ...]:
        """The caller's usual sizes for `my_sizes=true` (signed in only)."""
        if viewer is None:
            raise unauthenticated("Sign in to filter by your sizes.")
        with self.uow_factory() as uow:
            refs = tuple(sorted(uow.sizes.preferences(viewer.user_id).items()))
        if not refs:
            raise conflict("NO_USUAL_SIZES", "Set your usual sizes first.")
        return refs

    # ------------------------------------------------------------------ accounts integration
    def export_data(self, uow, user_id: uuid.UUID) -> dict:
        return {"usual_sizes": [{"system": s, "code": c} for s, c in sorted(uow.sizes.preferences(user_id).items())]}

    def erase(self, uow, user_id: uuid.UUID) -> None:
        uow.sizes.erase_preferences(user_id)
