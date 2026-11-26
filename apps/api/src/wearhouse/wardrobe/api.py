from __future__ import annotations

import uuid
from datetime import date
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from ..identity.api import current_principal
from ..identity.domain import Principal
from ..platform.errors import FieldError, validation_failed
from ..platform.http import error_body
from ..platform.idempotency import require_key
from ..recommendations.domain import ATTRIBUTES, OCCASIONS, RULESET_ID
from . import domain as d


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


SlotName = Literal["top", "outer", "bottom", "dress", "footwear", "underwear", "bag", "headwear", "eyewear", "earrings", "necklace",
                   "tie", "scarf", "belt", "wrist", "ring", "accessory"]
CareState = Literal["ready", "laundry", "repair", "stored"]


class WardrobeItemOut(BaseModel):
    id: str
    kind: Literal["verified", "declared"]
    verified: bool
    name: Optional[str]
    category: Optional[str]
    colour: Optional[str]
    colour_known: bool
    slot: str
    slot_source: Literal["override", "catalogue", "rule", "declared", "unknown"]  # rule: accessory-subtypes@1
    care_state: CareState
    wear_count: int
    last_worn_on: Optional[str]
    public_serial: Optional[str]
    product_id: Optional[str]
    claimed_at: Optional[str]
    has_photo: bool
    archived: bool
    size: Optional["ItemSizeOut"] = None
    size_source: Optional[Literal["owner", "purchase"]] = None
    attributes: dict[str, "AttributeOut"] = {}


class AttributeOut(BaseModel):
    """Thesis appendix lookup (origin rule, ruleset wardrobe-rules@1) or the owner's correction (origin owner)."""
    value: Union[StrictBool, StrictStr]
    origin: Literal["rule", "owner"]


class ItemSizeOut(BaseModel):
    system: str
    code: str
    label: str
    rank: int


WardrobeItemOut.model_rebuild()


class SizeRefIn(_Strict):
    system: StrictStr = Field(max_length=32)
    code: StrictStr = Field(max_length=8)


class ItemsOut(BaseModel):
    items: list[WardrobeItemOut]


class DeclareIn(_Strict):
    name: StrictStr = Field(max_length=80)
    slot: SlotName
    category: Optional[StrictStr] = Field(default=None, max_length=60)
    colour: Optional[StrictStr] = Field(default=None, max_length=40)
    size: Optional[SizeRefIn] = None


class ItemPatch(_Strict):
    care_state: Optional[CareState] = None
    slot_override: Optional[SlotName] = None
    name: Optional[StrictStr] = Field(default=None, max_length=80)
    archived: Optional[StrictBool] = None
    size: Optional[SizeRefIn] = None  # null clears your correction
    attributes: Optional[dict[str, Optional[Union[StrictBool, StrictStr]]]] = None  # value null = back to the rule


class SlotOut(BaseModel):
    slot: str
    capacity: int


class RegistryOut(BaseModel):
    slots: list[SlotOut]
    exclusions: list[list[str]]
    occasions: list[str] = []  # outfit-suggestion occasions (align-wearhouse-outfit-recommender)
    ruleset: Optional[str] = None
    attributes: list[str] = []


class ShelfIn(_Strict):
    name: StrictStr = Field(max_length=40)
    item_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


class ShelfPatch(_Strict):
    name: Optional[StrictStr] = Field(default=None, max_length=40)
    item_ids: Optional[list[uuid.UUID]] = Field(default=None, max_length=500)


class ShelfOut(BaseModel):
    id: str
    name: str
    item_ids: list[str]
    count: int


class LookIn(_Strict):
    name: StrictStr = Field(max_length=60)
    slots: dict[StrictStr, list[StrictStr]]


class LookPatch(_Strict):
    name: Optional[StrictStr] = Field(default=None, max_length=60)
    slots: Optional[dict[StrictStr, list[StrictStr]]] = None


class LookItemOut(BaseModel):
    slot: str
    item: Optional[WardrobeItemOut]
    missing_item_id: Optional[str] = None


