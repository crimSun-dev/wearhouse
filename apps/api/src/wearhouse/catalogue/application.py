"""Source-product ingestion (one validated product per request). Bulk import, publication and browse live in
`publication.py` (publish-wearhouse-catalogue) and reuse `apply_source_product`."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from ..identity.domain import Capability, Principal, require
from ..platform.clock import Clock, utcnow
from ..platform.errors import FieldError, conflict, validation_failed
from .domain import UNSIZED_RANK, SourceProductInput, content_digest, size_out, validate
from .ports import CatalogueUoW


@dataclass(frozen=True)
class IngestResult:
    product_id: uuid.UUID
    revision_id: uuid.UUID
    revision_no: int
    product_created: bool
    revision_created: bool


class CatalogueService:
    def __init__(self, uow_factory: Callable[[], CatalogueUoW], clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.clock = clock

    def ingest(self, principal: Principal, inp: SourceProductInput) -> IngestResult:
        require(principal, Capability.INGEST_PRODUCTS)
        errors = validate(inp)
        if errors:
            raise validation_failed(errors)
        with self.uow_factory() as uow:
            result = apply_source_product(uow, principal, inp, self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.source_product_ingested",
                             target_type="product", target_id=str(result.product_id),
                             details={"namespace": inp.source.namespace, "external_id": inp.external_id,
                                      "revision_no": result.revision_no, "product_created": result.product_created,
                                      "revision_created": result.revision_created})
            uow.commit()
        return result


def apply_source_product(uow: CatalogueUoW, principal: Principal, inp: SourceProductInput, now) -> IngestResult:
    """Shared by single ingestion and bulk import: same identity, digest and revision rules (validated input)."""
    digest = content_digest(inp)
    repo = uow.catalogue
    source_id = repo.ensure_source(inp.source.namespace, inp.source.name, inp.source.url)
    snapshot_id = repo.ensure_snapshot(source_id, inp)
    product, created = repo.lock_product(source_id, inp.external_id, inp.gtin, now)
    if inp.gtin is not None and product.gtin not in (None, inp.gtin.value):
        raise conflict("GTIN_CONFLICT", "This product already has a different GTIN.")
    latest = repo.latest_revision(product.id)
    if latest is not None and latest.content_digest == digest:
        return IngestResult(product.id, latest.id, latest.revision_no, False, False)
    no = 1 if latest is None else latest.revision_no + 1
    rid = repo.add_revision(product_id=product.id, revision_no=no, snapshot_id=snapshot_id, digest=digest, inp=inp,
                            created_by=principal.user_id, now=now)
    uow.outbox.emit(event_type="catalogue.product_revised", aggregate_type="product", aggregate_id=product.id,
                    payload={"revision_id": str(rid), "revision_no": no})
    return IngestResult(product.id, rid, no, created, True)


# ================================================================ sizes (add-wearhouse-sizes)
class SizeIndex:
    """One read of the size registry, for validating references and presenting labels/ranks.
    Other modules (commerce, ownership, wardrobe) use this instead of reading catalogue tables."""

    def __init__(self, systems, values):
        self.systems = {s.code: s for s in systems}
        self.values = {(v.system, v.code): v for v in values}

    @classmethod
    def load(cls, sizes) -> "SizeIndex":
        return cls(sizes.systems(), sizes.values())

    def require(self, system: str, code: str, field: str, *, active: bool = True):
        s, v = self.systems.get(system), self.values.get((system, code))
        if s is None or v is None or (active and not (s.active and v.active)):
            raise validation_failed([FieldError(field, "unknown_size", f"Unknown size {system}:{code}.")])
        return v

    def out(self, system: str | None, code: str | None, label: str | None = None) -> dict | None:
        if not system or not code:
            return None
        v = self.values.get((system, code))
        return size_out(system, code, label or (v.label if v else code), v.rank if v else UNSIZED_RANK)

    def sort_key(self, system: str | None, code: str | None) -> tuple:
        if not system or not code:
            return (UNSIZED_RANK, UNSIZED_RANK)
        s, v = self.systems.get(system), self.values.get((system, code))
        return (s.position if s else UNSIZED_RANK - 1, v.rank if v else UNSIZED_RANK - 1)
