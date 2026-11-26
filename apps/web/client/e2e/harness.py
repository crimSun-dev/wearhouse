"""E2E harness (test-only): a disposable migrated v2 database, the real v2 API built by the TEST factory with a
Neon-shaped local EdDSA issuer, and a token endpoint for the pages' e2e AuthPort fake.

    apps/api/.venv/Scripts/python.exe e2e/harness.py     (needs WEARHOUSE_TEST_ADMIN_URL: a DISPOSABLE server)

The database is dropped on exit. Nothing here is reachable from a production build.
"""
from __future__ import annotations

import atexit
import os
import signal
import sys
from threading import Thread
from pathlib import Path

API_TESTS = Path(__file__).resolve().parents[3] / "api" / "tests"
sys.path.insert(0, str(API_TESTS))

import uvicorn  # noqa: E402
from fastapi import Query  # noqa: E402

import conftest as fx  # noqa: E402  (disposable DB + role helpers from the v2 test suite)
from wearhouse.testing import LocalIssuer, create_test_app  # noqa: E402

PORT = int(os.environ.get("E2E_API_PORT", "8199"))
ORIGIN = os.environ.get("E2E_PAGES_ORIGIN", "http://127.0.0.1:4174")


def main() -> None:
    db = fx.create_database()
    atexit.register(fx.drop_database, db.name)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    issuer = LocalIssuer.neon()
    from dataclasses import replace
    settings = replace(fx.make_settings(db, issuer), allowed_origins=(ORIGIN,))
    app = create_test_app(settings, issuer=issuer)

    def token(sub: str = Query(..., max_length=64)):
        return {"token": issuer.token(sub, profile={"name": f"Test {sub}"})}

    app.add_api_route("/__e2e/token", token, methods=["GET"], include_in_schema=False)

    def grant(sub: str = Query(..., max_length=64), role: str = Query(..., pattern="^(catalogue_editor|inventory_manager|moderator|admin)$")):
        app.state.services.identity.grant_role(issuer=issuer.issuer, subject=sub, role=role, granted_by="e2e")
        return {"granted": role}

    app.add_api_route("/__e2e/grant", grant, methods=["POST"], include_in_schema=False)
    print(f"e2e harness: database {db.name}, API on http://127.0.0.1:{PORT}", flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    if os.environ.get("E2E_MANAGED") == "1":
        def stop_on_parent_exit():
            sys.stdin.buffer.read()
            server.should_exit = True

        Thread(target=stop_on_parent_exit, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()

