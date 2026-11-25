"""Sandbox commerce rules (pure). Prices are mock values set by staff; nothing is ever charged."""
from __future__ import annotations

from ..platform.errors import ApiError, FieldError, conflict, validation_failed

CURRENCY = "IDR"
MAX_PRICE_IDR = 100_000_000
MAX_STOCK = 100_000
MAX_QUANTITY = 5
MAX_CART_LINES = 20
MAX_WISHLIST = 500
SANDBOX_PAYMENT_REF = "sandbox-approved"
ORDER_FULFILLED, ORDER_CANCELLED = "fulfilled", "cancelled"


def offer_errors(price_idr: int, stock: int, currency: str) -> list[FieldError]:
    e = []
    if not 1 <= price_idr <= MAX_PRICE_IDR:
        e.append(FieldError("body.price_idr", "out_of_range", f"Price must be 1-{MAX_PRICE_IDR:,} rupiah."))
    if not 0 <= stock <= MAX_STOCK:
        e.append(FieldError("body.stock", "out_of_range", f"Stock must be 0-{MAX_STOCK:,}."))
    if currency != CURRENCY:
        e.append(FieldError("body.currency", "unsupported", "Only IDR is supported."))
    return e


def check_quantity(quantity: int) -> None:
    if not 1 <= quantity <= MAX_QUANTITY:
        raise validation_failed([FieldError("body.quantity", "out_of_range", f"Quantity must be 1-{MAX_QUANTITY}.")])


def not_for_sale() -> ApiError:
    return conflict("NOT_FOR_SALE", "This product has no sandbox offer.")


def out_of_stock(names: list[str]) -> ApiError:
    return conflict("OUT_OF_STOCK", "Not enough sandbox stock for: " + ", ".join(names) + ".")


def price_changed() -> ApiError:
    return conflict("PRICE_CHANGED", "The cart total changed since you looked. Review the cart and try again.")


def not_available(names: list[str]) -> ApiError:
    return conflict("NOT_AVAILABLE", "No longer available: " + ", ".join(names) + ".")


def size_required() -> ApiError:
    return validation_failed([FieldError("body.size", "size_required", "Choose a size for this product.")])


def size_not_offered(code: str) -> ApiError:
    return validation_failed([FieldError("body.size", "unknown_size", f"This product does not come in size {code}.")])


def one_size_only() -> ApiError:
    return validation_failed([FieldError("body.size", "one_size", "This product is one size; do not send a size.")])
