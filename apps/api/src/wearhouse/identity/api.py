from __future__ import annotations

import math

from fastapi import Request

from ..platform.errors import rate_limited
from .domain import Principal

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def current_principal(request: Request) -> Principal:
    """The only way a v2 route obtains its actor: the verified bearer token. (`GET /me` lives in accounts.)
    Mutating requests also pass the per-user write limit (harden-wearhouse-services-api), keyed by the VERIFIED
    user id: fresh tokens do not reset it and forged claims cannot spend someone else's quota."""
    principal = request.app.state.services.identity.authenticate(request.headers.get("authorization"))
    limiter = getattr(request.app.state, "write_limiter", None)
    if limiter is not None and request.method in MUTATING:
        retry = limiter.hit(str(principal.user_id))
        if retry is not None:
            counts = getattr(request.app.state, "rate_limited", None)
            if counts is not None:
                counts["writes"] = counts.get("writes", 0) + 1
            raise rate_limited(max(1, math.ceil(retry)), "Too many changes in a short time. Try again shortly.")
    return principal
