"""Starter wardrobe (owner request 2026-11-26): a configured set of official pieces is granted once, at onboarding."""
from __future__ import annotations

import pytest

from conftest import Api, counts, make_settings
from wearhouse.testing import create_test_app

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]


def onboard(api: Api, sub: str, handle: str):
    api.get("/api/v2/me", sub)
    r = api.client.patch("/api/v2/me/profile", json={"handle": handle}, headers=api.headers(sub))
    assert r.status_code == 200, r.text


def test_new_account_gets_the_starter_kit_once_as_owned_verified_items(api, staff, clean_db, issuer):
    kit_api = Api(create_test_app(make_settings(clean_db, issuer, starter_kit=(staff["product_id"],)), issuer=issuer), issuer)
    onboard(kit_api, "newcomer", "newcomer")
    items = kit_api.get("/api/v2/me/items", "newcomer").json()["items"]
    assert len(items) == 1 and items[0]["product"]["id"] == staff["product_id"]
    assert items[0]["public_serial"] and items[0]["acquisition"]["revision_no"] == 1
    wardrobe = kit_api.get("/api/v2/me/wardrobe/items", "newcomer").json()["items"]
    assert [w["verified"] for w in wardrobe] == [True]
    # Later profile edits, including a handle change, never grant again.
    r = kit_api.client.patch("/api/v2/me/profile", json={"display_name": "New Comer", "handle": "newcomer2"},
                             headers=kit_api.headers("newcomer"))
    assert r.status_code == 200, r.text
    assert len(kit_api.get("/api/v2/me/items", "newcomer").json()["items"]) == 1
    assert counts(clean_db, "activation_credential")["activation_credential"] == 0         # no activation key is ever minted for it


def test_without_configuration_onboarding_grants_nothing(api, staff, clean_db):
    onboard(api, "plain", "plain_user")
    assert api.get("/api/v2/me/items", "plain").json()["items"] == []
