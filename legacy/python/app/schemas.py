"""Pydantic contracts for interface I1 (client ↔ server). OpenAPI at /docs is generated from these."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Slot = Literal["top", "bottom", "dress", "outer", "footwear", "accessory"]
Occasion = Literal["campus", "casual", "worship", "formal", "wedding"]
Style = Literal["casual", "smart", "formal", "modest", "sporty", "street"]
FaultMode = Literal["none", "timeout", "http500", "malformed", "missing_fields"]
ADM4_PATTERN = r"^\d{2}\.\d{2}\.\d{2}\.\d{4}$"


class GarmentAttrs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    color_hex: str = Field("#808080", pattern=r"^#[0-9A-Fa-f]{6}$")
    style: Style = "casual"
    rain_suitable: bool = False
    heavy: bool = False
    long_sleeve: bool = False
    long_bottom: bool = False
    formality: int = Field(1, ge=1, le=5)


class GarmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slot: Slot
    attrs: GarmentAttrs = Field(default_factory=GarmentAttrs)


class GarmentOut(BaseModel):
    id: uuid.UUID
    name: str
    slot: str
    attrs: dict
    gtin: str | None = None
    serial: str | None = None
    origin: Literal["manual", "registered"]
    times_recommended: int
    times_chosen: int
    last_worn_at: date | None = None


class ManualWeatherIn(BaseModel):
    rain: bool
    hot: bool


class RecommendIn(BaseModel):
    occasion: Occasion
    when: datetime | None = Field(None, description="Defaults to now. Naive times are read as the location's local time.")
    adm4: str | None = Field(None, pattern=ADM4_PATTERN, description="BMKG village code, default Kemayoran (Jakarta)")
    manual_weather: ManualWeatherIn | None = Field(
        None, description="Two-tap manual answer. When given, BMKG is skipped and source=MANUAL."
    )


class OutfitIn(BaseModel):
    items: list[uuid.UUID] = Field(min_length=1, max_length=6)
    label: str | None = Field(None, max_length=60)
    planned_for: date | None = None
    occasion: Occasion | None = None


class OutfitOut(BaseModel):
    id: uuid.UUID
    label: str | None
    planned_for: date | None
    occasion: str | None
    items: list[GarmentOut]


class WearIn(BaseModel):
    worn_on: date | None = None


class ActivateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class ScanIn(BaseModel):
    gtin: str = Field(pattern=r"^\d{14}$")
    serial: str = Field(pattern=r"^[0-9a-f]{32}$")


class FaultIn(BaseModel):
    mode: FaultMode


class IssueCodesIn(BaseModel):
    gtin: str = Field(pattern=r"^\d{14}$")
    count: int = Field(1, ge=1, le=20)
