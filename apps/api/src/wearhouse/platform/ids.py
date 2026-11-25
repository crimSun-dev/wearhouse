from __future__ import annotations

import uuid


def new_id() -> uuid.UUID:
    return uuid.uuid4()


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None
