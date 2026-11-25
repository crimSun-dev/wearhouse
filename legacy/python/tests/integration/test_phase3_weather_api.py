"""Phase 3 — the gateway wired into /outfits/recommend, the fault switch and the I2 log."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import InterfaceLog
from tests.conftest import API_KEY

REC = "/api/v1/outfits/recommend"


@pytest.fixture
def fast_app(db_url):
    """Same app but with a short BMKG deadline so the timeout fault test stays quick."""
    application = create_app(Settings(database_url=db_url, api_key=API_KEY, bmkg_timeout_s=0.5))
    yield application
    application.state.engine.dispose()


@pytest.fixture
def fast_client(fast_app):
    with TestClient(fast_app, headers={"X-API-Key": API_KEY}) as c:
        yield c


def test_recommend_with_mock_bmkg_shows_source_and_five_outfits(client):
    r = client.post(REC, json={"occasion": "campus"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["weather"]["source"] == "LIVE"  # mock mode = the real frozen sample, re-dated
    assert "BMKG" in body["weather"]["credit"]
    assert 1 <= len(body["outfits"]) <= 5
    again = client.post(REC, json={"occasion": "campus"}).json()
    assert again["weather"]["source"] == "CACHED"


def test_recommend_rejects_bad_input_with_422(client):
    assert client.post(REC, json={"occasion": "party"}).status_code == 422
    assert client.post(REC, json={"occasion": "campus", "adm4": "jakarta"}).status_code == 422


@pytest.mark.parametrize("mode", ["timeout", "http500", "malformed", "missing_fields"])
def test_each_injected_fault_still_answers_from_cache(fast_client, mode):
    assert fast_client.post(REC, json={"occasion": "casual"}).json()["weather"]["source"] == "LIVE"
    assert fast_client.post("/api/v1/admin/fault", json={"mode": mode}).json() == {"fault": mode}
    body = fast_client.post(REC, json={"occasion": "casual"}).json()
    assert body["weather"]["source"] == "CACHED"
    assert "fallback" in body["weather"]["note"]
    assert body["outfits"]
    assert fast_client.get("/api/v1/health").json()["fault"] == mode


# 11
def test_cold_failure_without_cache_returns_manual_required_and_outfits_still_returned_when_manual_given(client):
    client.post("/api/v1/admin/fault", json={"mode": "http500"})
    cold = client.post(REC, json={"occasion": "campus"}).json()
    assert cold["weather"]["source"] == "MANUAL_REQUIRED"
    assert cold["outfits"] == [] and cold["weather"]["ask"] == ["rain", "hot"]
    manual = client.post(REC, json={"occasion": "campus", "manual_weather": {"rain": True, "hot": False}}).json()
    assert manual["weather"]["source"] == "MANUAL"
    assert manual["outfits"]
    for o in manual["outfits"]:  # rain rule applied with the manual answer
        assert any(i["attrs"]["rain_suitable"] for i in o["items"] if i["slot"] in ("footwear", "outer"))


# 12
def test_fault_endpoint_requires_api_key(anon_client, client):
    assert anon_client.post("/api/v1/admin/fault", json={"mode": "timeout"}).status_code == 401
    bad = TestClient(anon_client.app, headers={"X-API-Key": "wrong"})
    assert bad.post("/api/v1/admin/fault", json={"mode": "timeout"}).status_code == 401
    assert client.get("/api/v1/health").json()["fault"] == "none"
    assert client.post("/api/v1/admin/fault", json={"mode": "bogus"}).status_code == 422


def test_bmkg_calls_and_failures_are_logged_as_I2(client, app):
    client.post(REC, json={"occasion": "campus"})
    client.post("/api/v1/admin/fault", json={"mode": "http500"})
    client.post(REC, json={"occasion": "campus"})
    with Session(app.state.engine) as s:
        i2 = s.scalars(select(InterfaceLog).where(InterfaceLog.interface == "I2").order_by(InterfaceLog.id)).all()
        i1 = s.scalars(select(InterfaceLog).where(InterfaceLog.route == "POST " + REC).order_by(InterfaceLog.id)).all()
    assert [r.status for r in i2] == [200, 500]
    assert [r.weather_source for r in i1] == ["LIVE", "CACHED"]


def test_weather_debug_view_lists_validated_slots(client):
    body = client.get("/api/v1/weather").json()
    assert body["source"] == "LIVE" and len(body["slots"]) == 21
    assert any(s["rain"] for s in body["slots"])
