"""add-wearhouse-object-management 2.1: generated placeholders are deterministic, escaped and honest (pure)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from wearhouse.catalogue.placeholder import SILHOUETTES, placeholder_svg

NS = "{http://www.w3.org/2000/svg}"


def test_deterministic_and_labelled():
    a = placeholder_svg(name="Strap top", category="Vest top", colour="Black", slot="top")
    assert a == placeholder_svg(name="Strap top", category="Vest top", colour="Black", slot="top")
    assert a != placeholder_svg(name="Strap top", category="Vest top", colour="White", slot="top")
    root = ET.fromstring(a)
    texts = [t.text for t in root.iter(NS + "text")]
    assert "GENERATED PLACEHOLDER" in texts and "Strap top" in texts
    assert root.get("role") == "img" and "Generated placeholder" in root.get("aria-label")


def test_markup_in_names_is_inert():
    svg = placeholder_svg(name='<script>alert(1)</script> & "quotes"', category="<b>x</b>", colour=None, slot="dress")
    root = ET.fromstring(svg)  # still well-formed
    tags = {el.tag.replace(NS, "") for el in root.iter()}
    assert tags <= {"svg", "rect", "g", "path", "text"}  # no element came from the name
    assert b"<script" not in svg and b"&lt;script&gt;" in svg


def test_unknown_colour_uses_neutral_and_says_so():
    svg = placeholder_svg(name="Odd", category="Shirt", colour="Mauve-ish", slot="top").decode()
    assert "#b9a9b5" in svg and "Mauve-ish (no swatch)" in svg


@pytest.mark.parametrize("slot", list(SILHOUETTES) + [None, "made-up"])
def test_every_slot_renders(slot):
    ET.fromstring(placeholder_svg(name="Item", category="Cat", colour="Blue", slot=slot))


def test_long_names_are_wrapped_and_truncated():
    svg = placeholder_svg(name="Very long product name " * 6, category="T-shirt", colour="Red", slot="top").decode()
    assert "…" in svg and len(svg) < 6000
