from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..accounts.ports import AccountsRepository
from ..catalogue.ports import RevisionReader, SizeRepository
from ..ownership.ports import OwnershipRepository
from ..platform.pagination import Position
from ..platform.ports import UnitOfWork


@dataclass(frozen=True)
class OfferRow:
    product_id: uuid.UUID
    price_idr: int
    currency: str
    stock: int
    updated_at: datetime


@dataclass(frozen=True)
class OrderRow:
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    currency: str
    total_idr: int
    payment_ref: str
    created_at: datetime
    cancelled_at: datetime | None


@dataclass(frozen=True)
class OrderLineRow:
    line_no: int
    product_id: uuid.UUID
    revision_id: uuid.UUID
    product_name: str
    unit_price_idr: int
    quantity: int
    size_system: str | None = None
    size_code: str | None = None
    size_label: str | None = None


@dataclass(frozen=True)
class CartLineRow:
    product_id: uuid.UUID
    quantity: int
    size_system: str | None = None  # None = one size
    size_code: str | None = None


@dataclass(frozen=True)
class OfferSizeRow:
    product_id: uuid.UUID
    size_system: str
    size_code: str
    stock: int


@dataclass(frozen=True)
class OrderUnitRow:
    unit_id: uuid.UUID
    line_no: int
    delivery_id: uuid.UUID | None


class CommerceRepository(Protocol):
    def get_offer(self, product_id: uuid.UUID) -> OfferRow | None: ...
    def put_offer(self, product_id: uuid.UUID, price_idr: int, currency: str, stock: int, actor: uuid.UUID,
                  now: datetime) -> None: ...
    def delete_offer(self, product_id: uuid.UUID) -> bool: ...
    def all_offers(self) -> list[OfferRow]: ...
    def offers_for(self, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, OfferRow]: ...
    def lock_offers(self, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, OfferRow]: ...
    def adjust_stock(self, product_id: uuid.UUID, delta: int) -> None: ...
    def product_exists(self, product_id: uuid.UUID) -> bool: ...
    # per-size stock (add-wearhouse-sizes)
    def offer_sizes(self, product_ids: list[uuid.UUID], lock: bool = False) -> dict[uuid.UUID, dict[str, OfferSizeRow]]: ...
    def replace_offer_sizes(self, rows_by_product: dict[uuid.UUID, list[OfferSizeRow]]) -> None: ...
    def adjust_size_stock(self, product_id: uuid.UUID, size_code: str, delta: int) -> None: ...

    def wishlist(self, user_id: uuid.UUID) -> list[tuple[uuid.UUID, datetime]]: ...
    def add_wishlist(self, user_id: uuid.UUID, product_id: uuid.UUID, now: datetime) -> bool: ...
    def remove_wishlist(self, user_id: uuid.UUID, product_id: uuid.UUID) -> bool: ...
    def wishlist_count(self, user_id: uuid.UUID) -> int: ...

    def cart(self, user_id: uuid.UUID, lock: bool = False) -> list[CartLineRow]: ...
    def set_cart_line(self, user_id: uuid.UUID, line: CartLineRow, now: datetime) -> None: ...
    def remove_cart_line(self, user_id: uuid.UUID, product_id: uuid.UUID, size_code: str | None) -> bool: ...
    def clear_cart(self, user_id: uuid.UUID) -> None: ...

    def insert_order(self, order: OrderRow) -> None: ...
    def insert_order_line(self, order_id: uuid.UUID, line: OrderLineRow) -> None: ...
    def insert_order_unit(self, order_id: uuid.UUID, unit: OrderUnitRow) -> None: ...
    def orders(self, user_id: uuid.UUID, after: Position | None, limit: int) -> list[OrderRow]: ...
    def order(self, user_id: uuid.UUID, order_id: uuid.UUID, lock: bool = False) -> OrderRow | None: ...
    def order_lines(self, order_id: uuid.UUID) -> list[OrderLineRow]: ...
    def order_units(self, order_id: uuid.UUID) -> list[OrderUnitRow]: ...
    def set_unit_delivery(self, unit_id: uuid.UUID, delivery_id: uuid.UUID) -> None: ...
    def mark_cancelled(self, order_id: uuid.UUID, now: datetime) -> None: ...

    def erase_lists(self, user_id: uuid.UUID) -> None: ...

    def popular_products(self, since: datetime, limit: int) -> list[uuid.UUID]: ...
    # staff (add-wearhouse-object-management)
    def all_orders(self, status: str | None, after: Position | None, limit: int) -> list[OrderRow]: ...
    def bulk_put_offers(self, product_ids: list[uuid.UUID], price_idr: int, stock: int, actor: uuid.UUID,
                        now: datetime, overwrite: bool) -> list[uuid.UUID]: ...


class CommerceUoW(UnitOfWork, Protocol):
    commerce: CommerceRepository
    accounts: AccountsRepository  # buyer handles in the staff order view
    revisions: RevisionReader
    ownership: OwnershipRepository
    sizes: SizeRepository
