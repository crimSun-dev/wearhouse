"""Source field mappings (pure). `hm-articles@1` maps the H&M Personalized Fashion Recommendations
`articles.csv` columns to verified facts. Every original column is kept, identifiers stay strings, and a
wardrobe slot is only ever a rule annotation from the documented table (design D3). Nothing is invented.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..platform.errors import FieldError
from .domain import Annotation, Fact, Permission, SnapshotRef, SourceProductInput, SourceRef

HM_ARTICLES_V1 = "hm-articles@1"

REQUIRED = {  # fact name <- source column
    "product_name": "prod_name",
    "category": "product_type_name",
    "product_group": "product_group_name",
    "colour": "colour_group_name",
}
OPTIONAL = {
    "department": "department_name",
    "section": "section_name",
    "garment_group": "garment_group_name",
    "index_group": "index_group_name",
    "graphical_appearance": "graphical_appearance_name",
    "perceived_colour": "perceived_colour_master_name",
    "description": "detail_desc",
}
REQUIRED_COLUMNS = ("article_id", *REQUIRED.values())
OUTER_TYPES = frozenset({"Jacket", "Coat", "Blazer", "Outdoor Waistcoat"})
GROUP_SLOTS = {
    "Garment Upper body": "top",
    "Garment Lower body": "bottom",
    "Garment Full body": "dress",
    "Shoes": "footwear",
    "Accessories": "accessory",
}
MAPPINGS = (HM_ARTICLES_V1,)


def slot_for(product_group: str | None, product_type: str | None) -> str | None:
    """Rule table (design D3). Returns None (unknown) for anything not listed: never a guess."""
    slot = GROUP_SLOTS.get((product_group or "").strip())
    if slot == "top" and (product_type or "").strip() in OUTER_TYPES:
        return "outer"
    return slot


def missing_columns(header: list[str]) -> list[str]:
    return [c for c in REQUIRED_COLUMNS if c not in header]


@dataclass(frozen=True)
class JobContext:
    source: SourceRef
    snapshot: SnapshotRef
    permission: Permission


def map_hm_row(row: dict[str, str], ctx: JobContext) -> tuple[SourceProductInput | None, list[FieldError]]:
    """One CSV row -> the same input the single-product ingestion validates (plus row-level errors)."""
    errors: list[FieldError] = []
    original = {k: v for k, v in row.items() if k is not None}
    external_id = (original.get("article_id") or "").strip()
    if not external_id:
        errors.append(FieldError("article_id", "required", "article_id is empty."))
    facts: dict[str, Fact] = {}
    for fact, col in REQUIRED.items():
        value = (original.get(col) or "").strip()
        if not value:
            errors.append(FieldError(col, "required", f"{col} is empty."))
        else:
            facts[fact] = Fact(value=original[col], source_field=col)
    for fact, col in OPTIONAL.items():
        if (original.get(col) or "").strip():
            facts[fact] = Fact(value=original[col], source_field=col)
    if errors:
        return None, errors
    annotations = {}
    slot = slot_for(original.get("product_group_name"), original.get("product_type_name"))
    if slot is not None:
        annotations["slot"] = Annotation(value=slot, origin="rule", note=HM_ARTICLES_V1)
    return SourceProductInput(source=ctx.source, snapshot=ctx.snapshot, permission=ctx.permission,
                              external_id=external_id, original_fields=original, facts=facts,
                              annotations=annotations), []
