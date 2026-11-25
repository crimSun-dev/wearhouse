"""7.1 consistent error shapes and secret-free responses/logs."""
from __future__ import annotations

import logging
import uuid

import pytest
from sqlalchemy.exc import OperationalError

from conftest import issue, redeem
from wearhouse.ownership.domain import key_digest, normalize_key
from wearhouse.platform.adapters.sql import SqlAttemptLedger
from wearhouse.platform.http import redact

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]


def shape(r):
    body = r.json()
    assert isinstance(body["request_id"], str) and body["request_id"] == r.headers["x-request-id"]
    assert isinstance(body["code"], str) and body["code"].isupper() and isinstance(body["message"], str)
    assert set(body) <= {"code", "message", "request_id", "field_errors"}
    return body["code"]


def test_every_error_status_has_the_contract_shape(api, staff, clean_db, monkeypatch):
    unit = issue(api, staff["product_id"])
    seen = {}
    seen[400] = shape(redeem(api, "cust", "AAAA-BBBB-CCCC-DDDD"))
    seen[401] = shape(api.client.get("/api/v2/me"))
    seen[403] = shape(api.post("/api/v2/admin/unit-batches", "cust", json={"product_id": staff["product_id"]},
                               idem="forbid-0001"))
    seen[404] = shape(api.get("/api/v2/me/items/" + str(uuid.uuid4()), "cust"))
    assert redeem(api, "cust", unit["delivery"]["activation_key"], idem="conf-0001").status_code == 201
    seen[409] = shape(redeem(api, "cust", "AAAA-BBBB-CCCC-DDDD", idem="conf-0001"))
    seen[422] = shape(api.post("/api/v2/redemptions", "cust", json={"activation_key": 123}, idem="val-00001"))
    for i in range(10):
        redeem(api, "limited", f"AAAA-AAAA-AAAA-{chr(65 + i)}AAA")
    limited = redeem(api, "limited", "AAAA-AAAA-AAAA-ZZZZ")
    seen[429] = shape(limited)
    assert limited.headers["Retry-After"].isdigit()
    monkeypatch.setattr(SqlAttemptLedger, "reserve",
                        lambda *a, **k: (_ for _ in ()).throw(OperationalError("x", {}, Exception())))
    unavailable = redeem(api, "cust2", "AAAA-BBBB-CCCC-DDDD")
    seen[503] = shape(unavailable)
    assert unavailable.headers["Retry-After"] == "5"
    assert seen == {400: "INVALID_ACTIVATION_CODE", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                    409: "IDEMPOTENCY_KEY_REUSED", 422: "VALIDATION_FAILED", 429: "RATE_LIMITED",
                    503: "SERVICE_UNAVAILABLE"}


def test_field_errors_never_echo_input_values(api, staff):
    secret_like = "SECRET-INPUT-" + "Q" * 600  # too long -> 422, must not be echoed
    r = api.post("/api/v2/redemptions", "cust", json={"activation_key": secret_like, "extra": "PRIVATE-VALUE"},
                 idem="echo-00001")
    assert r.status_code == 422
    assert "SECRET-INPUT" not in r.text and "PRIVATE-VALUE" not in r.text and "QQQQ" not in r.text
    fields = {e["field"] for e in r.json()["field_errors"]}
    assert {"body.activation_key", "body.extra"} <= fields


def test_logs_hold_metadata_but_no_secrets(api, staff, clean_db, caplog):
    caplog.set_level(logging.DEBUG)
    unit = issue(api, staff["product_id"])
    key = unit["delivery"]["activation_key"]
    token = api.issuer.token("cust")
    api.client.post("/api/v2/redemptions", json={"activation_key": key[:-1] + "A"},
                    headers={"Authorization": "Bearer " + token, "Idempotency-Key": "log-check-0001"})
    api.client.post("/api/v2/redemptions", json={"activation_key": key},
                    headers={"Authorization": "Bearer " + token, "Idempotency-Key": "log-check-0002"})
    logs = caplog.text
    assert "POST /api/v2/redemptions 400" in logs and "POST /api/v2/redemptions 201" in logs  # metadata retained
    digest = key_digest(normalize_key(key))
    for secret in (key, key.replace("-", ""), key[:-1] + "A", token, token.split(".")[1], digest):
        assert secret not in logs


def test_redaction_filter_defence_in_depth():
    token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
    text = redact(f"Authorization: Bearer {token} key ABCD-EFGH-IJKL-MNOP digest {'a' * 64}")
    assert token not in text and "ABCD-EFGH-IJKL-MNOP" not in text and "a" * 64 not in text
