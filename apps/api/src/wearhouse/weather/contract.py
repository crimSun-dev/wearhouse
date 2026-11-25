"""Weather gateway contract: BMKG entry validation and the LIVE -> CACHED -> MANUAL fallback policy.

A v2-owned copy of legacy/python/app/weather.py (`validate_entry`, `parse_feed` and the gateway's cache/
fallback decisions) at commit ea21b05, kept pure (no HTTP, no clock globals). The persistent weather cache
and recommendation endpoints arrive with the later services change; this module fixes their contract
now (PROGRESS-001). Behaviour is pinned by tests/test_weather_contract.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Jakarta"
REQUIRED_FIELDS = ("local_datetime", "t", "hu", "weather_desc")
TEMP_RANGE = (15.0, 40.0)
HUMIDITY_RANGE = (0.0, 100.0)
MAX_AHEAD = timedelta(days=3)
MAX_BEHIND = timedelta(days=1)
HOT_AT_C = 32.0
DEFAULT_TTL = timedelta(hours=3)
DEFAULT_STALE_MAX = timedelta(hours=6)


class WeatherSource(str, Enum):
    LIVE = "LIVE"
    CACHED = "CACHED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class BMKGFormatError(ValueError):
    """A BMKG entry/feed failed the contract checks."""


@dataclass(frozen=True)
class WeatherSlot:
    at: datetime  # UTC
    temp_c: float
    humidity: int
    description: str
    rain: bool
    hot: bool


def _number(raw: dict, key: str) -> float:
    v = raw[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
        raise BMKGFormatError(f"field {key!r} is not a number")
    return float(v)


def _entry_time(raw: dict, tz: str) -> datetime:
    try:
        utc = raw.get("utc_datetime")
        if utc:
            return datetime.strptime(utc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        local = datetime.strptime(raw["local_datetime"], "%Y-%m-%d %H:%M:%S")
        return local.replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise BMKGFormatError(f"bad datetime: {exc}") from exc


def validate_entry(raw: dict, now: datetime, tz: str = DEFAULT_TZ) -> WeatherSlot:
    """Required fields; 15 <= t <= 40 C; 0 <= hu <= 100 %; time within [now-1d, now+3d]."""
    if not isinstance(raw, dict):
        raise BMKGFormatError("entry is not an object")
    missing = [k for k in REQUIRED_FIELDS if raw.get(k) is None]
    if missing:
        raise BMKGFormatError(f"missing fields: {missing}")
    t = _number(raw, "t")
    hu = _number(raw, "hu")
    if not TEMP_RANGE[0] <= t <= TEMP_RANGE[1]:
        raise BMKGFormatError("temperature out of range")
    if not HUMIDITY_RANGE[0] <= hu <= HUMIDITY_RANGE[1]:
        raise BMKGFormatError("humidity out of range")
    desc = raw["weather_desc"]
    if not isinstance(desc, str) or not desc.strip():
        raise BMKGFormatError("weather_desc is empty")
    at = _entry_time(raw, tz)
    if at > now + MAX_AHEAD or at < now - MAX_BEHIND:
        raise BMKGFormatError("entry time outside the forecast window")
    return WeatherSlot(at=at, temp_c=t, humidity=int(round(hu)), description=desc,
                       rain="hujan" in desc.lower(), hot=t >= HOT_AT_C)


def feed_timezone(payload: dict) -> str:
    try:
        return payload["lokasi"].get("timezone") or DEFAULT_TZ
    except (KeyError, TypeError, AttributeError):
        return DEFAULT_TZ


def parse_feed(payload: dict, now: datetime) -> list[WeatherSlot]:
    """Any bad entry rejects the whole feed (partial data is never used)."""
    try:
        entries = [e for day in payload["data"][0]["cuaca"] for e in day]
    except (KeyError, IndexError, TypeError) as exc:
        raise BMKGFormatError("unexpected feed structure") from exc
    if not entries:
        raise BMKGFormatError("feed has no entries")
    tz = feed_timezone(payload)
    return sorted((validate_entry(e, now=now, tz=tz) for e in entries), key=lambda s: s.at)


@dataclass(frozen=True)
class CachedFeed:
    slots: tuple[WeatherSlot, ...]
    fetched_at: datetime
    fresh_until: datetime


@dataclass(frozen=True)
class Decision:
    source: WeatherSource
    slots: tuple[WeatherSlot, ...]
    note: str


class FallbackPolicy:
    def __init__(self, ttl: timedelta = DEFAULT_TTL, stale_max: timedelta = DEFAULT_STALE_MAX):
        self.ttl, self.stale_max = ttl, stale_max

    def use_cache_without_fetch(self, cached: CachedFeed | None, now: datetime) -> Decision | None:
        if cached is not None and now < cached.fresh_until:
            return Decision(WeatherSource.CACHED, cached.slots, "cache hit")
        return None

    def after_fetch_success(self, slots: list[WeatherSlot], now: datetime) -> tuple[Decision, CachedFeed]:
        entry = CachedFeed(tuple(slots), now, now + self.ttl)
        return Decision(WeatherSource.LIVE, entry.slots, "fetched"), entry

    def after_fetch_failure(self, cached: CachedFeed | None, now: datetime, reason: str) -> Decision:
        if cached is not None and now - cached.fetched_at <= self.stale_max:
            return Decision(WeatherSource.CACHED, cached.slots, f"fallback after {reason}")
        return Decision(WeatherSource.MANUAL_REQUIRED, (), reason)
