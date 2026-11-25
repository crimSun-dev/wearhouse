"""Weather Gateway — the BMKG integration (interface I2; course Ch 9, 11–12).

The server is the only component that talks to BMKG. Every entry is validated
(contract checks), feeds are cached for 3 h, and failures walk the fault ladder
LIVE → CACHED (≤ 6 h old) → MANUAL.
"""
from __future__ import annotations

import asyncio
import copy
import json
import math
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

import httpx

BMKG_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
DEFAULT_TZ = "Asia/Jakarta"
REQUIRED_FIELDS = ("local_datetime", "t", "hu", "weather_desc")
TEMP_RANGE = (15.0, 40.0)
HUMIDITY_RANGE = (0.0, 100.0)
MAX_AHEAD = timedelta(days=3)
MAX_BEHIND = timedelta(days=1)
HOT_AT_C = 32.0
MAX_SLOT_GAP = timedelta(hours=3)
FAULT_MODES = ("none", "timeout", "http500", "malformed", "missing_fields")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WeatherSource(str, Enum):
    LIVE = "LIVE"
    CACHED = "CACHED"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class WeatherSlot:
    at: datetime  # UTC
    temp_c: float | None
    humidity: int | None
    description: str
    rain: bool
    hot: bool
    source: WeatherSource
    fetched_at: datetime | None
    note: str = ""


@dataclass(frozen=True)
class ManualWeather:
    rain: bool
    hot: bool


class WeatherUnavailable(Exception):
    """No live data and no usable cache: the client must ask for manual input."""


class BMKGFormatError(ValueError):
    """A BMKG entry/feed failed the I2 contract checks."""


