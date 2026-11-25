"""Sandbox commerce: staff offers, wishlist, cart, idempotent checkout, buyer-scoped receipts, key renewal and
cancellation. Purchases go through the real ownership machinery (buyer-bound credentials, encrypted delivery);
no money is ever charged and every price is labelled sandbox."""
from __future__ import annotations

import uuid
from typing import Callable

from ..catalogue.application import SizeIndex
from ..catalogue.ports import RevisionSummary
from ..identity.domain import Capability, Principal, require
from ..ownership.application import UnitFulfilment
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.errors import FieldError, conflict, not_found, validation_failed
from ..platform.idempotency import IdempotentExecutor, Outcome
from ..platform.ids import new_id
from ..platform.pagination import Position, check_limit, decode, encode
from .domain import (CURRENCY, MAX_CART_LINES, MAX_STOCK, MAX_WISHLIST, ORDER_CANCELLED, ORDER_FULFILLED,
                     SANDBOX_PAYMENT_REF, check_quantity, not_available, not_for_sale, offer_errors, one_size_only,
                     out_of_stock, price_changed, size_not_offered, size_required)
from .ports import CartLineRow, CommerceUoW, OfferRow, OfferSizeRow, OrderLineRow, OrderRow, OrderUnitRow

ROUTE_CHECKOUT = "POST /api/v2/me/checkout"
ROUTE_RENEW = "POST /api/v2/me/orders/{id}/units/{unit_id}/renew-key"
ORDERS_SCOPE = "me.orders"


def _iso(dt):
    return dt.isoformat() if dt else None


def _offer_view(o: OfferRow) -> dict:
    return {"price_idr": o.price_idr, "currency": o.currency, "in_stock": o.stock > 0, "sandbox": True}


def size_stock_rows(product_id, sizes, stock: int, size_stock: dict | None) -> list[OfferSizeRow]:
    """Per-size stock for a sized product (design D4): `size_stock[code]` when given, else `stock` for every size."""
    errors = []
    known = {x.code for x in sizes}
    for code, n in (size_stock or {}).items():
        if code not in known:
            errors.append(FieldError(f"body.size_stock.{code}", "unknown_size", f"The product has no size {code}."))
        elif not 0 <= n <= MAX_STOCK:
            errors.append(FieldError(f"body.size_stock.{code}", "out_of_range", f"Stock must be 0-{MAX_STOCK:,}."))
    rows = [OfferSizeRow(product_id, x.system, x.code, (size_stock or {}).get(x.code, stock)) for x in sizes]
    if not errors and sum(r.stock for r in rows) > MAX_STOCK:
        errors.append(FieldError("body.stock", "out_of_range", f"Total stock must be at most {MAX_STOCK:,}."))
    if errors:
        raise validation_failed(errors)
    return rows


