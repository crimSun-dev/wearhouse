"""GET /admin/ops (complete-wearhouse-tdd, TDD §14 observability): counts only, never identifiers or secrets."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from ..catalogue.adapters.tables import catalogue_import_job
from ..identity.api import current_principal
from ..identity.domain import Capability, Principal, require
from ..ownership.adapters.tables import ownership_event
from ..platform.clock import utcnow
from ..platform.tables import attempt_event, outbox_event
from ..recommendations.adapters.tables import recommendation_artifact
from .schema import SCHEMA_HEAD


class OpsOut(BaseModel):
    window_hours: int
    claim_attempts: int
    claims_succeeded: int
    claim_failures: int
    rate_limited_since_start: dict[str, int]
    import_jobs_running: int
    outbox_pending: int
    outbox_failing: int
    active_artifact: str | None
    model_mode: str
    schema_head: str


router = APIRouter(tags=["admin: operations"])


@router.get("/admin/ops", response_model=OpsOut, summary="Operational counts (admin): claims, limits, backlogs, model")
def ops(request: Request, principal: Principal = Depends(current_principal)):
    require(principal, Capability.VIEW_OPS)
    since = utcnow() - timedelta(hours=24)
    engine = request.app.state.engine
    with engine.connect() as c:
        attempts = c.execute(select(func.count()).select_from(attempt_event)
                             .where(attempt_event.c.scope == "actor", attempt_event.c.reserved_at >= since)).scalar_one()
        claimed = c.execute(select(func.count()).select_from(ownership_event)
                            .where(ownership_event.c.event_type == "claimed",
                                   ownership_event.c.created_at >= since)).scalar_one()
        running = c.execute(select(func.count()).select_from(catalogue_import_job)
                            .where(catalogue_import_job.c.status == "running")).scalar_one()
        pending = c.execute(select(func.count()).select_from(outbox_event)
                            .where(outbox_event.c.dispatched_at.is_(None))).scalar_one()
        failing = c.execute(select(func.count()).select_from(outbox_event)
                            .where(outbox_event.c.dispatched_at.is_(None), outbox_event.c.last_error.is_not(None))).scalar_one()
        art = c.execute(select(recommendation_artifact.c.name, recommendation_artifact.c.version,
                               recommendation_artifact.c.mode)
                        .where(recommendation_artifact.c.active.is_(True))).first()
    return {"window_hours": 24, "claim_attempts": attempts, "claims_succeeded": claimed,
            "claim_failures": max(attempts - claimed, 0),
            "rate_limited_since_start": dict(getattr(request.app.state, "rate_limited", {})),
            "import_jobs_running": running, "outbox_pending": pending, "outbox_failing": failing,
            "active_artifact": f"{art.name}@{art.version}" if art else None,
            "model_mode": art.mode if art else "heuristic_baseline", "schema_head": SCHEMA_HEAD}
