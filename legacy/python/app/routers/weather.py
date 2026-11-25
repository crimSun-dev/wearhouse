"""/outfits/recommend (I1 → I2 → rules → I3) and /weather (debug view)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from starlette.concurrency import run_in_threadpool

from .. import services
from ..deps import LOCAL_TZ, current_user, mark, now_utc, require_api_key
from ..rules import Context
from ..schemas import ADM4_PATTERN, RecommendIn
from ..weather import ManualWeather, WeatherSlot, WeatherUnavailable

router = APIRouter(tags=["weather"])
CREDIT = "Weather data: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id"


def weather_view(slot: WeatherSlot) -> dict:
    return {
        "source": slot.source.value,
        "fetched_at": slot.fetched_at.isoformat() if slot.fetched_at else None,
        "at": slot.at.isoformat(),
        "local_time": slot.at.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M WIB"),
        "rain": slot.rain,
        "hot": slot.hot,
        "t": slot.temp_c,
        "humidity": slot.humidity,
        "description": slot.description,
        "note": slot.note,
        "credit": CREDIT if slot.source.value != "MANUAL" else None,
    }


def _when(body: RecommendIn) -> datetime:
    when = body.when or now_utc()
    if when.tzinfo is None:  # naive → the location's local time (WIB for the demo locations)
        when = when.replace(tzinfo=LOCAL_TZ)
    return when


@router.post("/outfits/recommend", dependencies=[Depends(require_api_key)])
async def recommend(body: RecommendIn, request: Request, user=Depends(current_user)):
    st = request.app.state
    adm4 = body.adm4 or st.settings.default_adm4
    when = _when(body)
    manual = ManualWeather(body.manual_weather.rain, body.manual_weather.hot) if body.manual_weather else None
    try:
        slot = await st.gateway.slot_for(adm4, when, manual)
    except WeatherUnavailable as exc:
        mark(request, weather_source="MANUAL_REQUIRED", note=str(exc))
        return {
            "weather": {"source": "MANUAL_REQUIRED", "note": str(exc), "ask": ["rain", "hot"], "credit": CREDIT},
            "outfits": [],
            "message": "Weather unavailable. Answer two taps (Rainy/Dry, Hot/Normal) and resend with manual_weather.",
        }
    mark(request, weather_source=slot.source.value, note=slot.note or None)
    ctx = Context(rain=slot.rain, hot=slot.hot, occasion=body.occasion)
    today = when.astimezone(LOCAL_TZ).date()

    def work():
        with st.Session() as s:
            return services.recommend_and_record(s, user, ctx, today)

    recs, rows = await run_in_threadpool(work)
    outfits = [
        {
            "rank": i,
            "score": round(r.score, 4),
            "compat": round(r.compat, 4),
            "pref": round(r.pref, 4),
            "recency": round(r.recency, 4),
            "items": [services.garment_out(rows[g.id]) for g in r.outfit.items],
        }
        for i, r in enumerate(recs, 1)
    ]
    message = None
    if not outfits:
        message = ("No rain-ready outfit for this occasion; add rain footwear or a rain outer."
                   if ctx.rain else "No outfit satisfies this occasion's rules; add suitable garments.")
    return {"weather": weather_view(slot), "context": {"rain": ctx.rain, "hot": ctx.hot, "occasion": ctx.occasion},
            "outfits": outfits, "message": message}


@router.get("/weather")
async def weather(request: Request, adm4: str | None = Query(None, pattern=ADM4_PATTERN)):
    """Debug view of the validated forecast the gateway is using."""
    st = request.app.state
    adm4 = adm4 or st.settings.default_adm4
    try:
        fc = await st.gateway.forecast(adm4)
    except WeatherUnavailable as exc:
        mark(request, weather_source="MANUAL_REQUIRED", note=str(exc))
        return {"adm4": adm4, "source": "MANUAL_REQUIRED", "note": str(exc), "slots": [], "credit": CREDIT}
    mark(request, weather_source=fc.source.value)
    tz = ZoneInfo(fc.tz)
    return {
        "adm4": adm4,
        "source": fc.source.value,
        "fetched_at": fc.fetched_at.isoformat(),
        "note": fc.note,
        "timezone": fc.tz,
        "credit": CREDIT,
        "slots": [
            {"at": s.at.isoformat(), "local_time": s.at.astimezone(tz).strftime("%a %d %b %H:%M"), "t": s.temp_c,
             "humidity": s.humidity, "description": s.description, "rain": s.rain, "hot": s.hot}
            for s in fc.slots
        ],
    }