class LookRevisionOut(BaseModel):
    id: str
    look_id: str
    revision_no: int
    name: str
    created_at: str
    slots: dict[str, list[str]]
    items: list[LookItemOut]


class RevisionRefOut(BaseModel):
    id: str
    revision_no: int
    name: str
    created_at: str


class LookOut(BaseModel):
    id: str
    name: str
    current_revision_no: int
    deleted: bool
    current: LookRevisionOut
    revisions: Optional[list[RevisionRefOut]] = None


class PlanIn(_Strict):
    look_revision_id: uuid.UUID
    occasion: Optional[Literal["casual", "work", "formal", "sport", "event"]] = None
    note: Optional[StrictStr] = Field(default=None, max_length=200)


class PlanOut(BaseModel):
    look_revision: LookRevisionOut
    occasion: Optional[str]
    note: Optional[str]


class WearOut(BaseModel):
    id: str
    worn_on: str
    look_revision_id: Optional[str]
    item_ids: list[str]
    created_at: str


class DayWeatherOut(BaseModel):
    status: Literal["forecast", "beyond_forecast", "unavailable"]
    reason: Optional[str] = None
    source: Optional[str] = None
    fetched_at: Optional[str] = None
    min_temp_c: Optional[float] = None
    max_temp_c: Optional[float] = None
    rain: Optional[bool] = None
    hot: Optional[bool] = None
    descriptions: Optional[list[str]] = None


class DayOut(BaseModel):
    date: str
    is_today: bool
    past: bool
    plan: Optional[PlanOut]
    worn: list[WearOut]
    weather: DayWeatherOut


class PlannerOut(BaseModel):
    days: list[DayOut]
    from_: str = Field(alias="from")
    model_config = ConfigDict(populate_by_name=True)


class WearIn(_Strict):
    worn_on: date
    look_revision_id: Optional[uuid.UUID] = None
    item_ids: Optional[list[uuid.UUID]] = Field(default=None, max_length=20)


class WearLogOut(BaseModel):
    entries: list[WearOut]


class ModelOut(BaseModel):
    mode: Literal["heuristic_baseline", "trained"]
    name: str
    version: str
    trained_artifact: Optional[str]


class SuggestionWeatherOut(BaseModel):
    source: Literal["LIVE", "CACHED", "MANUAL", "NONE", "DISABLED"]  # DISABLED: weather off in Settings
    rain: Optional[bool]
    hot: Optional[bool]


class SuggestionOut(BaseModel):
    item_ids: list[str]
    slots: dict[str, str]
    score: Optional[float]
    components: dict[str, Union[float, None]]  # compatibility, preference (Eq. 8), recency (Eq. 9)
    explanation: list[str] = []
    items: list[WardrobeItemOut]


class SuggestionsOut(BaseModel):
    enabled: bool = True  # false when turned off in Settings (add-wearhouse-settings-security)
    run_id: Optional[str] = None  # post displayed/chosen events against it (align-wearhouse-outfit-recommender)
    ruleset: Optional[str] = None
    occasion: Optional[str] = None
    params: Optional[dict[str, float]] = None
    removed_by_rule: dict[str, int] = {}
    date: str
    model: Optional[ModelOut]
    style: Optional[str] = None
    weights: Optional[dict[str, float]] = None
    weather: SuggestionWeatherOut
    occasion_used: bool
    ready_items: int
    candidates_considered: int
    reasons: list[str]
    suggestions: list[SuggestionOut]


def _svc(request: Request):
    return request.app.state.services.wardrobe


public_router = APIRouter(tags=["wardrobe"])
router = APIRouter(tags=["wardrobe: me"])


@public_router.get("/wardrobe/slots", response_model=RegistryOut, summary="Slot registry and occupancy rules")
def slots():
    return {**d.registry(), "occasions": list(OCCASIONS), "ruleset": RULESET_ID, "attributes": list(ATTRIBUTES)}


