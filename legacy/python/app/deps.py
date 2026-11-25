"""FastAPI dependencies: DB session, API-key guard, current (synthetic) user."""
from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timezone
from typing import Iterator
from zoneinfo import ZoneInfo

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

from .seed_data import DEMO_USER_ID

LOCAL_TZ = ZoneInfo("Asia/Jakarta")


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.Session() as s:
        yield s


def require_api_key(request: Request, x_api_key: str | None = Header(None)) -> None:
    """Static demo key guarding every write (TDD assumption 3: one synthetic user, no real login)."""
    expected = request.app.state.settings.api_key
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="missing or wrong X-API-Key")


def current_user() -> uuid.UUID:
    return DEMO_USER_ID


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def local_today() -> date:
    return datetime.now(LOCAL_TZ).date()


def mark(request: Request, **fields) -> None:
    """Attach extra columns (weather_source, note) to this request's interface_log row."""
    request.scope.setdefault("dw_log", {}).update(fields)
