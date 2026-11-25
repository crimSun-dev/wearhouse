"""Weather gateway service: fresh cache -> live BMKG fetch -> stale cache (<= 6 h) -> MANUAL_REQUIRED.

Uses the pinned pure contract (contract.py). A feed with any invalid entry is rejected as a whole. Nothing here
ever synthesises weather: no data means MANUAL_REQUIRED (or `unavailable` for a planner day).
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from ..platform.clock import Clock, utcnow
from ..platform.errors import FieldError, validation_failed
from .contract import (DEFAULT_TZ, MAX_AHEAD, BMKGFormatError, CachedFeed, Decision, FallbackPolicy, WeatherSource,
                       parse_feed)
from .ports import FetchError, ForecastFetcher, WeatherUoW

ADM4 = re.compile(r"^\d{2}\.\d{2}\.\d{2}\.\d{4}$")
LOCAL = ZoneInfo(DEFAULT_TZ)


def check_adm4(adm4: str, field: str = "query.adm4") -> str:
    if not isinstance(adm4, str) or not ADM4.fullmatch(adm4):
        raise validation_failed([FieldError(field, "invalid", "A BMKG adm4 code looks like 31.71.03.1001.")])
    return adm4


def local_today(now: datetime) -> date:
    return now.astimezone(LOCAL).date()


class WeatherService:
    def __init__(self, uow_factory: Callable[[], WeatherUoW], fetcher: ForecastFetcher, *, clock: Clock = utcnow,
                 policy: FallbackPolicy | None = None):
        self.uow_factory = uow_factory
        self.fetcher = fetcher  # replaceable (tests inject a fake; nothing in tests calls BMKG)
        self.clock = clock
        self.policy = policy or FallbackPolicy()

    def decide(self, adm4: str) -> tuple[Decision, datetime | None]:
        check_adm4(adm4)
        now = self.clock()
        with self.uow_factory() as uow:
            cached = uow.weather.get_cache(adm4)
        hit = self.policy.use_cache_without_fetch(cached, now)
        if hit is not None:
            return hit, cached.fetched_at
        try:
            slots = parse_feed(self.fetcher.fetch(adm4), now)
        except FetchError as exc:
            reason = exc.reason
        except BMKGFormatError as exc:
            reason = f"malformed feed: {exc}"
        else:
            decision, entry = self.policy.after_fetch_success(slots, now)
            with self.uow_factory() as uow:
                uow.weather.put_cache(adm4, entry)
                uow.commit()
            return decision, entry.fetched_at
        decision = self.policy.after_fetch_failure(cached, now, reason)
        return decision, (cached.fetched_at if decision.source is WeatherSource.CACHED else None)

    def forecast(self, adm4: str) -> dict:
        decision, fetched_at = self.decide(adm4)
        return self.view(adm4, decision, fetched_at)

    @staticmethod
    def view(adm4: str | None, decision: Decision, fetched_at: datetime | None) -> dict:
        return {"adm4": adm4, "source": decision.source.value, "note": decision.note,
                "fetched_at": fetched_at.isoformat() if fetched_at else None,
                "slots": [{"at": s.at.isoformat(), "local_date": s.at.astimezone(LOCAL).date().isoformat(),
                           "temp_c": s.temp_c, "humidity": s.humidity, "description": s.description,
                           "rain": s.rain, "hot": s.hot} for s in decision.slots]}

    # ------------------------------------------------------------------ per-user location
    def my_weather(self, user_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            adm4 = uow.weather.get_location(user_id)
        if adm4 is None:
            return {"adm4": None, "source": WeatherSource.MANUAL_REQUIRED.value, "note": "no_location",
                    "fetched_at": None, "slots": []}
        return self.forecast(adm4)

    def set_location(self, user_id: uuid.UUID, adm4: str) -> dict:
        check_adm4(adm4, "body.adm4")
        with self.uow_factory() as uow:
            uow.weather.set_location(user_id, adm4, self.clock())
            uow.commit()
        return {"adm4": adm4}

    def clear_location(self, user_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            uow.weather.clear_location(user_id)
            uow.commit()

    def day_summaries(self, user_id: uuid.UUID, dates: list[date]) -> dict[date, dict]:
        """Planner weather per local date: `forecast` (from real slots) / `beyond_forecast` / `unavailable`."""
        today = local_today(self.clock())
        horizon = today + MAX_AHEAD
        forecast = self.my_weather(user_id)
        by_day: dict[str, list] = {}
        for s in forecast["slots"]:
            by_day.setdefault(s["local_date"], []).append(s)
        out = {}
        for d in dates:
            slots = by_day.get(d.isoformat(), [])
            if d > horizon:
                out[d] = {"status": "beyond_forecast"}
            elif not slots:
                out[d] = {"status": "unavailable", "reason": forecast["note"] if forecast["source"] ==
                          WeatherSource.MANUAL_REQUIRED.value else "no_slots_for_date"}
            else:
                temps = [s["temp_c"] for s in slots]
                out[d] = {"status": "forecast", "source": forecast["source"], "fetched_at": forecast["fetched_at"],
                          "min_temp_c": min(temps), "max_temp_c": max(temps),
                          "rain": any(s["rain"] for s in slots), "hot": any(s["hot"] for s in slots),
                          "descriptions": sorted({s["description"] for s in slots})}
        return out


def feed_from_json(raw: dict) -> CachedFeed:  # adapter helper kept next to the contract types
    from .contract import WeatherSlot
    slots = tuple(WeatherSlot(at=datetime.fromisoformat(s["at"]), temp_c=s["temp_c"], humidity=s["humidity"],
                              description=s["description"], rain=s["rain"], hot=s["hot"]) for s in raw["slots"])
    return CachedFeed(slots, datetime.fromisoformat(raw["fetched_at"]), datetime.fromisoformat(raw["fresh_until"]))
