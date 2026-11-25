from __future__ import annotations

import ipaddress
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..identity.api import current_principal
from ..identity.domain import Principal
from ..platform.http import error_body
from ..platform.idempotency import Outcome, require_key
from ..platform.ids import parse_uuid


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductView(BaseModel):
    id: str
    name: str
    category: str
    facts: dict


class SourceView(BaseModel):
    namespace: str
    external_id: str


class PublicItem(BaseModel):
    public_serial: str
    product: ProductView
    catalogue_status: str
    source: SourceView


class Acquisition(BaseModel):
    revision_id: str
    revision_no: int
    source_namespace: str
    external_id: str
    snapshot_sha256: str


class UnitSizeOut(BaseModel):
    system: str
    code: str
    label: str


class OwnedItem(BaseModel):
    id: str
    public_serial: str
    product: ProductView
    size: Optional[UnitSizeOut] = None  # the purchased size (add-wearhouse-sizes)
    state: Literal["owned", "revoked_sandbox"] = "owned"  # complete-wearhouse-tdd: sandbox order cancelled
    revoked_at: Optional[str] = None
    revoked_reason: Optional[str] = None
    acquisition: Acquisition
    claimed_at: str


class OwnedItemPage(BaseModel):
    items: list[OwnedItem]
    next_cursor: Optional[str]


class Delivery(BaseModel):
    status: str = Field(description="available | expired | unavailable")
    activation_key: Optional[str] = Field(default=None, description="Present only while available")
    expires_at: Optional[str] = None
    expired_at: Optional[str] = None
    reason: Optional[str] = None


class IssuedUnit(BaseModel):
    unit_id: str
    public_serial: str
    product_id: str
    acquisition_revision_id: str
    revision_no: Optional[int] = None
    actor_bound: bool
    delivery: Delivery


class UnitBatchIn(_Strict):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=1, description="Single-unit issuance only in this release")
    audience_user_id: Optional[uuid.UUID] = Field(default=None,
                                                  description="Bind the key to one account (optional)")
    size: Optional[str] = Field(default=None, max_length=8, description="One of the product's size codes (optional)")


class RedemptionIn(_Strict):
    activation_key: StrictStr = Field(min_length=1, max_length=512,
                                      description="Private key XXXX-XXXX-XXXX-XXXX. Anything else -> generic 400.")


class ErrorOut(BaseModel):
    code: str
    message: str
    request_id: Optional[str]
    field_errors: Optional[list[dict]] = None


ERRORS = {s: {"model": ErrorOut} for s in (400, 401, 403, 404, 409, 422, 429, 503)}


def client_ip(request: Request) -> str | None:
    peer = request.client.host if request.client else None
    trusted = request.app.state.services.trusted_proxies
    if peer and peer in trusted:
        xff = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        for hop in reversed(xff):
            if hop not in trusted:
                peer = hop
                break
    try:
        return str(ipaddress.ip_address(peer)) if peer else None
    except ValueError:
        return None


def _respond(out: Outcome, model=None) -> JSONResponse:
    headers = {"Idempotent-Replayed": "true"} if out.replayed else {}
    if out.status >= 400:
        return JSONResponse(error_body(out.body.get("code", "ERROR"), out.body.get("message", "")),
                            status_code=out.status, headers=headers)
    body = model(**out.body).model_dump() if model else out.body
    return JSONResponse(body, status_code=out.status, headers=headers)


public_router = APIRouter(tags=["public discovery"])
private_router = APIRouter(tags=["ownership"])
admin_router = APIRouter(tags=["admin: inventory"])


@public_router.get("/items/{serial}", response_model=PublicItem, responses={404: {"model": ErrorOut}},
                   summary="Public tag lookup: product discovery only, never ownership")
def public_item(serial: str, request: Request) -> PublicItem:
    return PublicItem(**request.app.state.services.discovery.lookup(serial))


@private_router.post("/redemptions", status_code=201, response_model=OwnedItem, responses=ERRORS,
                     summary="Redeem a private activation key (verified user, Idempotency-Key required)")
def redeem(body: RedemptionIn, request: Request, principal: Principal = Depends(current_principal),
           idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    key = require_key(idempotency_key)
    out = request.app.state.services.redemption.redeem(principal, activation_key=body.activation_key,
                                                       idem_key=key, client_ip=client_ip(request))
    return _respond(out, OwnedItem)


@private_router.get("/me/items", response_model=OwnedItemPage, responses=ERRORS,
                    summary="The caller's owned items (stable cursor pagination)")
def my_items(request: Request, principal: Principal = Depends(current_principal),
             limit: Optional[int] = Query(default=None, description="1-100, default 24"),
             cursor: Optional[str] = Query(default=None, max_length=512)) -> OwnedItemPage:
    return OwnedItemPage(**request.app.state.services.owned_items.list(principal, limit=limit, cursor=cursor))


@private_router.get("/me/items/{item_id}", response_model=OwnedItem, responses=ERRORS,
                    summary="One owned item (404 for absent and other users' items alike)")
def my_item(item_id: str, request: Request, principal: Principal = Depends(current_principal)) -> OwnedItem:
    return OwnedItem(**request.app.state.services.owned_items.get(principal, parse_uuid(item_id)))


@admin_router.post("/admin/unit-batches", status_code=201, response_model=IssuedUnit, responses=ERRORS,
                   summary="Issue one serialized unit + private key (inventory_manager or admin)")
def issue_unit(body: UnitBatchIn, request: Request, principal: Principal = Depends(current_principal),
               idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    key = require_key(idempotency_key)
    out = request.app.state.services.issuance.issue(principal, product_id=body.product_id,
                                                    audience_user_id=body.audience_user_id, idem_key=key,
                                                    size=body.size)
    return _respond(out, IssuedUnit)


@admin_router.post("/admin/units/{unit_id}/reissue", status_code=201, response_model=IssuedUnit, responses=ERRORS,
                   summary="Revoke and reissue an unclaimed unit's key (inventory_manager or admin)")
def reissue_unit(unit_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal),
                 idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    key = require_key(idempotency_key)
    out = request.app.state.services.issuance.reissue(principal, unit_id=unit_id, idem_key=key)
    return _respond(out, IssuedUnit)


class StaffUnitOut(BaseModel):
    unit_id: str
    public_serial: str
    status: str
    created_at: str
    claimed_at: Optional[str]
    size: Optional[UnitSizeOut] = None


class StaffUnitsPage(BaseModel):
    items: list[StaffUnitOut]
    next_cursor: Optional[str]


@admin_router.get("/admin/units", response_model=StaffUnitsPage,
                  summary="Units of a product (inventory_manager or admin): serial/status only, never keys or owners")
def staff_units(request: Request, product_id: uuid.UUID = Query(...), limit: Optional[int] = Query(None),
                cursor: Optional[str] = Query(None, max_length=512), principal: Principal = Depends(current_principal)):
    return request.app.state.services.issuance.units(principal, product_id=product_id, limit=limit, cursor=cursor)
