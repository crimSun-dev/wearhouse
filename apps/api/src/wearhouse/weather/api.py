from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, StrictStr

from ..identity.api import current_principal
from ..identity.domain import Principal


class WeatherSlotOut(BaseModel):
    at: str
    local_date: str
    temp_c: float
    humidity: int
    description: str
    rain: bool
    hot: bool


class ForecastOut(BaseModel):
    adm4: Optional[str]
    source: Literal["LIVE", "CACHED", "MANUAL_REQUIRED"]
    note: str
    fetched_at: Optional[str]
    slots: list[WeatherSlotOut]


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adm4: StrictStr


class LocationOut(BaseModel):
    adm4: str


router = APIRouter(tags=["weather"])


def _svc(request: Request):
    return request.app.state.services.weather


@router.get("/weather/forecast", response_model=ForecastOut,
            summary="BMKG forecast for an adm4 code (signed in): LIVE, CACHED (<= 6 h) or MANUAL_REQUIRED")
def forecast(request: Request, adm4: str = Query(..., max_length=13), principal: Principal = Depends(current_principal)):
    return _svc(request).forecast(adm4)


@router.get("/me/weather", response_model=ForecastOut, summary="Forecast for your saved BMKG location")
def my_weather(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).my_weather(principal.user_id)


@router.put("/me/weather/location", response_model=LocationOut, summary="Set your BMKG adm4 location")
def set_location(body: LocationIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).set_location(principal.user_id, body.adm4)


@router.delete("/me/weather/location", status_code=204, summary="Clear your weather location")
def clear_location(request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).clear_location(principal.user_id)
    return Response(status_code=204)
