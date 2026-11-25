from __future__ import annotations

from sqlalchemy import delete, func, insert, null, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ..ports import DeclaredRow, LookRevisionRow, LookRow, PlanRow, WearRow
from .tables import (look, look_revision, plan_entry, wardrobe_declared_item, wardrobe_item_state, wardrobe_shelf,
                     wardrobe_shelf_item, wear_entry, wear_entry_item)

_D = wardrobe_declared_item


def _declared(r) -> DeclaredRow:
    return DeclaredRow(r.id, r.name, r.slot, r.category, r.colour, r.photo_type, r.photo_sha256, r.archived_at,
                       r.created_at)


def _look(r) -> LookRow:
    return LookRow(r.id, r.name, r.current_revision_no, r.deleted_at, r.created_at)


def _rev(r) -> LookRevisionRow:
    return LookRevisionRow(r.id, r.look_id, r.revision_no, r.name, r.slots, r.created_at)


class SqlWardrobeRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------ declared items
    def insert_declared(self, user_id, row):
        self.conn.execute(insert(_D).values(id=row.id, user_id=user_id, name=row.name, slot=row.slot,
                                            category=row.category, colour=row.colour, created_at=row.created_at))

    def declared(self, user_id):
        cols = [c for c in _D.c if c.name != "photo"]  # never load photo bytes for lists
        rows = self.conn.execute(select(*cols).where(_D.c.user_id == user_id).order_by(_D.c.created_at, _D.c.id)).all()
        return [_declared(r) for r in rows]

    def update_declared(self, user_id, item_id, values):
        return self.conn.execute(update(_D).where(_D.c.id == item_id, _D.c.user_id == user_id)
                                 .values(**values)).rowcount == 1

    def set_photo(self, user_id, item_id, data, ctype, sha256):
        return self.update_declared(user_id, item_id, {"photo": data, "photo_type": ctype, "photo_sha256": sha256})

    def get_photo(self, user_id, item_id):
        r = self.conn.execute(select(_D.c.photo, _D.c.photo_type).where(_D.c.id == item_id, _D.c.user_id == user_id)
                              ).one_or_none()
        return (bytes(r.photo), r.photo_type) if r and r.photo is not None else None

    # ------------------------------------------------------------------ item state
    def states(self, user_id):
        rows = self.conn.execute(select(wardrobe_item_state).where(wardrobe_item_state.c.user_id == user_id)).all()
        return {r.item_id: (r.care_state, r.slot_override) for r in rows}

    def sizes(self, user_id):
        rows = self.conn.execute(select(wardrobe_item_state.c.item_id, wardrobe_item_state.c.size_system,
                                        wardrobe_item_state.c.size_code)
                                 .where(wardrobe_item_state.c.user_id == user_id,
                                        wardrobe_item_state.c.size_code.is_not(None))).all()
        return {r.item_id: (r.size_system, r.size_code) for r in rows}

    def attrs(self, user_id):
        rows = self.conn.execute(select(wardrobe_item_state.c.item_id, wardrobe_item_state.c.attrs)
                                 .where(wardrobe_item_state.c.user_id == user_id,
                                        wardrobe_item_state.c.attrs.is_not(None))).all()
        return {r.item_id: dict(r.attrs) for r in rows}

    def set_attrs(self, user_id, item_id, attrs, now):
        value = attrs if attrs else null()  # SQL NULL (a Python None would be stored as JSON null)
        stmt = pg_insert(wardrobe_item_state).values(user_id=user_id, item_id=item_id, attrs=value, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id", "item_id"], set_={
            "attrs": value, "updated_at": now}))

    def set_size(self, user_id, item_id, system, code, now):
        stmt = pg_insert(wardrobe_item_state).values(user_id=user_id, item_id=item_id, size_system=system,
                                                     size_code=code, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id", "item_id"], set_={
            "size_system": system, "size_code": code, "updated_at": now}))

    def set_state(self, user_id, item_id, care_state, slot_override, now):
        stmt = pg_insert(wardrobe_item_state).values(user_id=user_id, item_id=item_id, care_state=care_state,
                                                     slot_override=slot_override, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id", "item_id"], set_={
            "care_state": care_state, "slot_override": slot_override, "updated_at": now}))

    # ------------------------------------------------------------------ shelves
    def _shelf_items(self, shelf_id):
        return [r.item_id for r in self.conn.execute(select(wardrobe_shelf_item.c.item_id)
                                                     .where(wardrobe_shelf_item.c.shelf_id == shelf_id)
                                                     .order_by(wardrobe_shelf_item.c.position)).all()]

    def shelves(self, user_id):
        rows = self.conn.execute(select(wardrobe_shelf).where(wardrobe_shelf.c.user_id == user_id)
                                 .order_by(wardrobe_shelf.c.created_at, wardrobe_shelf.c.id)).all()
        return [{"id": r.id, "name": r.name, "item_ids": self._shelf_items(r.id)} for r in rows]

    def shelf(self, user_id, shelf_id):
        r = self.conn.execute(select(wardrobe_shelf).where(wardrobe_shelf.c.id == shelf_id,
                                                           wardrobe_shelf.c.user_id == user_id)
                              .with_for_update()).one_or_none()
        return {"id": r.id, "name": r.name, "item_ids": self._shelf_items(r.id)} if r else None

    def create_shelf(self, user_id, shelf_id, name, now):
        return self.conn.execute(pg_insert(wardrobe_shelf).values(id=shelf_id, user_id=user_id, name=name,
                                                                  created_at=now)
                                 .on_conflict_do_nothing(index_elements=["user_id", "name"])
                                 .returning(wardrobe_shelf.c.id)).first() is not None  # rowcount is -1 here

    def rename_shelf(self, user_id, shelf_id, name):
        clash = self.conn.execute(select(wardrobe_shelf.c.id).where(wardrobe_shelf.c.user_id == user_id,
                                                                    wardrobe_shelf.c.name == name,
                                                                    wardrobe_shelf.c.id != shelf_id)).first()
        if clash:
            return False
        self.conn.execute(update(wardrobe_shelf).where(wardrobe_shelf.c.id == shelf_id).values(name=name))
        return True

    def replace_shelf_items(self, shelf_id, item_ids):
        self.conn.execute(delete(wardrobe_shelf_item).where(wardrobe_shelf_item.c.shelf_id == shelf_id))
        if item_ids:
            self.conn.execute(insert(wardrobe_shelf_item), [{"shelf_id": shelf_id, "item_id": i, "position": n}
                                                            for n, i in enumerate(item_ids)])

    def delete_shelf(self, user_id, shelf_id):
        owned = self.conn.execute(select(wardrobe_shelf.c.id).where(wardrobe_shelf.c.id == shelf_id,
                                                                    wardrobe_shelf.c.user_id == user_id)).first()
        if not owned:
            return False
        self.conn.execute(delete(wardrobe_shelf_item).where(wardrobe_shelf_item.c.shelf_id == shelf_id))
        self.conn.execute(delete(wardrobe_shelf).where(wardrobe_shelf.c.id == shelf_id))
        return True

    # ------------------------------------------------------------------ looks
    def looks(self, user_id):
        rows = self.conn.execute(select(look).where(look.c.user_id == user_id, look.c.deleted_at.is_(None))
                                 .order_by(look.c.created_at.desc(), look.c.id)).all()
        return [_look(r) for r in rows]

    def look(self, user_id, look_id, lock=False):
        q = select(look).where(look.c.id == look_id, look.c.user_id == user_id)
        r = self.conn.execute(q.with_for_update() if lock else q).one_or_none()
        return _look(r) if r else None

    def insert_look(self, user_id, look_id, name, now):
        self.conn.execute(insert(look).values(id=look_id, user_id=user_id, name=name, current_revision_no=0,
                                              created_at=now))

    def insert_revision(self, row):
        self.conn.execute(insert(look_revision).values(id=row.id, look_id=row.look_id, revision_no=row.revision_no,
                                                       name=row.name, slots=row.slots, created_at=row.created_at))

    def update_look(self, look_id, *, name, revision_no):
        self.conn.execute(update(look).where(look.c.id == look_id).values(name=name, current_revision_no=revision_no))

    def soft_delete_look(self, look_id, now):
        self.conn.execute(update(look).where(look.c.id == look_id).values(deleted_at=now))

    def revision(self, user_id, revision_id):
        r = self.conn.execute(select(look_revision).select_from(look_revision.join(look, look.c.id == look_revision.c.look_id))
                              .where(look_revision.c.id == revision_id, look.c.user_id == user_id)).one_or_none()
        return _rev(r) if r else None

    def revision_by_no(self, look_id, revision_no):
        r = self.conn.execute(select(look_revision).where(look_revision.c.look_id == look_id,
                                                          look_revision.c.revision_no == revision_no)).one_or_none()
        return _rev(r) if r else None

    def revisions_of(self, look_id):
        rows = self.conn.execute(select(look_revision).where(look_revision.c.look_id == look_id)
                                 .order_by(look_revision.c.revision_no)).all()
        return [_rev(r) for r in rows]

    # ------------------------------------------------------------------ plans
    def plans(self, user_id, start, end):
        rows = self.conn.execute(select(plan_entry).where(plan_entry.c.user_id == user_id,
                                                          plan_entry.c.plan_date.between(start, end))
                                 .order_by(plan_entry.c.plan_date)).all()
        return [PlanRow(r.plan_date, r.look_revision_id, r.occasion, r.note) for r in rows]

    def set_plan(self, user_id, row, now):
        stmt = pg_insert(plan_entry).values(user_id=user_id, plan_date=row.plan_date,
                                            look_revision_id=row.look_revision_id, occasion=row.occasion,
                                            note=row.note, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id", "plan_date"], set_={
            "look_revision_id": row.look_revision_id, "occasion": row.occasion, "note": row.note, "updated_at": now}))

    def clear_plan(self, user_id, plan_date):
        return self.conn.execute(delete(plan_entry).where(plan_entry.c.user_id == user_id,
                                                          plan_entry.c.plan_date == plan_date)).rowcount == 1

    # ------------------------------------------------------------------ wear
    def insert_wear(self, user_id, row):
        self.conn.execute(insert(wear_entry).values(id=row.id, user_id=user_id, worn_on=row.worn_on,
                                                    look_revision_id=row.look_revision_id, created_at=row.created_at))
        self.conn.execute(insert(wear_entry_item), [{"wear_id": row.id, "item_id": i} for i in row.item_ids])

    def wear(self, user_id, start, end):
        rows = self.conn.execute(select(wear_entry).where(wear_entry.c.user_id == user_id,
                                                          wear_entry.c.worn_on.between(start, end))
                                 .order_by(wear_entry.c.worn_on, wear_entry.c.created_at)).all()
        out = []
        for r in rows:
            items = tuple(x.item_id for x in self.conn.execute(select(wear_entry_item.c.item_id)
                                                               .where(wear_entry_item.c.wear_id == r.id)
                                                               .order_by(wear_entry_item.c.item_id)).all())
            out.append(WearRow(r.id, r.worn_on, r.look_revision_id, items, r.created_at))
        return out

    def delete_wear(self, user_id, wear_id):
        owned = self.conn.execute(select(wear_entry.c.id).where(wear_entry.c.id == wear_id,
                                                                wear_entry.c.user_id == user_id)).first()
        if not owned:
            return False
        self.conn.execute(delete(wear_entry_item).where(wear_entry_item.c.wear_id == wear_id))
        self.conn.execute(delete(wear_entry).where(wear_entry.c.id == wear_id))
        return True

    def wear_stats(self, user_id):
        rows = self.conn.execute(select(wear_entry_item.c.item_id, func.count(), func.max(wear_entry.c.worn_on))
                                 .select_from(wear_entry_item.join(wear_entry, wear_entry.c.id == wear_entry_item.c.wear_id))
                                 .where(wear_entry.c.user_id == user_id).group_by(wear_entry_item.c.item_id)).all()
        return {item: (n, last) for item, n, last in rows}

    # ------------------------------------------------------------------ account deletion
    def erase_all(self, user_id):
        wear_ids = select(wear_entry.c.id).where(wear_entry.c.user_id == user_id)
        self.conn.execute(delete(wear_entry_item).where(wear_entry_item.c.wear_id.in_(wear_ids)))
        self.conn.execute(delete(wear_entry).where(wear_entry.c.user_id == user_id))
        self.conn.execute(delete(plan_entry).where(plan_entry.c.user_id == user_id))
        look_ids = select(look.c.id).where(look.c.user_id == user_id)
        self.conn.execute(delete(look_revision).where(look_revision.c.look_id.in_(look_ids)))
        self.conn.execute(delete(look).where(look.c.user_id == user_id))
        shelf_ids = select(wardrobe_shelf.c.id).where(wardrobe_shelf.c.user_id == user_id)
        self.conn.execute(delete(wardrobe_shelf_item).where(wardrobe_shelf_item.c.shelf_id.in_(shelf_ids)))
        self.conn.execute(delete(wardrobe_shelf).where(wardrobe_shelf.c.user_id == user_id))
        self.conn.execute(delete(wardrobe_item_state).where(wardrobe_item_state.c.user_id == user_id))
        self.conn.execute(delete(_D).where(_D.c.user_id == user_id))
