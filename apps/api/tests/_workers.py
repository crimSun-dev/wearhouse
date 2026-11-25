"""Separate-process workers for multi-process race/limit tests (spawned; no shared memory with the parent)."""
from __future__ import annotations

import time
import warnings


def claim_in_process(args: dict) -> tuple[int, str | None]:
    warnings.filterwarnings("ignore")
    from fastapi.testclient import TestClient

    from wearhouse.bootstrap.config import Settings
    from wearhouse.identity.adapters.oidc import OidcTokenVerifier, StaticJwks
    from wearhouse.testing import create_test_app

    s = args["settings"]
    settings = Settings(**s)
    verifier = OidcTokenVerifier(issuer=s["oidc_issuer"], audience=s["oidc_audience"], keys=StaticJwks(args["jwks"]))
    client = TestClient(create_test_app(settings, verifier=verifier), raise_server_exceptions=False)
    client.get("/api/v2/health")  # warm up before the synchronized start
    while time.time() < args["start_at"]:
        time.sleep(0.001)
    r = client.post("/api/v2/redemptions", json={"activation_key": args["key"]},
                    headers={"Authorization": "Bearer " + args["token"], "Idempotency-Key": args["idem"]})
    return r.status_code, r.json().get("code")


def friend_request_in_process(args: dict) -> int:
    warnings.filterwarnings("ignore")
    from fastapi.testclient import TestClient

    from wearhouse.bootstrap.config import Settings
    from wearhouse.identity.adapters.oidc import OidcTokenVerifier, StaticJwks
    from wearhouse.testing import create_test_app

    s = args["settings"]
    verifier = OidcTokenVerifier(issuer=s["oidc_issuer"], audience=s["oidc_audience"], keys=StaticJwks(args["jwks"]))
    client = TestClient(create_test_app(Settings(**s), verifier=verifier), raise_server_exceptions=False)
    client.get("/api/v2/health")
    while time.time() < args["start_at"]:
        time.sleep(0.001)
    r = client.post("/api/v2/me/friend-requests", json={"handle": args["handle"]},
                    headers={"Authorization": "Bearer " + args["token"], "Idempotency-Key": args["idem"]})
    return r.status_code
