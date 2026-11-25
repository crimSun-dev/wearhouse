from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from ..platform.ports import UnitOfWork
from .contract import CachedFeed


class FetchError(Exception):
    """The forecast source could not be reached or answered badly (reason is safe to show)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ForecastFetcher(Protocol):
    def fetch(self, adm4: str) -> dict: ...  # raw BMKG payload; raises FetchError


class WeatherRepository(Protocol):
    def get_cache(self, adm4: str) -> CachedFeed | None: ...
    def put_cache(self, adm4: str, feed: CachedFeed) -> None: ...
    def get_location(self, user_id: uuid.UUID) -> str | None: ...
    def set_location(self, user_id: uuid.UUID, adm4: str, now: datetime) -> None: ...
    def clear_location(self, user_id: uuid.UUID) -> None: ...


class WeatherUoW(UnitOfWork, Protocol):
    weather: WeatherRepository
