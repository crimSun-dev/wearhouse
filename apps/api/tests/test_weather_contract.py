"""3.7 weather contract: BMKG validation and LIVE -> CACHED -> MANUAL fallback, no network.

Mirrors the legacy measurement contract M4 (24 contract violations rejected; the frozen real BMKG sample,
tests/fixtures/bmkg_real_sample.json, maps 100 %) without importing legacy code.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wearhouse.weather.contract import (BMKGFormatError, CachedFeed, FallbackPolicy, WeatherSource, parse_feed,
                                        validate_entry)

NOW = datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bmkg_real_sample.json"


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


GOOD = {"utc_datetime": _fmt(NOW), "local_datetime": _fmt(NOW + timedelta(hours=7)), "t": 30, "hu": 80,
        "weather_desc": "Berawan"}


def var(**changes):
    e = dict(GOOD)
    for k, v in changes.items():
        if v is ...:
            e.pop(k)
        else:
            e[k] = v
    return e


def later(h):
    return {"utc_datetime": _fmt(NOW + timedelta(hours=h)), "local_datetime": _fmt(NOW + timedelta(hours=h + 7))}


BAD = [var(t=...), var(hu=...), var(weather_desc=...), var(local_datetime=...), var(t=None), var(hu=None),
       var(weather_desc=None), var(t=14.9), var(t=0), var(t=-10), var(t=40.1), var(t=45), var(t=99), var(hu=-1),
       var(hu=100.1), var(hu=250), var(t="30"), var(hu="80"), var(t=True), var(**later(73)), var(**later(240)),
       var(**later(-48)), var(weather_desc="  "), var(utc_datetime="tomorrow")]


def test_twenty_four_contract_violations_rejected():
    assert len(BAD) == 24
    for e in BAD:
        with pytest.raises(BMKGFormatError):
            validate_entry(e, now=NOW)


def test_good_entry_maps_rain_and_heat():
    s = validate_entry(var(t=33, weather_desc="Hujan Ringan"), now=NOW)
    assert (s.rain, s.hot, s.temp_c, s.humidity, s.at) == (True, True, 33.0, 80, NOW)


def test_frozen_real_bmkg_sample_maps_completely():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    entries = [e for day in payload["data"][0]["cuaca"] for e in day]
    real_now = datetime.fromisoformat(entries[0]["analysis_date"]).replace(tzinfo=timezone.utc)
    slots = parse_feed(payload, now=real_now)
    assert len(slots) == len(entries)
    for e in entries:
        s = validate_entry(e, now=real_now)
        assert s.rain == ("hujan" in e["weather_desc"].lower()) and s.hot == (e["t"] >= 32)


def test_one_bad_entry_rejects_whole_feed():
    feed = {"lokasi": {"timezone": "Asia/Jakarta"}, "data": [{"cuaca": [[GOOD, var(t=99)]]}]}
    with pytest.raises(BMKGFormatError):
        parse_feed(feed, now=NOW)


def test_fallback_ladder():
    policy = FallbackPolicy(ttl=timedelta(hours=3), stale_max=timedelta(hours=6))
    decision, cached = policy.after_fetch_success([validate_entry(GOOD, now=NOW)], NOW)
    assert decision.source is WeatherSource.LIVE
    assert policy.use_cache_without_fetch(cached, NOW + timedelta(hours=1)).source is WeatherSource.CACHED
    assert policy.use_cache_without_fetch(cached, NOW + timedelta(hours=4)) is None  # due for refresh
    fb = policy.after_fetch_failure(cached, NOW + timedelta(hours=5), "timeout")
    assert fb.source is WeatherSource.CACHED and fb.note == "fallback after timeout"
    assert policy.after_fetch_failure(cached, NOW + timedelta(hours=7), "http500").source is WeatherSource.MANUAL_REQUIRED
    assert policy.after_fetch_failure(None, NOW, "malformed").source is WeatherSource.MANUAL_REQUIRED
    assert isinstance(cached, CachedFeed)
