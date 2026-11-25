"""/health, /wardrobe, /garments, /outfits (save/plan/wear), /avatar."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from .. import services
from ..db import backend_name
from ..deps import current_user, get_session, local_today, require_api_key
from ..models import AppUser
from ..schemas import GarmentIn, GarmentOut, OutfitIn, OutfitOut, WearIn

router = APIRouter()


@router.get("/health", tags=["system"])
def health(request: Request):
    st = request.app.state
    return {
        "status": "ok",
        "db": backend_name(st.settings.database_url),
        "weather_mode": st.settings.weather_mode,
        "fault": st.fault.mode,
        "weather_cache": st.gateway.cache_info(),
    }


@router.get("/wardrobe", response_model=list[GarmentOut], tags=["wardrobe"])
def wardrobe(s: Session = Depends(get_session), user=Depends(current_user)):
    return [services.garment_out(g) for g in services.list_wardrobe(s, user)]


@router.post("/garments", status_code=201, response_model=GarmentOut, tags=["wardrobe"],
             dependencies=[Depends(require_api_key)])
def add_garment(body: GarmentIn, s: Session = Depends(get_session), user=Depends(current_user)):
    """Manual add (e.g. a thrifted item without a tag)."""
    return services.garment_out(services.add_garment(s, user, body))


@router.delete("/garments/{garment_id}", status_code=204, tags=["wardrobe"], dependencies=[Depends(require_api_key)])
def delete_garment(garment_id: uuid.UUID, s: Session = Depends(get_session), user=Depends(current_user)):
    """409 if a saved outfit uses the garment (blocked, not cascaded)."""
    services.delete_garment(s, user, garment_id)
    return Response(status_code=204)


@router.post("/outfits", status_code=201, response_model=OutfitOut, tags=["outfits"],
             dependencies=[Depends(require_api_key)])
def create_outfit(body: OutfitIn, s: Session = Depends(get_session), user=Depends(current_user)):
    """Save / plan an outfit. 409 on a slot clash, 422 on unknown garments."""
    return services.outfit_out(s, services.create_outfit(s, user, body))


@router.get("/outfits", response_model=list[OutfitOut], tags=["outfits"])
def list_outfits(week: str | None = Query(None, description="ISO week, e.g. 2026-W48 (calendar strip)"),
                 s: Session = Depends(get_session), user=Depends(current_user)):
    return [services.outfit_out(s, o) for o in services.list_outfits(s, user, week)]


@router.delete("/outfits/{outfit_id}", status_code=204, tags=["outfits"], dependencies=[Depends(require_api_key)])
def delete_outfit(outfit_id: uuid.UUID, s: Session = Depends(get_session), user=Depends(current_user)):
    services.delete_outfit(s, user, outfit_id)
    return Response(status_code=204)


@router.post("/outfits/{outfit_id}/wear", status_code=204, tags=["outfits"], dependencies=[Depends(require_api_key)])
def wear(outfit_id: uuid.UUID, body: WearIn | None = None, s: Session = Depends(get_session),
         user=Depends(current_user)):
    """Writes wear_log, sets last_worn_at and increments times_chosen for each item."""
    worn_on = (body.worn_on if body else None) or local_today()
    services.wear_outfit(s, user, outfit_id, worn_on)
    return Response(status_code=204)


@router.get("/avatar/{outfit_id}", tags=["outfits"])
def avatar(outfit_id: uuid.UUID, s: Session = Depends(get_session), user=Depends(current_user)):
    """Slot → template/texture/tint description that the Three.js avatar (Phase 7) consumes."""
    u = s.get(AppUser, user)
    return services.avatar_for(s, user, outfit_id, u.gender if u else None)