# ---------------------------------------------------------------- validation
def _number(raw: dict, key: str) -> float:
    v = raw[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
        raise BMKGFormatError(f"field {key!r} is not a number: {v!r}")
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


def validate_entry(
    raw: dict,
    now: datetime | None = None,
    tz: str = DEFAULT_TZ,
    source: WeatherSource = WeatherSource.LIVE,
    fetched_at: datetime | None = None,
) -> WeatherSlot:
    """I2 contract: required fields; 15 ≤ t ≤ 40 °C; 0 ≤ hu ≤ 100 %; time within 3 days."""
    if not isinstance(raw, dict):
        raise BMKGFormatError("entry is not an object")
    missing = [k for k in REQUIRED_FIELDS if raw.get(k) is None]
    if missing:
        raise BMKGFormatError(f"missing fields: {missing}")
    t = _number(raw, "t")
    hu = _number(raw, "hu")
    if not TEMP_RANGE[0] <= t <= TEMP_RANGE[1]:
        raise BMKGFormatError(f"temperature {t} outside {TEMP_RANGE}")
    if not HUMIDITY_RANGE[0] <= hu <= HUMIDITY_RANGE[1]:
        raise BMKGFormatError(f"humidity {hu} outside {HUMIDITY_RANGE}")
    desc = raw["weather_desc"]
    if not isinstance(desc, str) or not desc.strip():
        raise BMKGFormatError("weather_desc is empty")
    at = _entry_time(raw, tz)
    now = now or utcnow()
    if at > now + MAX_AHEAD or at < now - MAX_BEHIND:
        raise BMKGFormatError(f"entry time {at.isoformat()} not within 3 days of {now.isoformat()}")
    return WeatherSlot(
        at=at,
        temp_c=t,
        humidity=int(round(hu)),
        description=desc,
        rain="hujan" in desc.lower(),
        hot=t >= HOT_AT_C,
        source=source,
        fetched_at=fetched_at or now,
    )


def feed_timezone(payload: dict) -> str:
    try:
        return payload["lokasi"].get("timezone") or DEFAULT_TZ
    except (KeyError, TypeError, AttributeError):
        return DEFAULT_TZ


def parse_feed(payload: dict, now: datetime | None = None) -> list[WeatherSlot]:
    """Validate a whole BMKG feed. Any bad entry rejects the whole feed (never use partial data)."""
    try:
        cuaca = payload["data"][0]["cuaca"]
        entries = [e for day in cuaca for e in day]
    except (KeyError, IndexError, TypeError) as exc:
        raise BMKGFormatError(f"unexpected feed structure: {exc!r}") from exc
    if not entries:
        raise BMKGFormatError("feed has no entries")
    tz = feed_timezone(payload)
    now = now or utcnow()
    slots = [validate_entry(e, now=now, tz=tz, fetched_at=now) for e in entries]
    return sorted(slots, key=lambda s: s.at)


# ------------------------------------------------------------------- clients
class BMKGClient(Protocol):
    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict: ...


class HttpBMKGClient:
    """Real client for api.bmkg.go.id. A total deadline wraps the httpx per-phase timeouts."""

    def __init__(self, url: str = BMKG_URL, transport: httpx.AsyncBaseTransport | None = None):
        self.url = url
        self.transport = transport

    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict:
        async with httpx.AsyncClient(timeout=timeout_s, transport=self.transport) as client:
            resp = await asyncio.wait_for(client.get(self.url, params={"adm4": adm4}), timeout_s)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise BMKGFormatError("malformed JSON from BMKG") from exc


def _rebase_payload(payload: dict, now: datetime) -> dict:
    """Shift a frozen feed so its first entry sits one hour before `now` (keeps the 3-day window valid)."""
    p = copy.deepcopy(payload)
    entries = [e for day in p["data"][0]["cuaca"] for e in day]
    first = datetime.strptime(entries[0]["utc_datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    target = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    delta = target - first
    for e in entries:
        for key in ("utc_datetime", "local_datetime"):
            if e.get(key):
                shifted = datetime.strptime(e[key], "%Y-%m-%d %H:%M:%S") + delta
                e[key] = shifted.strftime("%Y-%m-%d %H:%M:%S")
        if e.get("datetime"):
            e["datetime"] = (
                datetime.strptime(e["utc_datetime"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")
            )
    return p


class MockBMKGClient:
    """Offline client: serves the frozen *real* BMKG sample, re-dated to the current time."""

    def __init__(self, fixture_path: Path | str, clock: Callable[[], datetime] = utcnow):
        self.payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        self.clock = clock

    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict:
        p = _rebase_payload(self.payload, self.clock())
        p["lokasi"]["adm4"] = adm4
        return p


class StaticBMKGClient:
    """Serves a given payload verbatim (used by tests and measure.py synthetic feeds)."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict:
        self.calls += 1
        return copy.deepcopy(self.payload)


class FaultState:
    def __init__(self, mode: str = "none"):
        self.set(mode)

    def set(self, mode: str) -> None:
        if mode not in FAULT_MODES:
            raise ValueError(f"unknown fault mode {mode!r}")
        self._mode = mode
        self._expires_at = time.monotonic() + 600 if mode != "none" else None

    @property
    def mode(self) -> str:
        if self._expires_at is not None and time.monotonic() >= self._expires_at:
            return "none"
        return self._mode


def fault_transport(mode: str, healthy_payload: Callable[[], dict]) -> httpx.MockTransport:
    """An in-process 'BMKG' that misbehaves in one of the FAULT_MODES (BMKG itself is never contacted)."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if mode == "timeout":
            await asyncio.sleep(3600)  # hangs; the client's deadline must cut it off
        if mode == "http500":
            return httpx.Response(500, text="Internal Server Error (injected)")
        if mode == "malformed":
            return httpx.Response(200, text='{"lokasi": {"adm4": "', headers={"content-type": "application/json"})
        payload = healthy_payload()
        if mode == "missing_fields":
            for day in payload["data"][0]["cuaca"]:
                for e in day:
                    e.pop("t", None)
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


class FaultInjectingClient:
    """Wraps a client; when a fault is on, the request goes through the *real* HTTP client
    code against an in-process transport that misbehaves."""

    def __init__(self, base: BMKGClient, fault: FaultState, healthy_payload: Callable[[], dict]):
        self.base = base
        self.fault = fault
        self.healthy_payload = healthy_payload

    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict:
        mode = self.fault.mode
        if mode == "none":
            return await self.base.fetch(adm4, timeout_s)
        client = HttpBMKGClient(transport=fault_transport(mode, self.healthy_payload))
        return await client.fetch(adm4, timeout_s)


# ------------------------------------------------------------------- gateway
@dataclass
class _CacheEntry:
    slots: list[WeatherSlot]
    tz: str
    fetched_at: datetime
    fresh_until: datetime


@dataclass(frozen=True)
class Forecast:
    slots: list[WeatherSlot]
    source: WeatherSource
    fetched_at: datetime
    tz: str
    note: str


I2Logger = Callable[[str, int | None, float, str], None]  # (adm4, status, latency_ms, note)


def _classify(exc: BaseException) -> tuple[int | None, str]:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return None, "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code, f"http{exc.response.status_code}"
    if isinstance(exc, BMKGFormatError):
        return 200, f"format: {exc}"
    if isinstance(exc, httpx.HTTPError):
        return None, f"network: {type(exc).__name__}"
    return None, f"error: {type(exc).__name__}: {exc}"


class WeatherGateway:
    def __init__(
        self,
        client: BMKGClient,
        ttl_s: int = 10800,
        stale_max_s: int = 21600,
        timeout_s: float = 3.0,
        clock: Callable[[], datetime] = utcnow,
        on_call: I2Logger | None = None,
    ):
        self.client = client
        self.ttl = timedelta(seconds=ttl_s)
        self.stale_max = timedelta(seconds=stale_max_s)
        self.timeout_s = timeout_s
        self.clock = clock
        self.on_call = on_call
        self._cache: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # demo controls --------------------------------------------------------
    def expire(self) -> None:
        """Mark cached feeds as due for refresh but keep them as fallback (used when a fault is switched)."""
        now = self.clock()
        for e in self._cache.values():
            e.fresh_until = min(e.fresh_until, now)

    def clear(self) -> None:
        self._cache.clear()

    def cache_info(self) -> dict:
        return {k: {"fetched_at": v.fetched_at.isoformat(), "entries": len(v.slots)} for k, v in self._cache.items()}

    # core -----------------------------------------------------------------
    def _log(self, adm4: str, status: int | None, latency_ms: float, note: str) -> None:
        if self.on_call:
            try:
                self.on_call(adm4, status, latency_ms, note)
            except Exception:  # logging must never break the weather path
                pass

    async def forecast(self, adm4: str) -> Forecast:
        lock = self._locks.setdefault(adm4, asyncio.Lock())
        async with lock:  # one BMKG call per location even under concurrent requests
            now = self.clock()
            entry = self._cache.get(adm4)
            if entry and now < entry.fresh_until:
                return Forecast(entry.slots, WeatherSource.CACHED, entry.fetched_at, entry.tz, "cache hit")
            t0 = time.perf_counter()
            try:
                payload = await self.client.fetch(adm4, self.timeout_s)
                slots = parse_feed(payload, now=now)
            except Exception as exc:  # noqa: BLE001 - every failure walks the fault ladder
                status, note = _classify(exc)
                self._log(adm4, status, (time.perf_counter() - t0) * 1000, note)
                if entry and now - entry.fetched_at <= self.stale_max:
                    return Forecast(entry.slots, WeatherSource.CACHED, entry.fetched_at, entry.tz, f"fallback after {note}")
                raise WeatherUnavailable(note) from exc
            self._log(adm4, 200, (time.perf_counter() - t0) * 1000, f"ok, {len(slots)} entries")
            tz = feed_timezone(payload)
            self._cache[adm4] = _CacheEntry(slots, tz, now, now + self.ttl)
            return Forecast(slots, WeatherSource.LIVE, now, tz, "fetched")

    async def slot_for(self, adm4: str, when: datetime, manual: ManualWeather | None = None) -> WeatherSlot:
        """Forecast slot nearest to `when`. An explicit manual answer skips BMKG (source=MANUAL)."""
        if manual is not None:
            return WeatherSlot(
                at=when.astimezone(timezone.utc), temp_c=None, humidity=None, description="manual input",
                rain=manual.rain, hot=manual.hot, source=WeatherSource.MANUAL, fetched_at=None, note="user supplied",
            )
        fc = await self.forecast(adm4)
        when_utc = when.astimezone(timezone.utc)
        best = min(fc.slots, key=lambda s: (abs(s.at - when_utc), s.at))
        if abs(best.at - when_utc) > MAX_SLOT_GAP:
            raise WeatherUnavailable("no forecast entry near the requested time")
        return replace(best, source=fc.source, fetched_at=fc.fetched_at, note=fc.note)
