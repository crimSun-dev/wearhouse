from __future__ import annotations

from sqlalchemy import delete, func, insert, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.sql import column, table

from ..ports import CartLineRow, OfferRow, OfferSizeRow, OrderLineRow, OrderRow, OrderUnitRow
from .tables import (cart_line, sandbox_offer, sandbox_offer_size, sandbox_order, sandbox_order_line, sandbox_order_unit,
                     wishlist_item)

_product = table("product", column("id"))  # existence check only; catalogue owns the table


def _offer(r) -> OfferRow:
    return OfferRow(r.product_id, r.price_idr, r.currency, r.stock, r.updated_at)


def _order(r) -> OrderRow:
    return OrderRow(r.id, r.user_id, r.status, r.currency, r.total_idr, r.payment_ref, r.created_at, r.cancelled_at)


class SqlCommerceRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------ offers
    def get_offer(self, product_id):
        r = self.conn.execute(select(sandbox_offer).where(sandbox_offer.c.product_id == product_id)).one_or_none()
        return _offer(r) if r else None

    def put_offer(self, product_id, price_idr, currency, stock, actor, now):
        stmt = pg_insert(sandbox_offer).values(product_id=product_id, price_idr=price_idr, currency=currency,
                                               stock=stock, updated_by=actor, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["product_id"], set_={
            "price_idr": price_idr, "currency": currency, "stock": stock, "updated_by": actor, "updated_at": now}))

    def delete_offer(self, product_id):
        return self.conn.execute(delete(sandbox_offer).where(sandbox_offer.c.product_id == product_id)).rowcount == 1

    def all_offers(self):
        return [_offer(r) for r in self.conn.execute(select(sandbox_offer).order_by(sandbox_offer.c.updated_at.desc()))]

    def offers_for(self, product_ids):
        if not product_ids:
            return {}
        rows = self.conn.execute(select(sandbox_offer).where(sandbox_offer.c.product_id.in_(list(product_ids)))).all()
        return {r.product_id: _offer(r) for r in rows}

    def lock_offers(self, product_ids):
        if not product_ids:
            return {}
        rows = self.conn.execute(select(sandbox_offer).where(sandbox_offer.c.product_id.in_(list(product_ids)))
                                 .order_by(sandbox_offer.c.product_id).with_for_update()).all()
        return {r.product_id: _offer(r) for r in rows}

    def adjust_stock(self, product_id, delta):
        self.conn.execute(update(sandbox_offer).where(sandbox_offer.c.product_id == product_id)
                          .values(stock=sandbox_offer.c.stock + delta))

    def product_exists(self, product_id):
        return self.conn.execute(select(_product.c.id).where(_product.c.id == product_id)).first() is not None

    # ------------------------------------------------------------------ per-size stock (add-wearhouse-sizes)
    def offer_sizes(self, product_ids, lock=False):
        if not product_ids:
            return {}
        out: dict = {}
        for i in range(0, len(product_ids), 5000):
            q = (select(sandbox_offer_size).where(sandbox_offer_size.c.product_id.in_(list(product_ids)[i:i + 5000]))
                 .order_by(sandbox_offer_size.c.product_id, sandbox_offer_size.c.size_code))
            if lock:
                q = q.with_for_update()
            for r in self.conn.execute(q):
                out.setdefault(r.product_id, {})[r.size_code] = OfferSizeRow(r.product_id, r.size_system, r.size_code,
                                                                             r.stock)
        return out

    def replace_offer_sizes(self, rows_by_product):
        """Replace each product's size rows and keep the offer total equal to their sum (design D4)."""
        pids = list(rows_by_product)
        for i in range(0, len(pids), 5000):
            chunk = pids[i:i + 5000]
            self.conn.execute(delete(sandbox_offer_size).where(sandbox_offer_size.c.product_id.in_(chunk)))
            rows = [{"product_id": r.product_id, "size_system": r.size_system, "size_code": r.size_code,
                     "stock": r.stock} for pid in chunk for r in rows_by_product[pid]]
            for j in range(0, len(rows), 5000):
                self.conn.execute(insert(sandbox_offer_size), rows[j:j + 5000])
            totals = (select(sandbox_offer_size.c.product_id, func.sum(sandbox_offer_size.c.stock).label("total"))
                      .where(sandbox_offer_size.c.product_id.in_(chunk))
                      .group_by(sandbox_offer_size.c.product_id).subquery())
            self.conn.execute(update(sandbox_offer).where(sandbox_offer.c.product_id == totals.c.product_id)
                              .values(stock=totals.c.total))

    def adjust_size_stock(self, product_id, size_code, delta):
        self.conn.execute(update(sandbox_offer_size).where(sandbox_offer_size.c.product_id == product_id,
                                                           sandbox_offer_size.c.size_code == size_code)
                          .values(stock=sandbox_offer_size.c.stock + delta))

    # ------------------------------------------------------------------ wishlist
    def wishlist(self, user_id):
        rows = self.conn.execute(select(wishlist_item.c.product_id, wishlist_item.c.created_at)
                                 .where(wishlist_item.c.user_id == user_id)
                                 .order_by(wishlist_item.c.created_at.desc(), wishlist_item.c.product_id)).all()
        return [(r.product_id, r.created_at) for r in rows]

    def add_wishlist(self, user_id, product_id, now):
        return self.conn.execute(pg_insert(wishlist_item).values(user_id=user_id, product_id=product_id, created_at=now)
                                 .on_conflict_do_nothing().returning(wishlist_item.c.product_id)).first() is not None

    def remove_wishlist(self, user_id, product_id):
        return self.conn.execute(delete(wishlist_item).where(wishlist_item.c.user_id == user_id,
                                                             wishlist_item.c.product_id == product_id)).rowcount == 1

    def wishlist_count(self, user_id):
        return self.conn.execute(select(func.count()).select_from(wishlist_item)
                                 .where(wishlist_item.c.user_id == user_id)).scalar_one()

    # ------------------------------------------------------------------ cart
    def cart(self, user_id, lock=False):
        q = (select(cart_line.c.product_id, cart_line.c.quantity, cart_line.c.size_system, cart_line.c.size_code)
             .where(cart_line.c.user_id == user_id).order_by(cart_line.c.product_id, cart_line.c.size_code))
        if lock:
            q = q.with_for_update()
        return [CartLineRow(r.product_id, r.quantity, r.size_system or None, r.size_code or None)
                for r in self.conn.execute(q).all()]

    def set_cart_line(self, user_id, line, now):
        stmt = pg_insert(cart_line).values(user_id=user_id, product_id=line.product_id, quantity=line.quantity,
                                           size_system=line.size_system or "", size_code=line.size_code or "",
                                           updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id", "product_id", "size_code"],
                                                     set_={"quantity": line.quantity, "updated_at": now}))

    def remove_cart_line(self, user_id, product_id, size_code):
        return self.conn.execute(delete(cart_line).where(cart_line.c.user_id == user_id,
                                                         cart_line.c.product_id == product_id,
                                                         cart_line.c.size_code == (size_code or ""))).rowcount == 1

    def clear_cart(self, user_id):
        self.conn.execute(delete(cart_line).where(cart_line.c.user_id == user_id))

    # ------------------------------------------------------------------ orders
    def insert_order(self, order):
        self.conn.execute(insert(sandbox_order).values(
            id=order.id, user_id=order.user_id, status=order.status, currency=order.currency,
            total_idr=order.total_idr, payment_ref=order.payment_ref, created_at=order.created_at))

    def insert_order_line(self, order_id, line):
        self.conn.execute(insert(sandbox_order_line).values(
            order_id=order_id, line_no=line.line_no, product_id=line.product_id, revision_id=line.revision_id,
            product_name=line.product_name, unit_price_idr=line.unit_price_idr, quantity=line.quantity,
            size_system=line.size_system, size_code=line.size_code, size_label=line.size_label))

    def insert_order_unit(self, order_id, unit):
        self.conn.execute(insert(sandbox_order_unit).values(order_id=order_id, unit_id=unit.unit_id,
                                                            line_no=unit.line_no, delivery_id=unit.delivery_id))

    def orders(self, user_id, after, limit):
        q = select(sandbox_order).where(sandbox_order.c.user_id == user_id)
        if after is not None:
            q = q.where(tuple_(sandbox_order.c.created_at, sandbox_order.c.id) < tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(sandbox_order.c.created_at.desc(), sandbox_order.c.id.desc())
                                 .limit(limit)).all()
        return [_order(r) for r in rows]

    def order(self, user_id, order_id, lock=False):
        q = select(sandbox_order).where(sandbox_order.c.id == order_id, sandbox_order.c.user_id == user_id)
        if lock:
            q = q.with_for_update()
        r = self.conn.execute(q).one_or_none()
        return _order(r) if r else None

    def order_lines(self, order_id):
        rows = self.conn.execute(select(sandbox_order_line).where(sandbox_order_line.c.order_id == order_id)
                                 .order_by(sandbox_order_line.c.line_no)).all()
        return [OrderLineRow(r.line_no, r.product_id, r.revision_id, r.product_name, r.unit_price_idr, r.quantity,
                             r.size_system, r.size_code, r.size_label) for r in rows]

    def order_units(self, order_id):
        rows = self.conn.execute(select(sandbox_order_unit).where(sandbox_order_unit.c.order_id == order_id)
                                 .order_by(sandbox_order_unit.c.line_no, sandbox_order_unit.c.unit_id)).all()
        return [OrderUnitRow(r.unit_id, r.line_no, r.delivery_id) for r in rows]

    def set_unit_delivery(self, unit_id, delivery_id):
        self.conn.execute(update(sandbox_order_unit).where(sandbox_order_unit.c.unit_id == unit_id)
                          .values(delivery_id=delivery_id))

    def mark_cancelled(self, order_id, now):
        self.conn.execute(update(sandbox_order).where(sandbox_order.c.id == order_id)
                          .values(status="cancelled", cancelled_at=now))

    def erase_lists(self, user_id):
        self.conn.execute(delete(wishlist_item).where(wishlist_item.c.user_id == user_id))
        self.conn.execute(delete(cart_line).where(cart_line.c.user_id == user_id))

    # ------------------------------------------------------------------ staff
    def all_orders(self, status, after, limit):
        q = select(sandbox_order)
        if status:
            q = q.where(sandbox_order.c.status == status)
        if after is not None:
            q = q.where(tuple_(sandbox_order.c.created_at, sandbox_order.c.id) < tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(sandbox_order.c.created_at.desc(), sandbox_order.c.id.desc()).limit(limit))
        return [_order(r) for r in rows]

    def bulk_put_offers(self, product_ids, price_idr, stock, actor, now, overwrite):
        written = []
        for i in range(0, len(product_ids), 5000):
            chunk = product_ids[i:i + 5000]
            stmt = pg_insert(sandbox_offer).values([{"product_id": pid, "price_idr": price_idr, "currency": "IDR",
                                                     "stock": stock, "updated_by": actor, "updated_at": now}
                                                    for pid in chunk])
            stmt = (stmt.on_conflict_do_update(index_elements=["product_id"], set_={
                "price_idr": price_idr, "stock": stock, "updated_by": actor, "updated_at": now}) if overwrite
                else stmt.on_conflict_do_nothing())
            written += list(self.conn.execute(stmt.returning(sandbox_offer.c.product_id)).scalars())
        return written

    def popular_products(self, since, limit):
        qty = func.sum(sandbox_order_line.c.quantity).label("qty")
        rows = self.conn.execute(select(sandbox_order_line.c.product_id, qty)
                                 .select_from(sandbox_order_line.join(sandbox_order,
                                                                      sandbox_order.c.id == sandbox_order_line.c.order_id))
                                 .where(sandbox_order.c.created_at >= since, sandbox_order.c.status == "fulfilled")
                                 .group_by(sandbox_order_line.c.product_id)
                                 .order_by(qty.desc(), sandbox_order_line.c.product_id).limit(limit))
        return [r.product_id for r in rows]
