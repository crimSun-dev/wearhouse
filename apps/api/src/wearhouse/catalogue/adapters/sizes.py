"""Size registry, product sizes and usual sizes (add-wearhouse-sizes)."""
from __future__ import annotations

from sqlalchemy import Text, and_, cast, delete, exists, func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ..ports import ProductSize, SizeSystem, SizeValue
from .tables import product, product_size, size_system, size_value, user_size_preference


class SqlSizeRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------ registry
    def systems(self):
        rows = self.conn.execute(select(size_system).order_by(size_system.c.position, size_system.c.code))
        return [SizeSystem(r.code, r.label, r.position, tuple(r.slots or ()), r.active) for r in rows]

    def values(self):
        rows = self.conn.execute(select(size_value).order_by(size_value.c.system_code, size_value.c.rank,
                                                             size_value.c.code))
        return [SizeValue(r.system_code, r.code, r.label, r.rank, r.common, r.active) for r in rows]

    def put_system(self, s, now):
        vals = {"label": s.label, "position": s.position, "slots": list(s.slots), "active": s.active, "updated_at": now}
        self.conn.execute(pg_insert(size_system).values(code=s.code, **vals)
                          .on_conflict_do_update(index_elements=["code"], set_=vals))

    def put_value(self, v, now):
        vals = {"label": v.label, "rank": v.rank, "common": v.common, "active": v.active, "updated_at": now}
        self.conn.execute(pg_insert(size_value).values(system_code=v.system, code=v.code, **vals)
                          .on_conflict_do_update(index_elements=["system_code", "code"], set_=vals))

    # ------------------------------------------------------------------ product sizes
    def product_sizes(self, product_ids):
        if not product_ids:
            return {}
        out: dict = {}
        for i in range(0, len(product_ids), 5000):
            rows = self.conn.execute(
                select(product_size.c.product_id, product_size.c.system_code, product_size.c.size_code,
                       product_size.c.origin)
                .select_from(product_size.join(size_value, and_(size_value.c.system_code == product_size.c.system_code,
                                                                size_value.c.code == product_size.c.size_code)))
                .where(product_size.c.product_id.in_(list(product_ids)[i:i + 5000]))
                .order_by(product_size.c.product_id, size_value.c.rank))
            for r in rows:
                out.setdefault(r.product_id, []).append(ProductSize(r.system_code, r.size_code, r.origin))
        return out

    def set_product_sizes(self, product_id, sizes, now):
        self.conn.execute(delete(product_size).where(product_size.c.product_id == product_id))
        if sizes:
            self.conn.execute(insert(product_size), [{"product_id": product_id, "system_code": s.system,
                                                     "size_code": s.code, "origin": s.origin, "created_at": now}
                                                    for s in sizes])
        self._sync_browse([product_id])

    def _sync_browse(self, product_ids):
        """product.browse_sizes = sorted 'system:code' of its product_size rows (design D7 / migration 0012)."""
        for i in range(0, len(product_ids), 5000):
            chunk = list(product_ids)[i:i + 5000]
            agg = (select(func.coalesce(func.array_agg(product_size.c.system_code + ":" + product_size.c.size_code),
                                        cast(literal("{}"), ARRAY(Text))))
                   .where(product_size.c.product_id == product.c.id).scalar_subquery())
            self.conn.execute(update(product).where(product.c.id.in_(chunk)).values(browse_sizes=agg))

    def unsized_published(self, slots, limit):
        if not slots:
            return []
        has = exists().where(product_size.c.product_id == product.c.id)
        rows = self.conn.execute(select(product.c.id, product.c.browse_slot)
                                 .where(product.c.publication_state == "published", product.c.browse_slot.in_(slots),
                                        ~has)
                                 .order_by(product.c.id).limit(limit))
        return [(r.id, r.browse_slot) for r in rows]

    def add_product_sizes(self, rows, now):
        payload = [{"product_id": pid, "system_code": s.system, "size_code": s.code, "origin": s.origin,
                    "created_at": now} for pid, s in rows]
        for i in range(0, len(payload), 5000):
            self.conn.execute(pg_insert(product_size).values(payload[i:i + 5000]).on_conflict_do_nothing())
        self._sync_browse(list(dict.fromkeys(pid for pid, _ in rows)))

    # ------------------------------------------------------------------ usual sizes
    def preferences(self, user_id):
        rows = self.conn.execute(select(user_size_preference.c.system_code, user_size_preference.c.size_code)
                                 .where(user_size_preference.c.user_id == user_id))
        return {r.system_code: r.size_code for r in rows}

    def set_preference(self, user_id, system, code, now):
        if code is None:
            self.conn.execute(delete(user_size_preference).where(user_size_preference.c.user_id == user_id,
                                                                 user_size_preference.c.system_code == system))
            return
        self.conn.execute(pg_insert(user_size_preference)
                          .values(user_id=user_id, system_code=system, size_code=code, updated_at=now)
                          .on_conflict_do_update(index_elements=["user_id", "system_code"],
                                                 set_={"size_code": code, "updated_at": now}))

    def erase_preferences(self, user_id):
        self.conn.execute(delete(user_size_preference).where(user_size_preference.c.user_id == user_id))
