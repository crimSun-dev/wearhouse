"""Phase 3 — Weather Gateway (I2). BMKG HTTP is mocked with respx; no network."""
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.weather import (
    BMKG_URL,
    BMKGFormatError,
    HttpBMKGClient,
    ManualWeather,
    WeatherGateway,
    WeatherSource,
    WeatherUnavailable,
    parse_feed,
    validate_entry,
)
from tests.conftest import Clock

NOW = datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc)
ADM4 = "31.71.03.1001"


def entry(hours_from_now=0, t=30, hu=80, desc="Cerah Berawan", now=NOW):
    at = now + timedelta(hours=hours_from_now)
    local = at + timedelta(hours=7)
    return {"utc_datetime": at.strftime("%Y-%m-%d %H:%M:%S"), "local_datetime": local.strftime("%Y-%m-%d %H:%M:%S"),
            "t": t, "hu": hu, "weather_desc": desc}


def payload(entries, now=NOW):
    return {"lokasi": {"adm4": ADM4, "timezone": "Asia/Jakarta"}, "data": [{"cuaca": [entries]}]}


def good_feed(now=NOW):
    return payload([entry(h, desc="Hujan Ringan" if h == 2 else "Berawan", now=now) for h in range(-1, 24, 3)], now)


def gateway(clock, **kw):
    return WeatherGateway(HttpBMKGClient(), clock=clock, **kw)


# 1
def test_valid_bmkg_payload_maps_hujan_to_rain_true():
    for desc, rain in [("Hujan Ringan", True), ("Hujan Petir", True), ("hujan sedang", True), ("Berawan", False),
                       ("Cerah", False)]:
        assert validate_entry(entry(desc=desc), now=NOW).rain is rain


# 2
def test_temp_32_is_hot_31_9_is_not():
    assert validate_entry(entry(t=32), now=NOW).hot is True
    assert validate_entry(entry(t=31.9), now=NOW).hot is False


# 3
@pytest.mark.parametrize("field", ["t", "hu", "weather_desc", "local_datetime"])
def test_missing_field_entry_rejected_with_BMKGFormatError(field):
    raw = entry()
    del raw[field]
    with pytest.raises(BMKGFormatError):
        validate_entry(raw, now=NOW)


def test_non_numeric_temperature_rejected():
    with pytest.raises(BMKGFormatError):
        validate_entry(entry(t="30"), now=NOW)


# 4
@pytest.mark.parametrize("t", [14.9, 40.1, -5])
def test_temp_out_of_15_40_rejected(t):
    with pytest.raises(BMKGFormatError):
        validate_entry(entry(t=t), now=NOW)


@pytest.mark.parametrize("hu", [-1, 100.5, 150])
def test_humidity_out_of_0_100_rejected(hu):
    with pytest.raises(BMKGFormatError):
        validate_entry(entry(hu=hu), now=NOW)


# 5
def test_entries_beyond_3_days_rejected():
    assert validate_entry(entry(hours_from_now=71), now=NOW)
    with pytest.raises(BMKGFormatError):
        validate_entry(entry(hours_from_now=73), now=NOW)
    with pytest.raises(BMKGFormatError):
        validate_entry(entry(hours_from_now=-30), now=NOW)


def test_one_bad_entry_rejects_whole_feed():
    feed = good_feed()
    feed["data"][0]["cuaca"][0][4]["hu"] = 101
    with pytest.raises(BMKGFormatError):
        parse_feed(feed, now=NOW)


# 6
@respx.mock
async def test_second_call_within_3h_served_from_cache_without_http():
    route = respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=good_feed()))
    clock = Clock(NOW)
    gw = gateway(clock)
    first = await gw.slot_for(ADM4, NOW + timedelta(hours=3))
    assert first.source is WeatherSource.LIVE and first.rain is True
    clock.advance(hours=2, minutes=59)
    second = await gw.slot_for(ADM4, NOW + timedelta(hours=3))
    assert second.source is WeatherSource.CACHED
    assert second.fetched_at == first.fetched_at == NOW
    assert route.call_count == 1
    clock.advance(minutes=2)  # now 3 h 01 m old → refetch
    await gw.slot_for(ADM4, NOW + timedelta(hours=3))
    assert route.call_count == 2


async def _warm_then_fail(side_effect, clock):
    route = respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=good_feed()))
    gw = gateway(clock)
    await gw.slot_for(ADM4, NOW)
    clock.advance(hours=4)  # cache is stale (> 3 h) but still usable as fallback (≤ 6 h)
    if isinstance(side_effect, httpx.Response):
        route.mock(return_value=side_effect)
    else:
        route.mock(side_effect=side_effect)
    slot = await gw.slot_for(ADM4, NOW + timedelta(hours=5))
    return slot, route


