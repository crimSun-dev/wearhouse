from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from ..identity.api import current_principal
from ..identity.domain import Principal
from ..platform.http import error_body
from ..platform.idempotency import Outcome, require_key


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfferIn(_Strict):
    price_idr: StrictInt
    stock: StrictInt  # for a sized product: stock of EACH size unless size_stock names it
    currency: StrictStr = "IDR"
    size_stock: Optional[dict[StrictStr, StrictInt]] = Field(default=None, max_length=40)


class SizeLabelOut(BaseModel):
    system: str
    code: str
    label: str


class SizeRefOut(SizeLabelOut):
    rank: int


class OfferSizeOut(SizeRefOut):
    in_stock: bool


class StaffOfferSizeOut(OfferSizeOut):
    stock: int


class StaffOfferOut(BaseModel):
    product_id: str
    name: Optional[str]
    price_idr: int
    currency: str
    stock: int
    on_sale: bool
    sandbox: Literal[True]
    updated_at: str
    sizes: list[StaffOfferSizeOut] = []


class OfferView(BaseModel):
    price_idr: int
    currency: str
    in_stock: bool
    sandbox: Literal[True]


class PublicOfferOut(OfferView):
    product_id: str
    sizes: list[OfferSizeOut] = []  # empty = one size; never stock counts


class WishlistItemOut(BaseModel):
    product_id: str
    name: Optional[str]
    available: bool
    offer: Optional[OfferView]
    added_at: str


class WishlistOut(BaseModel):
    items: list[WishlistItemOut]
    limit: int


class CartLineIn(_Strict):
    quantity: StrictInt
    size: Optional[StrictStr] = Field(default=None, max_length=8)  # size code; required for sized products


class CartLineOut(BaseModel):
    product_id: str
    name: Optional[str]
    quantity: int
    size: Optional[SizeRefOut]
    unit_price_idr: Optional[int]
    line_total_idr: Optional[int]
    available: bool


class CartOut(BaseModel):
    lines: list[CartLineOut]
    total_idr: int
    currency: str
    sandbox: Literal[True]
    checkout_ready: bool
    limit: int


class CheckoutIn(_Strict):
    expected_total_idr: StrictInt = Field(ge=0)


class DeliveryState(BaseModel):
    status: Literal["available", "expired", "unavailable", "claimed"]
    expires_at: Optional[str] = None
    expired_at: Optional[str] = None
    reason: Optional[str] = None


class OrderUnitOut(BaseModel):
    unit_id: str
    public_serial: Optional[str]
    state: str
    delivery: DeliveryState


class OrderLineOut(BaseModel):
    line_no: int
    product_id: str
    product_name: str
    size: Optional[SizeLabelOut]
    unit_price_idr: int
    quantity: int
    line_total_idr: int
    units: list[OrderUnitOut]


class ReceiptOut(BaseModel):
    id: str
    status: Literal["fulfilled", "cancelled"]
    currency: str
    total_idr: int
    sandbox: Literal[True]
    payment_ref: str
    created_at: str
    cancelled_at: Optional[str]
    cancellable: bool
    lines: list[OrderLineOut]


class OrderSummaryOut(BaseModel):
    id: str
    status: str
    total_idr: int
    currency: str
    sandbox: Literal[True]
    created_at: str
    item_count: int
    names: list[str]


class OrdersPageOut(BaseModel):
    items: list[OrderSummaryOut]
    next_cursor: Optional[str]


class KeyOut(BaseModel):
    """The private activation key of one purchased unit. Buyer only; every reveal is audited."""

    unit_id: str
    status: Literal["available", "expired", "unavailable", "claimed"]
    activation_key: Optional[str] = None
    expires_at: Optional[str] = None
    expired_at: Optional[str] = None
    reason: Optional[str] = None


class RenewOut(BaseModel):
    unit_id: str
    status: Literal["renewed"]


def _svc(request: Request):
    return request.app.state.services.commerce


def _respond(out: Outcome, model) -> JSONResponse:
    headers = {"Idempotent-Replayed": "true"} if out.replayed else {}
    if out.status >= 400:
        return JSONResponse(error_body(out.body.get("code", "ERROR"), out.body.get("message", "")),
                            status_code=out.status, headers=headers)
    return JSONResponse(model(**out.body).model_dump(), status_code=out.status, headers=headers)


admin_router = APIRouter(tags=["admin: commerce"])
public_router = APIRouter(tags=["commerce"])
me_router = APIRouter(tags=["commerce: me"])


# ------------------------------------------------------------------ staff offers
@admin_router.get("/admin/commerce/offers", response_model=list[StaffOfferOut], summary="All sandbox offers")
def staff_offers(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).staff_offers(principal)


@admin_router.put("/admin/commerce/offers/{product_id}", response_model=StaffOfferOut,
                  summary="Set a sandbox price and stock (catalogue_editor or admin). Nothing is ever charged.")
def put_offer(product_id: uuid.UUID, body: OfferIn, request: Request,
              principal: Principal = Depends(current_principal)):
    return _svc(request).put_offer(principal, product_id, price_idr=body.price_idr, stock=body.stock,
                                   currency=body.currency, size_stock=body.size_stock)