class CommerceService:
    def __init__(self, uow_factory: Callable[[], CommerceUoW], ring: KeyRing, fulfilment: UnitFulfilment, *,
                 clock: Clock = utcnow, lease_s: float = 15.0):
        self.uow_factory = uow_factory
        self.ring = ring
        self.fulfilment = fulfilment
        self.clock = clock
        self.executor = IdempotentExecutor(uow_factory, ring, clock, lease_s=lease_s)

    # ================================================================ offers
    def put_offer(self, principal: Principal, product_id: uuid.UUID, *, price_idr: int, stock: int,
                  currency: str = CURRENCY, size_stock: dict[str, int] | None = None) -> dict:
        """For a sized product `stock` is per size unless `size_stock` names a size (add-wearhouse-sizes D4)."""
        require(principal, Capability.MANAGE_OFFERS)
        errors = offer_errors(price_idr, stock, currency)
        if errors:
            raise validation_failed(errors)
        with self.uow_factory() as uow:
            if not uow.commerce.product_exists(product_id):
                raise not_found("Product not found.")
            sizes = uow.sizes.product_sizes([product_id]).get(product_id, [])
            if size_stock and not sizes:
                raise one_size_only()
            rows = size_stock_rows(product_id, sizes, stock, size_stock) if sizes else []
            before = uow.commerce.get_offer(product_id)
            uow.commerce.put_offer(product_id, price_idr, currency, stock, principal.user_id, self.clock())
            if sizes:
                uow.commerce.replace_offer_sizes({product_id: rows})
            uow.audit.record(actor_id=principal.user_id, action="commerce.offer_saved", target_type="product",
                             target_id=str(product_id),
                             details={"price_idr": price_idr, "stock": sum(r.stock for r in rows) if sizes else stock,
                                      "size_stock": {r.size_code: r.stock for r in rows} or None,
                                      "previous_price_idr": before.price_idr if before else None,
                                      "previous_stock": before.stock if before else None})
            uow.commit()
            return self._staff_offer(uow, uow.commerce.get_offer(product_id))

    def delete_offer(self, principal: Principal, product_id: uuid.UUID) -> None:
        require(principal, Capability.MANAGE_OFFERS)
        with self.uow_factory() as uow:
            if not uow.commerce.delete_offer(product_id):
                raise not_found("Offer not found.")
            uow.audit.record(actor_id=principal.user_id, action="commerce.offer_withdrawn", target_type="product",
                             target_id=str(product_id), details={})
            uow.commit()

    def staff_offers(self, principal: Principal) -> list[dict]:
        require(principal, Capability.MANAGE_OFFERS)
        with self.uow_factory() as uow:
            return [self._staff_offer(uow, o) for o in uow.commerce.all_offers()]

    def _staff_offer(self, uow: CommerceUoW, o: OfferRow) -> dict:
        rev = uow.revisions.current_for_product(o.product_id)
        on_sale = bool(uow.revisions.on_sale([o.product_id]))
        return {"product_id": str(o.product_id), "name": rev.product_name if rev else None,
                "price_idr": o.price_idr, "currency": o.currency, "stock": o.stock, "on_sale": on_sale,
                "sandbox": True, "updated_at": _iso(o.updated_at), "sizes": self._sizes_view(uow, o.product_id,
                                                                                            staff=True)}

    @staticmethod
    def _sizes_view(uow: CommerceUoW, product_id: uuid.UUID, *, staff: bool) -> list[dict]:
        """The product's catalogue sizes in rank order with this offer's stock (a missing size row = none)."""
        sizes = uow.sizes.product_sizes([product_id]).get(product_id, [])
        if not sizes:
            return []
        index = SizeIndex.load(uow.sizes)
        stock = uow.commerce.offer_sizes([product_id]).get(product_id, {})
        out = []
        for x in sizes:
            n = stock[x.code].stock if x.code in stock else 0
            out.append({**index.out(x.system, x.code), "in_stock": n > 0, **({"stock": n} if staff else {})})
        return out

    def public_offer(self, product_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            offer = uow.commerce.get_offer(product_id)
            if offer is None or not uow.revisions.on_sale([product_id]):
                raise not_found("This product is not on sale.")
            sizes = self._sizes_view(uow, product_id, staff=False)
        view = _offer_view(offer)
        if sizes:
            view["in_stock"] = any(x["in_stock"] for x in sizes)
        return {"product_id": str(product_id), **view, "sizes": sizes}

    # ================================================================ wishlist
    def wishlist(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            rows = uow.commerce.wishlist(principal.user_id)
            pids = [p for p, _ in rows]
            sale = uow.revisions.on_sale(pids)
            offers = uow.commerce.offers_for(pids)
            items = []
            for pid, added in rows:
                rev = sale.get(pid) or uow.revisions.current_for_product(pid)
                o = offers.get(pid)
                items.append({"product_id": str(pid), "name": rev.product_name if rev else None,
                              "available": pid in sale, "offer": _offer_view(o) if o and pid in sale else None,
                              "added_at": _iso(added)})
        return {"items": items, "limit": MAX_WISHLIST}

    def add_wishlist(self, principal: Principal, product_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            if not uow.revisions.on_sale([product_id]):
                raise not_found("Product not found.")
            existing = {p for p, _ in uow.commerce.wishlist(principal.user_id)}
            if product_id not in existing:
                if len(existing) >= MAX_WISHLIST:
                    raise conflict("WISHLIST_FULL", f"A wishlist holds at most {MAX_WISHLIST} products.")
                uow.commerce.add_wishlist(principal.user_id, product_id, self.clock())
            uow.commit()
        return self.wishlist(principal)

    def remove_wishlist(self, principal: Principal, product_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            uow.commerce.remove_wishlist(principal.user_id, product_id)
            uow.commit()

    # ================================================================ cart
    def cart(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            return self._cart_view(uow, principal.user_id)

    def _cart_view(self, uow: CommerceUoW, user_id: uuid.UUID) -> dict:
        lines = uow.commerce.cart(user_id)
        pids = list(dict.fromkeys(x.product_id for x in lines))
        sale = uow.revisions.on_sale(pids)
        offers = uow.commerce.offers_for(pids)
        size_stock = uow.commerce.offer_sizes(pids)
        index = SizeIndex.load(uow.sizes)
        out, total, ready = [], 0, bool(lines)
        for x in lines:
            pid, qty = x.product_id, x.quantity
            rev = sale.get(pid) or uow.revisions.current_for_product(pid)
            o = offers.get(pid)
            price = o.price_idr if o and pid in sale else None
            if x.size_code:
                row = size_stock.get(pid, {}).get(x.size_code)
                available = price is not None and row is not None and row.stock >= qty
            else:
                available = price is not None and o.stock >= qty
            ready = ready and available
            line_total = price * qty if price is not None else None
            total += line_total or 0
            out.append({"product_id": str(pid), "name": rev.product_name if rev else None, "quantity": qty,
                        "size": index.out(x.size_system, x.size_code),
                        "unit_price_idr": price, "line_total_idr": line_total, "available": available})
        return {"lines": out, "total_idr": total, "currency": CURRENCY, "sandbox": True, "checkout_ready": ready,
                "limit": MAX_CART_LINES}

    def set_cart_line(self, principal: Principal, product_id: uuid.UUID, quantity: int,
                      size: str | None = None) -> dict:
        """A sized product needs one of its sizes; a one-size product takes none. Each size is its own line."""
        check_quantity(quantity)
        with self.uow_factory() as uow:
            if not uow.revisions.on_sale([product_id]):
                raise not_found("Product not found.")
            if uow.commerce.get_offer(product_id) is None:
                raise not_for_sale()
            sizes = {x.code: x for x in uow.sizes.product_sizes([product_id]).get(product_id, [])}
            if sizes and size is None:
                raise size_required()
            if not sizes and size is not None:
                raise one_size_only()
            if size is not None and size not in sizes:
                raise size_not_offered(size)
            current = {(x.product_id, x.size_code) for x in uow.commerce.cart(principal.user_id, lock=True)}
            if (product_id, size) not in current and len(current) >= MAX_CART_LINES:
                raise conflict("CART_FULL", f"A cart holds at most {MAX_CART_LINES} lines.")
            line = CartLineRow(product_id, quantity, sizes[size].system if size else None, size)
            uow.commerce.set_cart_line(principal.user_id, line, self.clock())
            uow.commit()
            return self._cart_view(uow, principal.user_id)

    def remove_cart_line(self, principal: Principal, product_id: uuid.UUID, size: str | None = None) -> dict:
        with self.uow_factory() as uow:
            uow.commerce.remove_cart_line(principal.user_id, product_id, size)
            uow.commit()
            return self._cart_view(uow, principal.user_id)

    # ================================================================ checkout
    def checkout(self, principal: Principal, *, expected_total_idr: int, idem_key: str) -> Outcome:
        user = principal.user_id

        def execute(uow: CommerceUoW, rec):
            lines = uow.commerce.cart(user, lock=True)
            if not lines:
                raise conflict("CART_EMPTY", "The cart is empty.")
            pids = list(dict.fromkeys(x.product_id for x in lines))
            offers = uow.commerce.lock_offers(pids)  # ordered row locks: last-item races serialise here
            size_stock = uow.commerce.offer_sizes(pids, lock=True)  # then size rows, same order (design D4)
            sale = uow.revisions.on_sale(pids)
            index = SizeIndex.load(uow.sizes)
            catalogue_sizes = {pid: {x.code for x in v} for pid, v in uow.sizes.product_sizes(pids).items()}
            name = lambda pid: sale[pid].product_name if pid in sale else str(pid)  # noqa: E731
            gone = [name(p) for p in pids if p not in sale]
            gone += [f"{name(x.product_id)} ({x.size_code})" for x in lines
                     if x.size_code and x.size_code not in catalogue_sizes.get(x.product_id, set())]
            if gone:
                raise not_available(gone)
            if any(p not in offers for p in pids):
                raise not_for_sale()
            need: dict = {}
            for x in lines:
                need[x.product_id] = need.get(x.product_id, 0) + x.quantity
            short = [name(p) for p, q in need.items() if offers[p].stock < q]
            for x in lines:
                row = size_stock.get(x.product_id, {}).get(x.size_code) if x.size_code else None
                if x.size_code and (row is None or row.stock < x.quantity):
                    label = index.out(x.size_system, x.size_code)["label"]
                    short.append(f"{name(x.product_id)} (size {label})")
            if short:
                raise out_of_stock(list(dict.fromkeys(short)))
            total = sum(offers[x.product_id].price_idr * x.quantity for x in lines)
            if total != expected_total_idr:
                raise price_changed()
            now = self.clock()
            order_id = new_id()
            uow.commerce.insert_order(OrderRow(order_id, user, ORDER_FULFILLED, CURRENCY, total, SANDBOX_PAYMENT_REF,
                                               now, None))
            units = 0
            for line_no, x in enumerate(lines, start=1):
                pid, qty = x.product_id, x.quantity
                rev: RevisionSummary = sale[pid]
                size = index.out(x.size_system, x.size_code)
                uow.commerce.adjust_stock(pid, -qty)
                if x.size_code:
                    uow.commerce.adjust_size_stock(pid, x.size_code, -qty)
                uow.commerce.insert_order_line(order_id, OrderLineRow(
                    line_no, pid, rev.revision_id, rev.product_name, offers[pid].price_idr, qty,
                    x.size_system, x.size_code, size["label"] if size else None))
                for _ in range(qty):
                    u = self.fulfilment.fulfil(uow, product_id=pid, revision_id=rev.revision_id, buyer_id=user,
                                               reference={"order_id": str(order_id), "line_no": line_no},
                                               size=size)
                    uow.commerce.insert_order_unit(order_id, OrderUnitRow(u["unit_id"], line_no, u["delivery_id"]))
                    units += 1
            uow.commerce.clear_cart(user)
            uow.audit.record(actor_id=user, action="commerce.order_placed", target_type="sandbox_order",
                             target_id=str(order_id), details={"total_idr": total, "lines": len(lines),
                                                               "units": units, "sandbox": True})
            uow.outbox.emit(event_type="commerce.order_placed", aggregate_type="sandbox_order", aggregate_id=order_id,
                            payload={"total_idr": total, "units": units})
            return 201, {"order_id": str(order_id)}

        out = self.executor.run(actor_id=user, route=ROUTE_CHECKOUT, key=idem_key,
                                body={"expected_total_idr": expected_total_idr}, execute=execute)
        if out.status >= 400:
            return out
        return Outcome(out.status, self.receipt(principal, uuid.UUID(out.body["order_id"])), out.replayed)

    # ================================================================ orders
    def orders(self, principal: Principal, *, limit: int | None, cursor: str | None) -> dict:
        limit = check_limit(limit)
        after = decode(self.ring, cursor, principal=principal.user_id, scope=ORDERS_SCOPE, filter_key="") \
            if cursor else None
        with self.uow_factory() as uow:
            rows = uow.commerce.orders(principal.user_id, after, limit + 1)
            more, rows = len(rows) > limit, rows[:limit]
            items = []
            for o in rows:
                lines = uow.commerce.order_lines(o.id)
                items.append({"id": str(o.id), "status": o.status, "total_idr": o.total_idr, "currency": o.currency,
                              "sandbox": True, "created_at": _iso(o.created_at),
                              "item_count": sum(x.quantity for x in lines),
                              "names": [x.product_name for x in lines]})
        nxt = encode(self.ring, principal=principal.user_id, scope=ORDERS_SCOPE, filter_key="",
                     pos=Position(rows[-1].created_at, rows[-1].id)) if more else None
        return {"items": items, "next_cursor": nxt}

    def receipt(self, principal: Principal, order_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            o = uow.commerce.order(principal.user_id, order_id)
            if o is None:
                raise not_found("Order not found.")
            return self._receipt(uow, o)

    def _receipt(self, uow: CommerceUoW, o: OrderRow) -> dict:
        lines = uow.commerce.order_lines(o.id)
        units = uow.commerce.order_units(o.id)
        states = self.fulfilment.unit_states(uow, [u.unit_id for u in units])
        serials = {u.id: u.public_serial for u in uow.ownership.units([u.unit_id for u in units])}
        by_line: dict[int, list] = {}
        for u in units:
            state = states.get(u.unit_id, "unknown")
            if state == "claimed" and o.status == ORDER_CANCELLED:
                state, delivery = "revoked", {"status": "unavailable", "reason": "revoked_sandbox"}
            elif state == "claimed":
                delivery = {"status": "claimed"}
            elif state == "retired":
                delivery = {"status": "unavailable", "reason": "cancelled"}
            else:
                delivery = self.fulfilment.delivery_state(uow, delivery_id=u.delivery_id, buyer_id=o.user_id)
            by_line.setdefault(u.line_no, []).append({"unit_id": str(u.unit_id), "public_serial": serials.get(u.unit_id),
                                                      "state": state, "delivery": delivery})
        return {"id": str(o.id), "status": o.status, "currency": o.currency, "total_idr": o.total_idr, "sandbox": True,
                "payment_ref": o.payment_ref, "created_at": _iso(o.created_at), "cancelled_at": _iso(o.cancelled_at),
                "cancellable": o.status == ORDER_FULFILLED,  # claimed items are revoked (sandbox only)
                "lines": [{"line_no": x.line_no, "product_id": str(x.product_id), "product_name": x.product_name,
                           "size": _line_size(x), "unit_price_idr": x.unit_price_idr, "quantity": x.quantity,
                           "line_total_idr": x.unit_price_idr * x.quantity, "units": by_line.get(x.line_no, [])}
                          for x in lines]}

    def _order_unit(self, uow: CommerceUoW, user: uuid.UUID, order_id: uuid.UUID, unit_id: uuid.UUID,
                    lock: bool = False) -> tuple[OrderRow, OrderUnitRow]:
        o = uow.commerce.order(user, order_id, lock=lock)
        unit = next((u for u in uow.commerce.order_units(order_id) if u.unit_id == unit_id), None) if o else None
        if o is None or unit is None:
            raise not_found("Order not found.")
        return o, unit

    def reveal_key(self, principal: Principal, order_id: uuid.UUID, unit_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            o, unit = self._order_unit(uow, principal.user_id, order_id, unit_id)
            state = self.fulfilment.unit_states(uow, [unit_id]).get(unit_id)
            if state == "claimed":
                out = {"status": "claimed"}
            elif state == "retired":
                out = {"status": "unavailable", "reason": "cancelled"}
            else:
                out = self.fulfilment.open_delivery(uow, delivery_id=unit.delivery_id, buyer_id=principal.user_id)
            uow.commit()
        return {"unit_id": str(unit_id), **out}

    def renew_key(self, principal: Principal, order_id: uuid.UUID, unit_id: uuid.UUID, *, idem_key: str) -> Outcome:
        user = principal.user_id

        def execute(uow: CommerceUoW, rec):
            o, _ = self._order_unit(uow, user, order_id, unit_id, lock=True)
            if o.status != ORDER_FULFILLED:
                raise conflict("ORDER_CANCELLED", "This order was cancelled.")
            delivery_id = self.fulfilment.renew_key(uow, unit_id=unit_id, buyer_id=user)
            uow.commerce.set_unit_delivery(unit_id, delivery_id)
            uow.audit.record(actor_id=user, action="commerce.key_renewed", target_type="garment_unit",
                             target_id=str(unit_id), details={"order_id": str(order_id)})
            return 201, {"unit_id": str(unit_id), "status": "renewed"}

        route = ROUTE_RENEW.replace("{id}", str(order_id)).replace("{unit_id}", str(unit_id))
        return self.executor.run(actor_id=user, route=route, key=idem_key, body={"unit_id": str(unit_id)},
                                 execute=execute)

    def cancel(self, principal: Principal, order_id: uuid.UUID) -> dict:
        user = principal.user_id
        with self.uow_factory() as uow:
            o = uow.commerce.order(user, order_id, lock=True)  # serialises concurrent cancels
            if o is None:
                raise not_found("Order not found.")
            if o.status == ORDER_FULFILLED:
                units = uow.commerce.order_units(order_id)
                outcome = self.fulfilment.cancel_units(uow, unit_ids=[u.unit_id for u in units], actor_id=user,
                                                       reason="order_cancelled")
                lines = uow.commerce.order_lines(order_id)
                offers = uow.commerce.lock_offers([x.product_id for x in lines])
                size_stock = uow.commerce.offer_sizes(list(offers), lock=True)
                for x in lines:
                    if x.product_id in offers:
                        uow.commerce.adjust_stock(x.product_id, x.quantity)
                        if x.size_code and x.size_code in size_stock.get(x.product_id, {}):
                            uow.commerce.adjust_size_stock(x.product_id, x.size_code, x.quantity)
                now = self.clock()
                uow.commerce.mark_cancelled(order_id, now)
                uow.audit.record(actor_id=user, action="commerce.order_cancelled", target_type="sandbox_order",
                                 target_id=str(order_id), details={"units": len(units), "restocked": len(offers),
                                                                   **outcome})
                uow.outbox.emit(event_type="commerce.order_cancelled", aggregate_type="sandbox_order",
                                aggregate_id=order_id, payload={})
                o = uow.commerce.order(user, order_id)
            uow.commit()
            return self._receipt(uow, o)

    # ================================================================ accounts integration
    def export_data(self, uow: CommerceUoW, user_id: uuid.UUID) -> dict:
        """Account export section: lists and orders, never keys."""
        wish = [{"product_id": str(p), "added_at": _iso(a)} for p, a in uow.commerce.wishlist(user_id)]
        cart = [{"product_id": str(x.product_id), "quantity": x.quantity, "size_system": x.size_system,
                 "size_code": x.size_code} for x in uow.commerce.cart(user_id)]
        orders, after = [], None
        while True:
            page = uow.commerce.orders(user_id, after, 100)
            for o in page:
                orders.append({"id": str(o.id), "status": o.status, "total_idr": o.total_idr, "currency": o.currency,
                               "sandbox": True, "created_at": _iso(o.created_at), "cancelled_at": _iso(o.cancelled_at),
                               "lines": [{"product_id": str(x.product_id), "product_name": x.product_name,
                                          "size": _line_size(x), "unit_price_idr": x.unit_price_idr,
                                          "quantity": x.quantity} for x in uow.commerce.order_lines(o.id)]})
            if len(page) < 100:
                break
            after = Position(page[-1].created_at, page[-1].id)
        return {"wishlist": wish, "cart": cart, "orders": orders}


def _line_size(x: OrderLineRow) -> dict | None:
    return {"system": x.size_system, "code": x.size_code, "label": x.size_label} if x.size_code else None


# ================================================================ staff (add-wearhouse-object-management)
MAX_BULK_RULES = 50
STAFF_ORDERS_SCOPE = "admin.orders"


class CommerceStaffService:
    def __init__(self, uow_factory: Callable[[], CommerceUoW], ring: KeyRing, *, clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.ring = ring
        self.clock = clock

    def orders(self, principal: Principal, *, status: str | None, limit: int | None, cursor: str | None) -> dict:
        """Every sandbox order (commerce:orders). Never keys: only lines, totals, status and the buyer handle."""
        require(principal, Capability.VIEW_ORDERS)
        if status not in (None, ORDER_FULFILLED, ORDER_CANCELLED):
            raise validation_failed([FieldError("query.status", "invalid", "status must be fulfilled or cancelled.")])
        n = check_limit(limit)
        fkey = status or ""
        after = decode(self.ring, cursor, principal=principal.user_id, scope=STAFF_ORDERS_SCOPE, filter_key=fkey) \
            if cursor else None
        with self.uow_factory() as uow:
            rows = uow.commerce.all_orders(status, after, n + 1)
            more, rows = len(rows) > n, rows[:n]
            items = []
            for o in rows:
                lines = uow.commerce.order_lines(o.id)
                buyer = uow.accounts.get_profile(o.user_id)
                items.append({"id": str(o.id), "status": o.status, "total_idr": o.total_idr, "currency": o.currency,
                              "sandbox": True, "created_at": _iso(o.created_at), "cancelled_at": _iso(o.cancelled_at),
                              "buyer_handle": buyer.handle if buyer else None,
                              "item_count": sum(x.quantity for x in lines),
                              "lines": [{"product_id": str(x.product_id), "product_name": x.product_name,
                                         "size": _line_size(x), "unit_price_idr": x.unit_price_idr,
                                         "quantity": x.quantity} for x in lines]})
        nxt = encode(self.ring, principal=principal.user_id, scope=STAFF_ORDERS_SCOPE, filter_key=fkey,
                     pos=Position(rows[-1].created_at, rows[-1].id)) if more else None
        return {"items": items, "next_cursor": nxt}

    def bulk_offers(self, principal: Principal, *, rules: list[dict], overwrite: bool) -> dict:
        """Category/slot rules -> sandbox offers for every matching PUBLISHED product. Mock values, labelled sandbox."""
        require(principal, Capability.MANAGE_OFFERS)
        if not 1 <= len(rules) <= MAX_BULK_RULES:
            raise validation_failed([FieldError("body.rules", "out_of_range", f"Send 1-{MAX_BULK_RULES} rules.")])
        errors = []
        for i, r in enumerate(rules):
            if not (r.get("category") or r.get("slot")):
                errors.append(FieldError(f"body.rules.{i}", "no_match", "A rule needs a category and/or a slot."))
            errors += [FieldError(f"body.rules.{i}.{e.field.split('.')[-1]}", e.code, e.message)
                       for e in offer_errors(r["price_idr"], r["stock"], CURRENCY)]
        if errors:
            raise validation_failed(errors)
        results = []
        with self.uow_factory() as uow:
            now = self.clock()
            for r in rules:
                ids = uow.revisions.published_ids(r.get("category"), r.get("slot"))
                written = uow.commerce.bulk_put_offers(ids, r["price_idr"], r["stock"], principal.user_id, now,
                                                       overwrite)
                sizes = uow.sizes.product_sizes(written)  # sized products: `stock` per size (design D4)
                uow.commerce.replace_offer_sizes({pid: [OfferSizeRow(pid, x.system, x.code, r["stock"]) for x in v]
                                                  for pid, v in sizes.items()})
                results.append({"category": r.get("category"), "slot": r.get("slot"), "matched": len(ids),
                                "written": len(written), "sized": len(sizes)})
            uow.audit.record(actor_id=principal.user_id, action="commerce.offers_bulk_saved", target_type="sandbox_offer",
                             target_id="*", details={"overwrite": overwrite, "rules": results, "sandbox": True})
            uow.commit()
        return {"overwrite": overwrite, "sandbox": True, "results": results}
