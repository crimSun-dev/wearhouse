"""harden-wearhouse-services-api 1.1: layered edge rate limits (pool SYSTEM_DESIGN RULE-033 / TRAP-018)."""
from __future__ import annotations

import asyncio
import dataclasses

import pytest

from conftest import Api, make_settings
from wearhouse.platform.http import RateLimitMiddleware, SlidingWindow
from wearhouse.testing import create_test_app


def limited(clean_db, issuer, **limits):
    s = dataclasses.replace(make_settings(clean_db, issuer), **limits)
    return Api(create_test_app(s, issuer=issuer), issuer)


@pytest.mark.postgres
def test_write_flood_is_limited_per_caller(clean_db, issuer):
    api = limited(clean_db, issuer, rate_writes_per_min=3)
    codes = [api.client.post("/api/v2/me/wardrobe/items", headers=api.headers("flooder"),
                             json={"name": f"Tee {i}", "slot": "top"}).status_code for i in range(4)]
    assert codes[:3] == [201, 201, 201] and codes[3] == 429
    r = api.client.post("/api/v2/me/wardrobe/items", headers=api.headers("flooder"), json={"name": "x", "slot": "top"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and r.json()["code"] == "RATE_LIMITED"
    assert r.json()["request_id"]  # the standard error body, with a request id
    ok = api.client.post("/api/v2/me/wardrobe/items", headers=api.headers("calm"), json={"name": "y", "slot": "top"})
    assert ok.status_code == 201  # another caller is unaffected
    assert api.get("/api/v2/me/wardrobe/items", "flooder").status_code == 200  # reads are not write-limited


@pytest.mark.postgres
def test_ip_and_global_limits_with_health_exempt(clean_db, issuer):
    api = limited(clean_db, issuer, rate_ip_per_min=5)
    codes = [api.get("/api/v2/wardrobe/slots").status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    api2 = limited(clean_db, issuer, rate_global_per_min=2)
    assert [api2.get("/api/v2/wardrobe/slots").status_code for _ in range(3)] == [200, 200, 429]
    assert all(api2.get("/api/v2/health").status_code == 200 for _ in range(5))  # exempt


def test_edge_window_slides_and_never_reads_tokens():
    now = [100.0]
    calls = []

    async def app(scope, receive, send):
        calls.append(scope["path"])

    mw = RateLimitMiddleware(app, ip_per_min=1, global_per_min=0, clock=lambda: now[0])
    scope = {"type": "http", "method": "GET", "path": "/api/v2/catalogue/products", "client": ("1.2.3.4", 1),
             "headers": [(b"authorization", b"Bearer eyJhbGciOiJFZERTQSJ9.secret-token-text.sig")]}
    sent = []

    async def send(msg):
        sent.append(msg)

    async def receive():
        return {"type": "http.request"}

    asyncio.run(mw(scope, receive, send))
    asyncio.run(mw(scope, receive, send))
    assert len(calls) == 1 and sent[0]["status"] == 429
    assert list(mw.ip.hits) == ["ip:1.2.3.4"]  # keyed by client IP only; token text never stored
    now[0] += 61  # the window slides
    asyncio.run(mw(scope, receive, send))
    assert len(calls) == 2


@pytest.mark.postgres
def test_fresh_tokens_do_not_reset_the_write_limit(clean_db, issuer):
    api = limited(clean_db, issuer, rate_writes_per_min=2)
    import time
    tokens = {"Bearer " + issuer.token("same-user", now=time.time() - i) for i in range(3)}  # distinct iat
    assert len(tokens) == 3  # three distinct tokens for one user
    codes = [api.client.post("/api/v2/me/wardrobe/items", headers={"Authorization": t},
                             json={"name": "z", "slot": "top"}).status_code for t in tokens]
    assert codes == [201, 201, 429]


def test_sliding_window_retry_after():
    t = [0.0]
    w = SlidingWindow(2, 60, clock=lambda: t[0])
    assert w.hit("k") is None and w.hit("k") is None
    t[0] = 10
    assert w.hit("k") == pytest.approx(50)


def test_deployments_refuse_disabled_edge_limits():
    from wearhouse.bootstrap.config import ConfigError, Settings
    base = Settings(environment="production", database_url="postgresql://x@h/db", auth_adapter="oidc",
                    oidc_issuer="https://issuer.example", oidc_audience="https://issuer.example",
                    oidc_jwks_url="https://issuer.example/jwks", delivery_secret="s" * 44)
    with pytest.raises(ConfigError, match="Edge rate limits"):
        dataclasses.replace(base, rate_ip_per_min=0).validate()
