"""3.1 package/app-factory smoke tests (no database needed)."""
from __future__ import annotations

import importlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

import wearhouse
from wearhouse.bootstrap.app import API_PREFIX, build_app
from wearhouse.bootstrap.cli import offline_settings
from wearhouse.bootstrap.config import DEFAULT_PORT

REPO = Path(__file__).resolve().parents[3]


def test_package_imports_from_src_layout():
    assert Path(wearhouse.__file__).parts[-3:] == ("src", "wearhouse", "__init__.py")
    for mod in ("wearhouse.bootstrap.app", "wearhouse.identity.application", "wearhouse.catalogue.application",
                "wearhouse.ownership.application", "wearhouse.recommendations.baseline", "wearhouse.weather.contract"):
        importlib.import_module(mod)


def test_app_factory_builds_without_database_and_serves_health():
    app = build_app(offline_settings())
    with TestClient(app) as c:
        r = c.get(f"{API_PREFIX}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "wearhouse-api", "version": wearhouse.__version__}
    assert "x-request-id" in r.headers


def test_readiness_without_engine_is_not_ready():
    with TestClient(build_app(offline_settings())) as c:
        assert c.get(f"{API_PREFIX}/health/ready").status_code == 503


def test_v2_uses_port_8100_distinct_from_legacy_8000():
    assert DEFAULT_PORT == 8100
    dev = (REPO / "tools" / "dev_api.ps1").read_text(encoding="utf-8")
    legacy = (REPO / "run_demo.ps1").read_text(encoding="utf-8")
    assert re.search(r"\[int\]\$Port = 8100", dev)
    assert re.search(r"\[int\]\$Port = 8000", legacy)


def test_only_foundation_routes_are_exposed():
    spec = build_app(offline_settings()).openapi()
    paths = {(m.upper(), p) for p, ops in spec["paths"].items() for m in ops}
    assert paths == {
        ("GET", "/api/v2/health"), ("GET", "/api/v2/health/ready"), ("GET", "/api/v2/me"),
        ("POST", "/api/v2/admin/source-products"), ("POST", "/api/v2/admin/unit-batches"),
        ("POST", "/api/v2/admin/units/{unit_id}/reissue"), ("GET", "/api/v2/items/{serial}"),
        ("POST", "/api/v2/redemptions"), ("GET", "/api/v2/me/items"), ("GET", "/api/v2/me/items/{item_id}"),
        # add-wearhouse-accounts
        ("GET", "/api/v2/me/profile"), ("PATCH", "/api/v2/me/profile"), ("GET", "/api/v2/me/privacy"),
        ("PUT", "/api/v2/me/privacy"), ("POST", "/api/v2/me/sessions/revoke-all"), ("GET", "/api/v2/me/export"),
        ("DELETE", "/api/v2/me"), ("GET", "/api/v2/users/search"), ("POST", "/api/v2/me/friend-requests"),
        ("GET", "/api/v2/me/friend-requests"), ("POST", "/api/v2/me/friend-requests/{request_id}/accept"),
        ("POST", "/api/v2/me/friend-requests/{request_id}/decline"),
        ("DELETE", "/api/v2/me/friend-requests/{request_id}"), ("GET", "/api/v2/me/friends"),
        ("DELETE", "/api/v2/me/friends/{handle}"), ("GET", "/api/v2/me/blocks"), ("PUT", "/api/v2/me/blocks/{handle}"),
        ("DELETE", "/api/v2/me/blocks/{handle}"), ("GET", "/api/v2/profiles/{handle}"),
        ("GET", "/api/v2/profiles/{handle}/wardrobe"), ("GET", "/api/v2/profiles/{handle}/friends"),
        # publish-wearhouse-catalogue
        ("POST", "/api/v2/admin/catalogue/import-jobs"), ("GET", "/api/v2/admin/catalogue/import-jobs/{job_id}"),
        ("GET", "/api/v2/admin/catalogue/review"), ("GET", "/api/v2/admin/catalogue/products/{product_id}"),
        ("POST", "/api/v2/admin/catalogue/products/{product_id}/publish"),
        ("POST", "/api/v2/admin/catalogue/products/{product_id}/retire"),
        ("GET", "/api/v2/admin/catalogue/collections"), ("PUT", "/api/v2/admin/catalogue/collections/{slug}"),
        ("DELETE", "/api/v2/admin/catalogue/collections/{slug}"), ("GET", "/api/v2/catalogue/products"),
        ("GET", "/api/v2/catalogue/products/{product_id}"), ("GET", "/api/v2/catalogue/facets"),
        ("GET", "/api/v2/catalogue/collections"), ("GET", "/api/v2/catalogue/collections/{slug}"),
        # add-wearhouse-sandbox-commerce
        ("GET", "/api/v2/admin/commerce/offers"), ("PUT", "/api/v2/admin/commerce/offers/{product_id}"),
        ("DELETE", "/api/v2/admin/commerce/offers/{product_id}"), ("GET", "/api/v2/commerce/products/{product_id}/offer"),
        ("GET", "/api/v2/me/wishlist"), ("PUT", "/api/v2/me/wishlist/{product_id}"),
        ("DELETE", "/api/v2/me/wishlist/{product_id}"), ("GET", "/api/v2/me/cart"), ("PUT", "/api/v2/me/cart/{product_id}"),
        ("DELETE", "/api/v2/me/cart/{product_id}"), ("POST", "/api/v2/me/checkout"), ("GET", "/api/v2/me/orders"),
        ("GET", "/api/v2/me/orders/{order_id}"), ("GET", "/api/v2/me/orders/{order_id}/units/{unit_id}/key"),
        ("POST", "/api/v2/me/orders/{order_id}/units/{unit_id}/renew-key"), ("POST", "/api/v2/me/orders/{order_id}/cancel"),
        # build-wearhouse-wardrobe-planning-services
        ("GET", "/api/v2/wardrobe/slots"), ("GET", "/api/v2/me/wardrobe/items"), ("POST", "/api/v2/me/wardrobe/items"),
        ("GET", "/api/v2/me/wardrobe/items/{item_id}"), ("PATCH", "/api/v2/me/wardrobe/items/{item_id}"),
        ("PUT", "/api/v2/me/wardrobe/items/{item_id}/photo"), ("GET", "/api/v2/me/wardrobe/items/{item_id}/photo"),
        ("GET", "/api/v2/me/wardrobe/shelves"), ("POST", "/api/v2/me/wardrobe/shelves"),
        ("PATCH", "/api/v2/me/wardrobe/shelves/{shelf_id}"), ("DELETE", "/api/v2/me/wardrobe/shelves/{shelf_id}"),
        ("GET", "/api/v2/me/looks"), ("POST", "/api/v2/me/looks"), ("GET", "/api/v2/me/looks/{look_id}"),
        ("PATCH", "/api/v2/me/looks/{look_id}"), ("DELETE", "/api/v2/me/looks/{look_id}"),
        ("GET", "/api/v2/me/look-revisions/{revision_id}"), ("GET", "/api/v2/me/planner"),
        ("PUT", "/api/v2/me/planner/{plan_date}"), ("DELETE", "/api/v2/me/planner/{plan_date}"),
        ("POST", "/api/v2/me/wear"), ("GET", "/api/v2/me/wear"), ("DELETE", "/api/v2/me/wear/{wear_id}"),
        ("GET", "/api/v2/me/recommendations/outfits"), ("GET", "/api/v2/weather/forecast"), ("GET", "/api/v2/me/weather"),
        ("PUT", "/api/v2/me/weather/location"), ("DELETE", "/api/v2/me/weather/location"),
        # add-wearhouse-social-profile-services
        ("GET", "/api/v2/me/shares"), ("POST", "/api/v2/me/shares"), ("PATCH", "/api/v2/me/shares/{share_id}"),
        ("DELETE", "/api/v2/me/shares/{share_id}"), ("GET", "/api/v2/me/feed"), ("GET", "/api/v2/me/plan-sharing"),
        ("PUT", "/api/v2/me/plan-sharing"), ("GET", "/api/v2/me/notifications"),
        ("GET", "/api/v2/me/notifications/unread-count"), ("POST", "/api/v2/me/notifications/read"),
        ("GET", "/api/v2/me/showcase"), ("PUT", "/api/v2/me/showcase"), ("GET", "/api/v2/shares/{share_id}"),
        ("GET", "/api/v2/profiles/{handle}/shares"), ("GET", "/api/v2/profiles/{handle}/week"),
        ("GET", "/api/v2/profiles/{handle}/showcase"),
        # add-wearhouse-object-management
        ("GET", "/api/v2/admin/catalogue/products/{product_id}/media"),
        ("POST", "/api/v2/admin/catalogue/products/{product_id}/media"),
        ("POST", "/api/v2/admin/catalogue/products/{product_id}/media/generate"),
        ("PUT", "/api/v2/admin/catalogue/products/{product_id}/media/order"),
        ("PATCH", "/api/v2/admin/catalogue/media/{media_id}"), ("DELETE", "/api/v2/admin/catalogue/media/{media_id}"),
        ("POST", "/api/v2/admin/catalogue/media/generate-missing"), ("GET", "/api/v2/media/{media_id}"),
        ("GET", "/api/v2/admin/staff"), ("GET", "/api/v2/admin/staff/{handle}"),
        ("PUT", "/api/v2/admin/staff/{handle}/roles/{role}"), ("DELETE", "/api/v2/admin/staff/{handle}/roles/{role}"),
        ("GET", "/api/v2/admin/units"), ("GET", "/api/v2/admin/commerce/orders"),
        ("POST", "/api/v2/admin/commerce/offers/bulk"), ("POST", "/api/v2/admin/catalogue/import-jobs/{job_id}/publish"),
        # complete-wearhouse-research-intelligence
        ("GET", "/api/v2/catalogue/products/{product_id}/similar"), ("GET", "/api/v2/me/recommendations/products"),
        # add-wearhouse-sizes
        ("GET", "/api/v2/catalogue/sizes"), ("GET", "/api/v2/catalogue/products/{product_id}/sizes"),
        ("GET", "/api/v2/admin/catalogue/sizes"), ("PUT", "/api/v2/admin/catalogue/size-systems/{code}"),
        ("PUT", "/api/v2/admin/catalogue/size-systems/{code}/sizes/{size_code}"),
        ("GET", "/api/v2/admin/catalogue/products/{product_id}/sizes"),
        ("PUT", "/api/v2/admin/catalogue/products/{product_id}/sizes"),
        ("POST", "/api/v2/admin/catalogue/sizes/assign-missing"), ("GET", "/api/v2/me/sizes"), ("PUT", "/api/v2/me/sizes"),
        # add-wearhouse-settings-security
        ("GET", "/api/v2/me/settings"), ("PATCH", "/api/v2/me/settings"), ("GET", "/api/v2/me/security"),
        ("GET", "/api/v2/about"),
        # align-wearhouse-outfit-recommender
        ("POST", "/api/v2/me/recommendations/outfits/{run_id}/events"),
        # complete-wearhouse-tdd
        ("POST", "/api/v2/shares/{share_id}/report"), ("GET", "/api/v2/admin/moderation/reports"),
        ("POST", "/api/v2/admin/moderation/shares/{share_id}"), ("GET", "/api/v2/me/inspirations"),
        ("POST", "/api/v2/me/inspirations"), ("DELETE", "/api/v2/me/inspirations/{inspiration_id}"),
        ("GET", "/api/v2/admin/ops"),
    }
    assert not any("scan" in p for _, p in paths), "v2 never exposes serial-based ownership"


def test_openapi_export_is_offline_deterministic_and_checked_in(monkeypatch):
    from wearhouse.bootstrap.cli import export_openapi
    import wearhouse.platform.db as db

    def no_engines(*a, **k):
        raise AssertionError("contract export must not create database engines")

    monkeypatch.setattr(db, "make_engine", no_engines)
    first, second = export_openapi(), export_openapi()
    assert first == second
    checked_in = (REPO / "packages" / "contracts" / "openapi-v2.json").read_text(encoding="utf-8")
    assert checked_in.replace("\r\n", "\n") == first, "stale contract: run python tools/contracts.py generate"
