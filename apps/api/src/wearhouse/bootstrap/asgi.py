"""ASGI entrypoint: `uvicorn wearhouse.bootstrap.asgi:app --port 8100`. Configuration from WEARHOUSE_* only."""
from __future__ import annotations

from .app import create_app

app = create_app()