# 7
@respx.mock
async def test_timeout_after_3s_falls_back_to_cache_source_CACHED():
    slot, route = await _warm_then_fail(httpx.ReadTimeout("simulated"), Clock(NOW))
    assert slot.source is WeatherSource.CACHED
    assert "timeout" in slot.note
    assert route.call_count == 2
    assert route.calls[-1].request.extensions["timeout"]["read"] == 3.0  # the 3 s budget is what httpx is given


async def test_hanging_bmkg_is_cut_off_by_the_total_deadline():
    async def hang(request):
        import asyncio

        await asyncio.sleep(60)

    gw = WeatherGateway(HttpBMKGClient(transport=httpx.MockTransport(hang)), timeout_s=0.3, clock=Clock(NOW))
    t0 = time.perf_counter()
    with pytest.raises(WeatherUnavailable, match="timeout"):
        await gw.slot_for(ADM4, NOW)
    assert time.perf_counter() - t0 < 1.0


# 8
@respx.mock
async def test_http_500_falls_back_to_cache():
    slot, _ = await _warm_then_fail(httpx.Response(500), Clock(NOW))
    assert slot.source is WeatherSource.CACHED and "http500" in slot.note


# 9
@respx.mock
async def test_malformed_json_falls_back_to_cache():
    slot, _ = await _warm_then_fail(httpx.Response(200, text="{not json"), Clock(NOW))
    assert slot.source is WeatherSource.CACHED and "format" in slot.note


@respx.mock
async def test_missing_fields_feed_falls_back_to_cache():
    broken = good_feed()
    for e in broken["data"][0]["cuaca"][0]:
        e.pop("t")
    slot, _ = await _warm_then_fail(httpx.Response(200, json=broken), Clock(NOW))
    assert slot.source is WeatherSource.CACHED and "missing fields" in slot.note


# 10
@respx.mock
async def test_cache_older_than_6h_not_used():
    route = respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=good_feed()))
    clock = Clock(NOW)
    gw = gateway(clock)
    await gw.slot_for(ADM4, NOW)
    clock.advance(hours=6, minutes=1)
    route.mock(return_value=httpx.Response(500))
    with pytest.raises(WeatherUnavailable):
        await gw.slot_for(ADM4, NOW + timedelta(hours=6))
    # the caller then asks the user: MANUAL
    manual = await gw.slot_for(ADM4, NOW, manual=ManualWeather(rain=True, hot=False))
    assert manual.source is WeatherSource.MANUAL and manual.rain is True


@respx.mock
async def test_manual_answer_skips_bmkg_entirely():
    route = respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=good_feed()))
    gw = gateway(Clock(NOW))
    slot = await gw.slot_for(ADM4, NOW, manual=ManualWeather(rain=False, hot=True))
    assert slot.source is WeatherSource.MANUAL and slot.hot is True and route.call_count == 0


@respx.mock
async def test_slot_choice_across_midnight_uses_utc_and_local_zone():
    """01:30 WIB on the 25th is 18:30 UTC on the 24th → nearest entry is 19:00 UTC (02:00 WIB on the 25th)."""
    import json
    from pathlib import Path

    real = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "bmkg_real_sample.json").read_text("utf-8"))
    respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=real))
    now = datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc)
    gw = gateway(Clock(now))
    from zoneinfo import ZoneInfo

    when = datetime(2026, 11, 25, 1, 30, tzinfo=ZoneInfo("Asia/Jakarta"))
    slot = await gw.slot_for(ADM4, when)
    assert slot.at == datetime(2026, 11, 24, 19, 0, tzinfo=timezone.utc)
    assert slot.at.astimezone(ZoneInfo("Asia/Jakarta")).date().isoformat() == "2026-11-25"
    assert slot.rain is True  # "Hujan Ringan" at 02:00 WIB in the frozen real sample


@respx.mock
async def test_request_far_outside_forecast_is_unavailable():
    respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=good_feed()))
    gw = gateway(Clock(NOW))
    with pytest.raises(WeatherUnavailable):
        await gw.slot_for(ADM4, NOW + timedelta(days=5))


@respx.mock
async def test_every_bmkg_attempt_is_reported_for_the_I2_log():
    calls = []
    route = respx.get(BMKG_URL).mock(return_value=httpx.Response(200, json=good_feed()))
    clock = Clock(NOW)
    gw = WeatherGateway(HttpBMKGClient(), clock=clock, on_call=lambda *a: calls.append(a))
    await gw.slot_for(ADM4, NOW)
    await gw.slot_for(ADM4, NOW)  # cache hit: no I2 call, no log
    clock.advance(hours=4)
    route.mock(return_value=httpx.Response(500))
    await gw.slot_for(ADM4, NOW + timedelta(hours=4))
    assert [(c[0], c[1]) for c in calls] == [(ADM4, 200), (ADM4, 500)]
    assert calls[1][3] == "http500"
