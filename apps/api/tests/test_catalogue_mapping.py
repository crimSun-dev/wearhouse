"""publish-wearhouse-catalogue 2.1: mapping hm-articles@1 (pure, no database).

Rows below are SYNTHETIC rows in the H&M articles.csv column format (no real H&M data is in the repo).
"""
from __future__ import annotations

from datetime import date

import pytest

from wearhouse.catalogue.domain import Permission, SnapshotRef, SourceRef, validate
from wearhouse.catalogue.mapping import HM_ARTICLES_V1, JobContext, map_hm_row, missing_columns, slot_for

CTX = JobContext(SourceRef("hm-pfr-synthetic", "Synthetic rows in H&M format", "https://wearhouse.invalid/s"),
                 SnapshotRef("b" * 64, "articles-synthetic.csv", date(2026, 11, 25)),
                 Permission("synthetic-test-fixture", "tests only", date(2026, 11, 25), "test suite",
                            "https://wearhouse.invalid/terms"))


def row(**over):
    base = {"article_id": "0108775015", "product_code": "0108775", "prod_name": "Strap top",
            "product_type_name": "Vest top", "product_group_name": "Garment Upper body",
            "colour_group_name": "Black", "department_name": "Jersey Basic", "section_name": "Womens Everyday Basics",
            "garment_group_name": "Jersey Basic", "index_group_name": "Ladieswear",
            "graphical_appearance_name": "Solid", "perceived_colour_master_name": "Black",
            "detail_desc": "Jersey top with narrow shoulder straps."}
    base.update(over)
    return base


def test_maps_required_and_optional_facts_keeping_originals_and_zeros():
    inp, errors = map_hm_row(row(), CTX)
    assert errors == [] and validate(inp) == []
    assert inp.external_id == "0108775015"
    assert inp.original_fields["product_code"] == "0108775"  # unmapped column still preserved
    assert {k: (f.value, f.source_field) for k, f in inp.facts.items()}["category"] == ("Vest top", "product_type_name")
    assert set(inp.facts) == {"product_name", "category", "product_group", "colour", "department", "section",
                              "garment_group", "index_group", "graphical_appearance", "perceived_colour", "description"}
    assert inp.annotations["slot"].value == "top" and inp.annotations["slot"].origin == "rule"
    assert inp.annotations["slot"].note == HM_ARTICLES_V1


def test_empty_description_and_optional_columns_are_omitted_not_invented():
    inp, _ = map_hm_row(row(detail_desc="", department_name="  "), CTX)
    assert "description" not in inp.facts and "department" not in inp.facts


@pytest.mark.parametrize("group,ptype,slot", [
    ("Garment Upper body", "T-shirt", "top"), ("Garment Upper body", "Jacket", "outer"),
    ("Garment Upper body", "Coat", "outer"), ("Garment Upper body", "Blazer", "outer"),
    ("Garment Upper body", "Outdoor Waistcoat", "outer"), ("Garment Lower body", "Trousers", "bottom"),
    ("Garment Full body", "Dress", "dress"), ("Shoes", "Sneakers", "footwear"), ("Accessories", "Bag", "accessory"),
    ("Underwear", "Bra", "underwear"), ("Socks & Tights", "Socks", None), ("Swimwear", "Bikini top", None),
    ("Nightwear", "Pyjama set", None), ("Cosmetic", "Lip gloss", None), ("", "", None),
])
def test_slot_rule_table(group, ptype, slot):
    assert slot_for(group, ptype) == slot
    inp, _ = map_hm_row(row(product_group_name=group or "Unknown", product_type_name=ptype or "X"), CTX)
    assert (inp.annotations.get("slot").value if "slot" in inp.annotations else None) == slot


def test_missing_required_values_are_row_errors():
    inp, errors = map_hm_row(row(product_type_name="", article_id=""), CTX)
    assert inp is None and {e.field for e in errors} == {"product_type_name", "article_id"}


def test_missing_required_columns_detected_from_header():
    assert missing_columns(["article_id", "prod_name"]) == ["product_type_name", "product_group_name",
                                                           "colour_group_name"]
    assert missing_columns(list(row())) == []
