"""Catalogue ports. `RevisionReader` is the public application interface other modules consume;
they never query catalogue tables directly."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from ..platform.ports import AuditWriter, OutboxWriter, UnitOfWork
from .domain import SourceProductInput


@dataclass(frozen=True)
class ProductRow:
    id: uuid.UUID
    gtin: str | None
    current_revision_id: uuid.UUID | None


@dataclass(frozen=True)
class RevisionRow:
    id: uuid.UUID
    revision_no: int
    content_digest: str


@dataclass(frozen=True)
class RevisionSummary:
    product_id: uuid.UUID
    revision_id: uuid.UUID
    revision_no: int
    source_namespace: str
    external_id: str
    snapshot_sha256: str
    catalogue_status: str
    facts: dict  # verified source facts: name -> value

    @property
    def product_name(self) -> str:
        return str(self.facts.get("product_name", ""))

    @property
    def category(self) -> str:
        return str(self.facts.get("category", ""))


class CatalogueRepository(Protocol):
    def ensure_source(self, namespace: str, name: str, url: str) -> uuid.UUID: ...

    def ensure_snapshot(self, source_id: uuid.UUID, inp: SourceProductInput) -> uuid.UUID: ...

    def lock_product(self, source_id: uuid.UUID, external_id: str, gtin, now: datetime) -> tuple[ProductRow, bool]:
        """Insert-if-absent and lock the product identity row. Returns (row, created)."""

    def latest_revision(self, product_id: uuid.UUID) -> RevisionRow | None: ...

    def add_revision(self, *, product_id: uuid.UUID, revision_no: int, snapshot_id: uuid.UUID, digest: str,
                     inp: SourceProductInput, created_by: uuid.UUID, now: datetime) -> uuid.UUID: ...


class RevisionReader(Protocol):
    def current_for_product(self, product_id: uuid.UUID) -> RevisionSummary | None: ...

    def published_for_product(self, product_id: uuid.UUID) -> RevisionSummary | None:
        """The published revision (publish-wearhouse-catalogue); None for drafts."""

    def by_revision(self, revision_id: uuid.UUID) -> RevisionSummary | None: ...

    def on_sale(self, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, RevisionSummary]:
        """Published, non-retired products only (add-wearhouse-sandbox-commerce)."""

    def published_ids(self, category: str | None, slot: str | None) -> list[uuid.UUID]:
        """Published products matching a category and/or slot (bulk sandbox offers)."""

    def annotations_for(self, revision_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
        """revision id -> annotations {name: {value, origin, note}} (wardrobe planning: catalogue slot)."""


@dataclass(frozen=True)
class ProductState:
    id: uuid.UUID
    publication_state: str
    published_revision_id: uuid.UUID | None
    current_revision_id: uuid.UUID | None
    published_at: datetime | None


@dataclass(frozen=True)
class RevisionContent:
    id: uuid.UUID
    product_id: uuid.UUID
    revision_no: int
    facts: dict  # name -> {value, source_field}
    annotations: dict  # name -> {value, origin, note}
    created_at: datetime


@dataclass(frozen=True)
class BrowseQuery:
    q: str | None = None
    category: str | None = None
    colour: str | None = None
    slot: str | None = None
    sort: str = "newest"  # newest | name
    sizes: tuple[tuple[str, str], ...] = ()  # (system, code): products available in ANY of these (add-wearhouse-sizes)
    exclude: tuple = ()  # product ids to leave out: "hide owned products" (complete-wearhouse-tdd)


@dataclass(frozen=True)
class BrowseRow:
    id: uuid.UUID
    name: str
    category: str | None
    colour: str | None
    slot: str | None
    published_at: datetime
    thumbnail: str | None = None


@dataclass(frozen=True)
class MediaRow:
    id: uuid.UUID
    product_id: uuid.UUID
    kind: str  # generated | uploaded
    content_type: str
    sha256: str
    byte_size: int
    alt_text: str | None
    position: int
    rights: dict
    generator: str | None
    status: str  # active | removed
    created_at: datetime
    removed_at: datetime | None
    created_by: uuid.UUID | None = None


class CataloguePublishing(Protocol):
    """Import jobs, publication, collections and public browse (publish-wearhouse-catalogue)."""

    def create_import_job(self, *, job_id: uuid.UUID, source_id: uuid.UUID, snapshot_id: uuid.UUID, mapping: str,
                          row_count: int, created_by: uuid.UUID, now: datetime) -> None: ...
    def add_import_row(self, *, job_id: uuid.UUID, row_no: int, external_id: str | None, outcome: str,
                       product_id: uuid.UUID | None, revision_no: int | None, errors: list[dict]) -> None: ...
    def complete_import_job(self, job_id: uuid.UUID, totals: dict, now: datetime) -> None: ...
    def get_import_job(self, job_id: uuid.UUID) -> dict | None: ...
    def lock_product_state(self, product_id: uuid.UUID) -> ProductState | None: ...
    def revision_content(self, revision_id: uuid.UUID) -> RevisionContent | None: ...
    def revisions_of(self, product_id: uuid.UUID) -> list[RevisionContent]: ...
    def product_identity(self, product_id: uuid.UUID) -> dict | None: ...
    def set_published(self, product_id: uuid.UUID, revision_id: uuid.UUID, browse: dict, now: datetime) -> None: ...
    def set_retired(self, product_id: uuid.UUID, now: datetime) -> None: ...
    def review_queue(self, limit: int) -> list[dict]: ...
    def browse(self, query: BrowseQuery, after: list | None, limit: int) -> list[BrowseRow]: ...
    def facets(self) -> dict[str, list[dict]]: ...
    def public_media(self, revision_id: uuid.UUID) -> list[dict]: ...
    def collections(self, *, public: bool) -> list[dict]: ...
    def collection(self, slug: str, *, public: bool) -> dict | None: ...
    def put_collection(self, slug: str, title: str, product_ids: list[uuid.UUID], now: datetime) -> None: ...
    def delete_collection(self, slug: str) -> bool: ...
    def existing_products(self, product_ids: list[uuid.UUID]) -> set[uuid.UUID]: ...
    # recommendation serving (complete-wearhouse-research-intelligence)
    def cards(self, product_ids: list[uuid.UUID]) -> list[dict]: ...
    def similar_by_content(self, product_id: uuid.UUID, limit: int) -> list[uuid.UUID]: ...
    def newest_published(self, limit: int, exclude: set[uuid.UUID]) -> list[uuid.UUID]: ...
    def products_by_external(self, namespace: str, external_ids: list[str]) -> dict[str, uuid.UUID]: ...
    # product media objects (add-wearhouse-object-management)
    def list_media(self, product_id: uuid.UUID, include_removed: bool = False) -> list[MediaRow]: ...
    def lock_media_list(self, product_id: uuid.UUID) -> list[MediaRow]: ...
    def insert_media(self, row: MediaRow, data: bytes) -> None: ...
    def get_media(self, media_id: uuid.UUID) -> MediaRow | None: ...
    def media_bytes(self, media_id: uuid.UUID) -> dict | None: ...
    def update_media(self, media_id: uuid.UUID, values: dict) -> None: ...
    def products_without_media(self, limit: int) -> list[dict]: ...
    def browse_facts(self, product_id: uuid.UUID) -> dict | None: ...


class CatalogueUoW(UnitOfWork, Protocol):
    catalogue: CatalogueRepository
    publishing: CataloguePublishing
    audit: AuditWriter
    outbox: OutboxWriter


# ------------------------------------------------------------------ sizes (add-wearhouse-sizes)
@dataclass(frozen=True)
class SizeSystem:
    code: str
    label: str
    position: int
    slots: tuple[str, ...]
    active: bool


@dataclass(frozen=True)
class SizeValue:
    system: str
    code: str
    label: str
    rank: int
    common: bool
    active: bool


@dataclass(frozen=True)
class ProductSize:
    system: str
    code: str
    origin: str


class SizeRepository(Protocol):
    """Public size interface: other modules read sizes only through this port (uow.sizes)."""
    def systems(self) -> list[SizeSystem]: ...
    def values(self) -> list[SizeValue]: ...
    def put_system(self, s: SizeSystem, now: datetime) -> None: ...
    def put_value(self, v: SizeValue, now: datetime) -> None: ...
    def product_sizes(self, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ProductSize]]: ...
    def set_product_sizes(self, product_id: uuid.UUID, sizes: list[ProductSize], now: datetime) -> None: ...
    def unsized_published(self, slots: list[str], limit: int) -> list[tuple[uuid.UUID, str]]: ...
    def add_product_sizes(self, rows: list[tuple[uuid.UUID, ProductSize]], now: datetime) -> None: ...
    def preferences(self, user_id: uuid.UUID) -> dict[str, str]: ...
    def set_preference(self, user_id: uuid.UUID, system: str, code: str | None, now: datetime) -> None: ...
    def erase_preferences(self, user_id: uuid.UUID) -> None: ...
