from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ..identity.api import current_principal
from ..identity.domain import Principal


class RecModelOut(BaseModel):
    mode: Literal["heuristic_baseline", "trained"]
    name: str
    version: str
    trained_artifact: Optional[str]
    fallback: Optional[str] = None


class RecCardOut(BaseModel):
    id: str
    name: Optional[str]
    category: Optional[str]
    colour: Optional[str]
    slot: Optional[str]
    thumbnail: Optional[str]


class SimilarOut(BaseModel):
    product_id: str
    model: RecModelOut
    items: list[RecCardOut]


class RerankScoreOut(BaseModel):
    completion: float
    duplicate: float


class PersonalCardOut(RecCardOut):
    rerank: Optional[RerankScoreOut] = None


class RerankOut(BaseModel):
    name: str
    lambda_c: float
    lambda_d: float
    cold_start: bool


class ForMeOut(BaseModel):
    model: RecModelOut
    sized_to_you: bool = False  # true when products missing your usual size were left out (add-wearhouse-sizes)
    rerank: Optional[RerankOut] = None  # complete-wearhouse-tdd: Eq. 3 heuristic (declared, not tuned)
    items: list[PersonalCardOut]


public_router = APIRouter(tags=["recommendations"])
me_router = APIRouter(tags=["recommendations: me"])


def _svc(request: Request):
    return request.app.state.services.recommendations


@public_router.get("/catalogue/products/{product_id}/similar", response_model=SimilarOut,
                   summary="Similar published products with a declared model mode")
def similar(product_id: uuid.UUID, request: Request, limit: int = Query(12)):
    return _svc(request).similar(product_id, limit)


@me_router.get("/me/recommendations/products", response_model=ForMeOut,
               summary="Products for you (never ones you own) with a declared model mode")
def for_me(request: Request, limit: int = Query(12), principal: Principal = Depends(current_principal)):
    return _svc(request).for_me(principal, limit)
