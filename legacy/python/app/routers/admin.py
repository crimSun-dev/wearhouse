"""Demo controls (API key required) and the interface log (Ch 15 raw data)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import registration
from ..deps import get_session, now_utc, require_api_key
from ..models import InterfaceLog, Product, as_utc
from ..schemas import FaultIn, IssueCodesIn
from ..seeding import reset_demo

router = APIRouter(tags=["admin"])
admin = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_api_key)])


@admin.post("/fault")
def set_fault(body: FaultIn, request: Request):
    """I6 fault switch. Switching marks cached forecasts as due so the next request really hits the fault
    (the cached copy stays available as the CACHED fallback)."""
    st = request.app.state
    st.fault.set(body.mode)
    st.gateway.expire()
    return {"fault": st.fault.mode}


@admin.post("/weather/clear-cache")
def clear_cache(request: Request):
    """Forget every cached forecast (to demo a cold failure → MANUAL_REQUIRED)."""
    request.app.state.gateway.clear()
    return {"cleared": True}


@admin.post("/codes", status_code=201)
def issue_codes(body: IssueCodesIn, s: Session = Depends(get_session)):
    """Retailer side: mint tag serials + activation codes. Codes are shown ONCE (only hashes are stored)."""
    try:
        return registration.issue_codes(s, body.gtin, body.count)
    except LookupError:
        raise HTTPException(status_code=404, detail="unknown gtin")


@admin.get("/products")
def products(s: Session = Depends(get_session)):
    return [{"gtin": p.gtin, "name": p.name, "slot": p.slot} for p in s.scalars(select(Product)).all()]


@admin.post("/reset")
def reset(request: Request, s: Session = Depends(get_session)):
    """Fresh demo run: wipe outfits/wear/registrations/logs and re-seed the 28 garments."""
    reset_demo(s)
    request.app.state.gateway.clear()
    request.app.state.fault.set("none")
    return {"reset": True}


def _row(r: InterfaceLog) -> dict:
    return {"id": r.id, "at": as_utc(r.at).isoformat(), "interface": r.interface, "route": r.route,
            "status": r.status, "latency_ms": None if r.latency_ms is None else round(r.latency_ms, 2),
            "weather_source": r.weather_source, "note": r.note}


@router.get("/metrics/interface-log", tags=["metrics"])
def interface_log(limit: int = Query(50, ge=1, le=500), interface: str | None = Query(None, pattern=r"^I[1-6]$"),
                  s: Session = Depends(get_session)):
    """Newest first. This endpoint itself is not logged (the demo page polls it)."""
    q = select(InterfaceLog)
    if interface:
        q = q.where(InterfaceLog.interface == interface)
    return [_row(r) for r in s.scalars(q.order_by(InterfaceLog.id.desc()).limit(limit)).all()]


@router.get("/metrics/summary", tags=["metrics"])
def summary(s: Session = Depends(get_session)):
    """Row counts per interface plus BMKG (I2) calls in the last 24 h (budget: ≤ 8/day/location)."""
    per_iface = dict(s.execute(select(InterfaceLog.interface, func.count()).group_by(InterfaceLog.interface)).all())
    since = now_utc() - timedelta(hours=24)
    i2_24h = s.scalar(select(func.count()).select_from(InterfaceLog)
                      .where(InterfaceLog.interface == "I2", InterfaceLog.at >= since)) or 0
    return {"rows_per_interface": per_iface, "bmkg_calls_last_24h": i2_24h}


router.include_router(admin)