@admin_router.delete("/admin/commerce/offers/{product_id}", status_code=204, summary="Withdraw a sandbox offer")
def delete_offer(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).delete_offer(principal, product_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ public
@public_router.get("/commerce/products/{product_id}/offer", response_model=PublicOfferOut,
                   summary="Sandbox offer of a published product (no stock count)")
def public_offer(product_id: uuid.UUID, request: Request):
    return _svc(request).public_offer(product_id)


# ------------------------------------------------------------------ wishlist / cart
@me_router.get("/me/wishlist", response_model=WishlistOut, summary="Your wishlist")
def wishlist(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).wishlist(principal)


@me_router.put("/me/wishlist/{product_id}", response_model=WishlistOut, summary="Add a published product")
def add_wishlist(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).add_wishlist(principal, product_id)


@me_router.delete("/me/wishlist/{product_id}", status_code=204, summary="Remove from your wishlist")
def remove_wishlist(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).remove_wishlist(principal, product_id)
    return Response(status_code=204)


@me_router.get("/me/cart", response_model=CartOut, summary="Your cart with current sandbox prices")
def cart(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).cart(principal)


@me_router.put("/me/cart/{product_id}", response_model=CartOut, summary="Set a cart quantity (1-5)")
def set_cart(product_id: uuid.UUID, body: CartLineIn, request: Request,
             principal: Principal = Depends(current_principal)):
    return _svc(request).set_cart_line(principal, product_id, body.quantity, body.size)


@me_router.delete("/me/cart/{product_id}", response_model=CartOut, summary="Remove a cart line (size for sized lines)")
def remove_cart(product_id: uuid.UUID, request: Request, size: Optional[str] = Query(None, max_length=8),
                principal: Principal = Depends(current_principal)):
    return _svc(request).remove_cart_line(principal, product_id, size)


# ------------------------------------------------------------------ orders
@me_router.post("/me/checkout", status_code=201, response_model=ReceiptOut,
                summary="Sandbox checkout (Idempotency-Key required). Issues buyer-bound units; no money is charged.")
def checkout(body: CheckoutIn, request: Request, principal: Principal = Depends(current_principal),
             idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    out = _svc(request).checkout(principal, expected_total_idr=body.expected_total_idr,
                                 idem_key=require_key(idempotency_key))
    return _respond(out, ReceiptOut)


@me_router.get("/me/orders", response_model=OrdersPageOut, summary="Your sandbox orders, newest first")
def orders(request: Request, limit: Optional[int] = Query(None), cursor: Optional[str] = Query(None, max_length=512),
           principal: Principal = Depends(current_principal)):
    return _svc(request).orders(principal, limit=limit, cursor=cursor)


@me_router.get("/me/orders/{order_id}", response_model=ReceiptOut, summary="Receipt (no keys)")
def receipt(order_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).receipt(principal, order_id)


@me_router.get("/me/orders/{order_id}/units/{unit_id}/key", response_model=KeyOut,
               summary="Reveal one purchased unit's activation key (buyer only, audited)")
def reveal_key(order_id: uuid.UUID, unit_id: uuid.UUID, request: Request,
               principal: Principal = Depends(current_principal)):
    return _svc(request).reveal_key(principal, order_id, unit_id)


@me_router.post("/me/orders/{order_id}/units/{unit_id}/renew-key", status_code=201, response_model=RenewOut,
                summary="Revoke and renew an unclaimed unit's key (Idempotency-Key required)")
def renew_key(order_id: uuid.UUID, unit_id: uuid.UUID, request: Request,
              principal: Principal = Depends(current_principal),
              idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    out = _svc(request).renew_key(principal, order_id, unit_id, idem_key=require_key(idempotency_key))
    return _respond(out, RenewOut)


@me_router.post("/me/orders/{order_id}/cancel", response_model=ReceiptOut,
                summary="Cancel while no unit is claimed: keys revoked, units retired, stock restored")
def cancel(order_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).cancel(principal, order_id)


# ------------------------------------------------------------------ staff (add-wearhouse-object-management)
class StaffOrderLineOut(BaseModel):
    product_id: str
    product_name: str
    size: Optional[SizeLabelOut]
    unit_price_idr: int
    quantity: int


class StaffOrderOut(BaseModel):
    id: str
    status: str
    total_idr: int
    currency: str
    sandbox: Literal[True]
    created_at: str
    cancelled_at: Optional[str]
    buyer_handle: Optional[str]
    item_count: int
    lines: list[StaffOrderLineOut]


class StaffOrdersPage(BaseModel):
    items: list[StaffOrderOut]
    next_cursor: Optional[str]


class OfferRuleIn(_Strict):
    category: Optional[StrictStr] = Field(default=None, max_length=100)
    slot: Optional[StrictStr] = Field(default=None, max_length=32)
    price_idr: StrictInt
    stock: StrictInt


class BulkOffersIn(_Strict):
    rules: list[OfferRuleIn] = Field(max_length=50)
    overwrite: bool = False


class BulkRuleResultOut(BaseModel):
    category: Optional[str]
    slot: Optional[str]
    matched: int
    written: int
    sized: int = 0  # written offers whose product has sizes (stock applied per size)


class BulkOffersOut(BaseModel):
    overwrite: bool
    sandbox: Literal[True]
    results: list[BulkRuleResultOut]


def _staff(request: Request):
    return request.app.state.services.commerce_staff


@admin_router.get("/admin/commerce/orders", response_model=StaffOrdersPage,
                  summary="All sandbox orders (inventory_manager or admin); never keys")
def staff_orders(request: Request, status: Optional[str] = Query(None, max_length=16), limit: Optional[int] = Query(None),
                 cursor: Optional[str] = Query(None, max_length=512), principal: Principal = Depends(current_principal)):
    return _staff(request).orders(principal, status=status, limit=limit, cursor=cursor)


@admin_router.post("/admin/commerce/offers/bulk", response_model=BulkOffersOut,
                   summary="Bulk sandbox offers by category/slot rules (mock prices, labelled sandbox)")
def bulk_offers(body: BulkOffersIn, request: Request, principal: Principal = Depends(current_principal)):
    return _staff(request).bulk_offers(principal, rules=[r.model_dump() for r in body.rules], overwrite=body.overwrite)
