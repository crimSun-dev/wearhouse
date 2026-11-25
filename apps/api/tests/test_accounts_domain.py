"""add-wearhouse-accounts 3.3: pure visibility policy and validators (no database)."""
from __future__ import annotations

import itertools

import pytest

from wearhouse.accounts.domain import (DEFAULT_DISPLAY_NAME, Relation, Section, Visibility, can_view, clean_bio,
                                       clean_display_name, default_display_name, is_reserved, normalize_handle,
                                       relation_of)
from wearhouse.platform.errors import ApiError

EXPECTED = {  # (setting, relation) -> visible, identical for every section
    (Visibility.PUBLIC, Relation.SELF): True, (Visibility.PUBLIC, Relation.FRIEND): True,
    (Visibility.PUBLIC, Relation.STRANGER): True, (Visibility.PUBLIC, Relation.ANONYMOUS): True,
    (Visibility.PUBLIC, Relation.BLOCKED): False,
    (Visibility.FRIENDS, Relation.SELF): True, (Visibility.FRIENDS, Relation.FRIEND): True,
    (Visibility.FRIENDS, Relation.STRANGER): False, (Visibility.FRIENDS, Relation.ANONYMOUS): False,
    (Visibility.FRIENDS, Relation.BLOCKED): False,
    (Visibility.PRIVATE, Relation.SELF): True, (Visibility.PRIVATE, Relation.FRIEND): False,
    (Visibility.PRIVATE, Relation.STRANGER): False, (Visibility.PRIVATE, Relation.ANONYMOUS): False,
    (Visibility.PRIVATE, Relation.BLOCKED): False,
}


@pytest.mark.parametrize("section,setting,relation", list(itertools.product(Section, Visibility, Relation)))
def test_can_view_exhaustive(section, setting, relation):
    assert can_view(section, setting, relation) is EXPECTED[(setting, relation)]


def test_relation_precedence():
    assert relation_of(is_self=True, viewer_known=True, blocked=True, friends=True) is Relation.SELF
    assert relation_of(is_self=False, viewer_known=True, blocked=True, friends=True) is Relation.BLOCKED
    assert relation_of(is_self=False, viewer_known=False, blocked=False, friends=False) is Relation.ANONYMOUS
    assert relation_of(is_self=False, viewer_known=True, blocked=False, friends=True) is Relation.FRIEND
    assert relation_of(is_self=False, viewer_known=True, blocked=False, friends=False) is Relation.STRANGER


@pytest.mark.parametrize("raw,expected", [("Dravenstyle", "dravenstyle"), ("  abc ", "abc"), ("a_1", "a_1"),
                                          ("x" * 20, "x" * 20)])
def test_valid_handles(raw, expected):
    assert normalize_handle(raw) == expected


@pytest.mark.parametrize("raw", ["ab", "x" * 21, "1abc", "_abc", "ab-c", "ab c", "ábc", "аbc", "ab.c", "", "ab\x00c"])
def test_invalid_handles(raw):
    with pytest.raises(ApiError) as e:
        normalize_handle(raw)
    assert e.value.status == 422


def test_reserved_handles():
    assert is_reserved("admin") and is_reserved("wearhouse_team") and not is_reserved("dravenstyle")


def test_display_name_and_bio_rules():
    assert clean_display_name("  Ada Lovelace ") == "Ada Lovelace"
    assert clean_display_name("名前") == "名前"
    for bad in ("", "   ", "x" * 33, "bad\x07bell", "zero​width"):
        with pytest.raises(ApiError):
            clean_display_name(bad)
    assert clean_bio("line one\nline two") == "line one\nline two"
    for bad in ("x" * 161, "tab\there"):
        with pytest.raises(ApiError):
            clean_bio(bad)


def test_default_display_name_from_hint():
    assert default_display_name("Draven Chen") == "Draven Chen"
    assert default_display_name("x" * 50) == "x" * 32
    assert default_display_name("\x00\x01") == DEFAULT_DISPLAY_NAME
    assert default_display_name(None) == DEFAULT_DISPLAY_NAME