# ------------------------------------------------------------------ items
@router.get("/me/wardrobe/items", response_model=ItemsOut, summary="Your wardrobe: verified + declared items")
def items(request: Request, slot: Optional[str] = Query(None, max_length=16),
          care_state: Optional[str] = Query(None, max_length=16), shelf_id: Optional[uuid.UUID] = Query(None),
          size: Optional[str] = Query(None, max_length=48, description="system:code, e.g. alpha:M"),
          sort: Optional[str] = Query(None, max_length=8, description="size | name | worn"),
          principal: Principal = Depends(current_principal)):
    return _svc(request).items(principal, slot=slot, care_state=care_state, shelf_id=shelf_id, size=size, sort=sort)


@router.post("/me/wardrobe/items", status_code=201, response_model=WardrobeItemOut,
             summary="Declare a manual item (thrifted/gifted): no serial, unknowns stay unknown")
def declare(body: DeclareIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).declare(principal, name=body.name, slot=body.slot, category=body.category,
                                 colour=body.colour, size=body.size.model_dump() if body.size else None)


@router.get("/me/wardrobe/items/{item_id}", response_model=WardrobeItemOut, summary="One of your items")
def item(item_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).item(principal, item_id)


@router.patch("/me/wardrobe/items/{item_id}", response_model=WardrobeItemOut,
              summary="Care state, slot override (null clears), name/archive for declared items")
def update_item(item_id: uuid.UUID, body: ItemPatch, request: Request,
                principal: Principal = Depends(current_principal)):
    changes = {k: getattr(body, k) for k in body.model_fields_set}
    if "size" in changes and changes["size"] is not None:
        changes["size"] = changes["size"].model_dump()
    return _svc(request).update_item(principal, item_id, changes)


@router.put("/me/wardrobe/items/{item_id}/photo", response_model=WardrobeItemOut,
            summary="Upload a private photo for a declared item (raw JPEG/PNG/WebP body, max 2 MB)",
            openapi_extra={"requestBody": {"required": True, "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/webp": {"schema": {"type": "string", "format": "binary"}}}}})
async def put_photo(item_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > d.MAX_PHOTO_BYTES:
            raise validation_failed([FieldError("body", "too_large", "Photos are at most 2 MB.")])
    return await run_in_threadpool(_svc(request).put_photo, principal, item_id, bytes(data))


@router.get("/me/wardrobe/items/{item_id}/photo", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}},
            summary="Your declared item photo (owner only)")
