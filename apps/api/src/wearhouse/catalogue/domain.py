"""Catalogue domain: source-preserving product facts, provenance and revision content identity.

Rules (design D5):
- (source namespace, external string id) identifies a product; leading zeros are preserved.
- Every verified fact names the original source field it came from and must equal that value.
  Curator/rule annotations are stored separately and can never shadow a fact.
- GTINs need GS1 check-digit validity plus evidence, and are never derived from an external id.
- Unknown characteristics stay absent (no defaults are invented).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Union

from ..platform.errors import FieldError, validation_failed

Scalar = Union[str, int, float, bool]

NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
EXTERNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")
FACT_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FACTS = ("product_name", "category")
ANNOTATION_ORIGINS = frozenset({"curator", "rule"})
MAX_ORIGINAL_FIELDS = 200


@dataclass(frozen=True)
class SourceRef:
    namespace: str
    name: str
    url: str


@dataclass(frozen=True)
class SnapshotRef:
    sha256: str
    file_name: str
    acquired_on: date


@dataclass(frozen=True)
class Permission:
    basis: str
    scope: str
    accepted_on: date
    accepted_by: str
    terms_url: str

    def as_record(self) -> dict:
        return {"basis": self.basis, "scope": self.scope, "accepted_on": self.accepted_on.isoformat(),
                "accepted_by": self.accepted_by, "terms_url": self.terms_url}


@dataclass(frozen=True)
class Fact:
    value: Scalar
    source_field: str


@dataclass(frozen=True)
class Annotation:
    value: Scalar
    origin: str
    note: str | None = None


@dataclass(frozen=True)
class Gtin:
    value: str
    scheme: str
    evidence: str


@dataclass(frozen=True)
class MediaRef:
    uri: str
    version: str
    rights: dict


@dataclass(frozen=True)
class Variant:
    key: str
    facts: dict[str, Fact]


@dataclass(frozen=True)
class SourceProductInput:
    source: SourceRef
    snapshot: SnapshotRef
    permission: Permission
    external_id: str
    original_fields: dict[str, Scalar | None]
    facts: dict[str, Fact]
    annotations: dict[str, Annotation] = field(default_factory=dict)
    gtin: Gtin | None = None
    media: tuple[MediaRef, ...] = ()
    variants: tuple[Variant, ...] = ()


def gs1_check_digit_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) not in (8, 12, 13, 14):
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def _https(url: str) -> bool:
    return url.startswith("https://") and len(url) <= 2048 and " " not in url


def _facts_errors(prefix: str, facts: dict[str, Fact], original: dict) -> list[FieldError]:
    errs = []
    for name, f in facts.items():
        if not FACT_NAME.fullmatch(name):
            errs.append(FieldError(f"{prefix}.{name}", "invalid_name", "Fact names are lower_snake_case."))
            continue
        if f.source_field not in original:
            errs.append(FieldError(f"{prefix}.{name}", "not_traceable_to_source",
                                   "A verified fact must name a field present in original_fields."))
        elif original[f.source_field] is None or str(original[f.source_field]) != str(f.value):
            errs.append(FieldError(f"{prefix}.{name}", "not_traceable_to_source",
                                   "A verified fact must equal its original source value."))
    return errs


def validate(inp: SourceProductInput) -> list[FieldError]:
    e: list[FieldError] = []
    if not NAMESPACE.fullmatch(inp.source.namespace):
        e.append(FieldError("source.namespace", "invalid", "Namespace must match ^[a-z0-9][a-z0-9-]{1,62}$."))
    if not inp.source.name.strip():
        e.append(FieldError("source.name", "required", "Source name is required."))
    if not _https(inp.source.url):
        e.append(FieldError("source.url", "https_required", "Source URL must be https."))
    if not SHA256.fullmatch(inp.snapshot.sha256):
        e.append(FieldError("snapshot.sha256", "invalid", "Snapshot checksum must be 64 lowercase hex chars."))
    if not inp.snapshot.file_name.strip():
        e.append(FieldError("snapshot.file_name", "required", "Snapshot file name is required."))
    for name in ("basis", "scope", "accepted_by"):
        if not getattr(inp.permission, name).strip():
            e.append(FieldError(f"permission.{name}", "required", "Permission record field is required."))
    if not _https(inp.permission.terms_url):
        e.append(FieldError("permission.terms_url", "https_required", "Terms URL must be https."))
    if not EXTERNAL_ID.fullmatch(inp.external_id):
        e.append(FieldError("external_id", "invalid", "External id must be a 1-64 char source string."))
    if not inp.original_fields:
        e.append(FieldError("original_fields", "required", "The original source row is required."))
    elif len(inp.original_fields) > MAX_ORIGINAL_FIELDS:
        e.append(FieldError("original_fields", "too_many", f"At most {MAX_ORIGINAL_FIELDS} fields."))
    for req in REQUIRED_FACTS:
        if req not in inp.facts:
            e.append(FieldError(f"facts.{req}", "required", f"Verified fact '{req}' is required."))
    e += _facts_errors("facts", inp.facts, inp.original_fields)
    for name, a in inp.annotations.items():
        if name in inp.facts:
            e.append(FieldError(f"annotations.{name}", "shadows_fact",
                                "Annotations are kept separate and cannot replace a source fact."))
        if a.origin not in ANNOTATION_ORIGINS:
            e.append(FieldError(f"annotations.{name}", "invalid_origin", "Origin must be 'curator' or 'rule'."))
    if inp.gtin is not None:
        g = inp.gtin
        if g.scheme != "gs1" or not gs1_check_digit_ok(g.value):
            e.append(FieldError("gtin.value", "invalid_gtin", "GTIN must be a valid GS1 number."))
        if g.value.lstrip("0") == inp.external_id.lstrip("0"):
            e.append(FieldError("gtin.value", "gtin_from_external_id",
                                "A source article id is not a GTIN; do not synthesize one."))
        if not g.evidence.strip():
            e.append(FieldError("gtin.evidence", "required", "GTIN requires identifier evidence."))
    for i, m in enumerate(inp.media):
        if not (_https(m.uri) or m.uri.startswith("urn:")):
            e.append(FieldError(f"media.{i}.uri", "invalid", "Media references must be https or urn: URIs."))
        if not str(m.rights.get("basis", "")).strip():
            e.append(FieldError(f"media.{i}.rights", "required", "Media needs a rights basis."))
    keys = [v.key for v in inp.variants]
    if len(keys) != len(set(keys)):
        e.append(FieldError("variants", "duplicate_key", "Variant keys must be unique."))
    for v in inp.variants:
        e += _facts_errors(f"variants.{v.key}.facts", v.facts, inp.original_fields)
    return e


def revision_content(inp: SourceProductInput) -> dict:
    """Canonical revision content. Snapshot/provenance metadata is excluded so re-ingesting the same
    facts from a newer snapshot does not create a spurious revision."""
    return {
        "original_fields": inp.original_fields,
        "facts": {k: {"value": f.value, "source_field": f.source_field} for k, f in sorted(inp.facts.items())},
        "annotations": {k: {"value": a.value, "origin": a.origin, "note": a.note}
                        for k, a in sorted(inp.annotations.items())},
        "gtin": None if inp.gtin is None else {"value": inp.gtin.value, "scheme": inp.gtin.scheme},
        "media": sorted([{"uri": m.uri, "version": m.version, "rights": m.rights} for m in inp.media],
                        key=lambda m: (m["uri"], m["version"])),
        "variants": sorted([{"key": v.key, "facts": {k: {"value": f.value, "source_field": f.source_field}
                                                     for k, f in sorted(v.facts.items())}} for v in inp.variants],
                           key=lambda v: v["key"]),
    }


def content_digest(inp: SourceProductInput) -> str:
    blob = json.dumps(revision_content(inp), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


# ------------------------------------------------------------------ documented colour table
# Colour-group names (H&M colour_group_name and plain English) -> representative swatch hex. Only listed names
# map; anything else stays unknown. Used by the colour-harmony heuristic and generated placeholders; these are
# representative swatches, never measured product colours.
COLOUR_HEX = {
    "black": "#000000", "white": "#ffffff", "off white": "#f4f1ea", "grey": "#808080", "light grey": "#c8c8c8",
    "dark grey": "#4a4a4a", "beige": "#d8c3a5", "light beige": "#e8dcc8", "dark beige": "#b59f7b",
    "brown": "#7b4b2a", "dark brown": "#4b2e1a", "red": "#c0392b", "dark red": "#7b1e1e", "light red": "#e57373",
    "pink": "#e891b0", "light pink": "#f6c6d6", "dark pink": "#b8336a", "orange": "#e67e22", "dark orange": "#b35900",
    "yellow": "#f1c40f", "light yellow": "#fbe7a1", "dark yellow": "#b7950b", "green": "#3a8f4b",
    "light green": "#a3d9a5", "dark green": "#1e5631", "greenish khaki": "#8a8d5a", "khaki green": "#78866b",
    "blue": "#2e6fb7", "light blue": "#9cc3e6", "dark blue": "#1b2a4a", "navy": "#1b2a4a", "turquoise": "#30b5b0",
    "purple": "#7d3c98", "light purple": "#c39bd3", "dark purple": "#4a235a", "lilac purple": "#b39ddb",
    "gold": "#c9a227", "silver": "#bfc1c2", "bronze/copper": "#a0522d",
    # remaining H&M colour groups (2026-11-25 catalogue): hue families; "Other", "Transparent", "Unknown" stay unknown
    "light orange": "#f5b880", "yellowish brown": "#a67b3d", "greyish beige": "#b8ad9a",
    "light turquoise": "#9fe0dc", "dark turquoise": "#137a75", "other pink": "#e891b0", "other yellow": "#f1c40f",
    "other orange": "#e67e22", "other green": "#3a8f4b", "other red": "#c0392b", "other blue": "#2e6fb7",
    "other purple": "#7d3c98", "other turquoise": "#30b5b0",
}


def colour_hex(name: str | None) -> str | None:
    if not name:
        return None
    return COLOUR_HEX.get(name.strip().lower())


# ------------------------------------------------------------------ sizes (add-wearhouse-sizes)
# Size systems and values are DATA (size_system / size_value); these helpers only parse and present references.
UNSIZED_RANK = 10**9


def parse_size_param(raw: str, field: str) -> tuple[str, str]:
    """`system:code`, e.g. `alpha:M` or `eu_shoe:42` (codes are unique within a system only)."""
    system, sep, code = (raw or "").partition(":")
    if not sep or not system or not code:
        raise validation_failed([FieldError(field, "invalid_size", "Use system:code, for example alpha:M.")])
    return system, code


def size_out(system: str, code: str, label: str, rank: int) -> dict:
    return {"system": system, "code": code, "label": label, "rank": rank}