def get_photo(item_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    data, ctype = _svc(request).photo(principal, item_id)
    return Response(content=data, media_type=ctype, headers={"X-Content-Type-Options": "nosniff"})


# ------------------------------------------------------------------ shelves
@router.get("/me/wardrobe/shelves", response_model=list[ShelfOut], summary="Your shelves")
def shelves(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).shelves(principal)


@router.post("/me/wardrobe/shelves", status_code=201, response_model=ShelfOut, summary="Create a shelf")
def create_shelf(body: ShelfIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).create_shelf(principal, body.name, body.item_ids)


@router.patch("/me/wardrobe/shelves/{shelf_id}", response_model=ShelfOut, summary="Rename / replace items in order")
def update_shelf(shelf_id: uuid.UUID, body: ShelfPatch, request: Request,
                 principal: Principal = Depends(current_principal)):
    return _svc(request).update_shelf(principal, shelf_id, name=body.name, item_ids=body.item_ids)


@router.delete("/me/wardrobe/shelves/{shelf_id}", status_code=204, summary="Delete a shelf (items stay)")
def delete_shelf(shelf_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).delete_shelf(principal, shelf_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ looks
@router.get("/me/looks", response_model=list[LookOut], summary="Your looks (current revisions)")
def looks(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).looks(principal)


@router.post("/me/looks", status_code=201, response_model=LookOut, summary="Create a look (revision 1)")
def create_look(body: LookIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).create_look(principal, body.name, body.slots)


@router.get("/me/looks/{look_id}", response_model=LookOut, summary="A look with its revision history")
def look(look_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).look(principal, look_id)


@router.patch("/me/looks/{look_id}", response_model=LookOut, summary="Edit a look (writes a new revision)")
def edit_look(look_id: uuid.UUID, body: LookPatch, request: Request,
              principal: Principal = Depends(current_principal)):
    return _svc(request).edit_look(principal, look_id, body.name, body.slots)


@router.delete("/me/looks/{look_id}", status_code=204, summary="Delete a look (revisions stay for plans/history)")
def delete_look(look_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).delete_look(principal, look_id)
    return Response(status_code=204)


@router.get("/me/look-revisions/{revision_id}", response_model=LookRevisionOut, summary="One immutable revision")
def revision(revision_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).revision(principal, revision_id)


# ------------------------------------------------------------------ planner
@router.get("/me/planner", response_model=PlannerOut, response_model_by_alias=True,
            summary="Seven local dates: plans, wear and forecast-horizon-labelled weather")
def planner(request: Request, from_: Optional[date] = Query(None, alias="from"),
            principal: Principal = Depends(current_principal)):
    return _svc(request).planner(principal, from_)


@router.put("/me/planner/{plan_date}", response_model=DayOut, summary="Plan a look revision for a date (today..+30)")
def set_plan(plan_date: date, body: PlanIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).set_plan(principal, plan_date, look_revision_id=body.look_revision_id,
                                  occasion=body.occasion, note=body.note)


@router.delete("/me/planner/{plan_date}", status_code=204, summary="Clear a date plan")
def clear_plan(plan_date: date, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).clear_plan(principal, plan_date)
    return Response(status_code=204)


# ------------------------------------------------------------------ wear
@router.post("/me/wear", status_code=201, response_model=WearOut,
             summary="Log what you actually wore (Idempotency-Key required; today..-60 days)")
def log_wear(body: WearIn, request: Request, principal: Principal = Depends(current_principal),
             idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    out = _svc(request).log_wear(principal, worn_on=body.worn_on, look_revision_id=body.look_revision_id,
                                 item_ids=body.item_ids, idem_key=require_key(idempotency_key))
    headers = {"Idempotent-Replayed": "true"} if out.replayed else {}
    if out.status >= 400:
        return JSONResponse(error_body(out.body.get("code", "ERROR"), out.body.get("message", "")),
                            status_code=out.status, headers=headers)
    return JSONResponse(out.body, status_code=out.status, headers=headers)


@router.get("/me/wear", response_model=WearLogOut, summary="Your wear log")
def wear_log(request: Request, from_: Optional[date] = Query(None, alias="from"), to: Optional[date] = Query(None),
             principal: Principal = Depends(current_principal)):
    return _svc(request).wear_log(principal, from_, to)


@router.delete("/me/wear/{wear_id}", status_code=204, summary="Delete a wear entry")
def delete_wear(wear_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).delete_wear(principal, wear_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ suggestions
@router.get("/me/recommendations/outfits", response_model=SuggestionsOut,
            summary="Outfit suggestions: thesis hard rules + Eqs. 7-9 (heuristic compatibility; declared mode)")
def suggestions(request: Request, on: Optional[date] = Query(None, alias="date"), limit: int = Query(5),
                rain: Optional[bool] = Query(None), hot: Optional[bool] = Query(None),
                occasion: Optional[str] = Query(None, max_length=16),
                principal: Principal = Depends(current_principal)):
    return _svc(request).suggestions(principal, on=on, limit=limit, rain=rain, hot=hot, occasion=occasion)


class SuggestionEventIn(_Strict):
    kind: Literal["displayed", "chosen"]
    index: Optional[StrictInt] = None


class SuggestionEventOut(BaseModel):
    run_id: str
    displayed: bool
    chosen_index: Optional[int]


@router.post("/me/recommendations/outfits/{run_id}/events", response_model=SuggestionEventOut,
             summary="Record that a run's suggestions were displayed, or which one you chose (once per run)")
def suggestion_event(run_id: uuid.UUID, body: SuggestionEventIn, request: Request,
                     principal: Principal = Depends(current_principal)):
    return _svc(request).suggestion_event(principal, run_id, kind=body.kind, index=body.index)
