"""publish-wearhouse-catalogue: bulk import jobs, draft -> published -> retired lifecycle, featured collections and
the public store-front browse. Staff operations need the catalogue capability; browse is public and read-only."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import uuid
from datetime import datetime
from typing import Callable

from ..identity.domain import Capability, Principal, require
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.errors import FieldError, conflict, not_found, validation_failed
from ..platform.ids import new_id
from ..platform.pagination import check_limit, decode_keyset, encode_keyset, invalid_cursor
from .application import SizeIndex, apply_source_product
from .domain import SourceProductInput, validate
from .mapping import HM_ARTICLES_V1, MAPPINGS, JobContext, map_hm_row, missing_columns
from .placeholder import GENERATOR, placeholder_svg
from .ports import BrowseQuery, CatalogueUoW, MediaRow, RevisionContent

MAX_ROWS = 5000
MAX_BYTES = 10 * 1024 * 1024
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SORTS = ("newest", "name")
MAX_COLLECTION_ITEMS = 200
CONTEXT_FIELDS = ("source.", "snapshot.", "permission.")


def _value(d: dict, name: str):
    v = d.get(name)
    return v.get("value") if isinstance(v, dict) else None


def browse_fields(rev: RevisionContent) -> dict:
    """Denormalised browse columns written on publish (design D1). Only published facts/annotations."""
    name = _value(rev.facts, "product_name")
    desc = _value(rev.facts, "description")
    return {"browse_name": None if name is None else str(name),
            "browse_category": _str(_value(rev.facts, "category")),
            "browse_colour": _str(_value(rev.facts, "colour")),
            "browse_slot": _str(_value(rev.annotations, "slot")),
            "browse_text": f"{name or ''} {desc or ''}".lower()}


def _str(v):
    return None if v is None else str(v)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Strict parse of the whole file BEFORE any row is processed (spec: malformed input is rejected up front)."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise validation_failed([FieldError("body.csv", "too_large", "The CSV exceeds 10 MB.")])
    try:
        reader = csv.reader(io.StringIO(text.lstrip("﻿"), newline=""), strict=True)
        rows = list(reader)
    except csv.Error as exc:
        raise validation_failed([FieldError("body.csv", "malformed", f"The CSV is malformed: {exc}.")]) from None
    rows = [r for r in rows if r != []]
    if not rows:
        raise validation_failed([FieldError("body.csv", "empty", "The CSV has no header row.")])
    header = [h.strip() for h in rows[0]]
    if len(set(header)) != len(header):
        raise validation_failed([FieldError("body.csv", "duplicate_columns", "The header repeats a column.")])
    missing = missing_columns(header)
    if missing:
        raise validation_failed([FieldError("body.csv", "missing_columns",
                                            "Required columns are missing: " + ", ".join(missing) + ".")])
    data = rows[1:]
    if not data:
        raise validation_failed([FieldError("body.csv", "empty", "The CSV has no data rows.")])
    if len(data) > MAX_ROWS:
        raise validation_failed([FieldError("body.csv", "too_many_rows", f"A job may contain at most {MAX_ROWS} rows.")])
    for i, r in enumerate(data, start=1):
        if len(r) != len(header):
            raise validation_failed([FieldError("body.csv", "malformed",
                                                f"Row {i} has {len(r)} fields; the header has {len(header)}.")])
    return header, [dict(zip(header, r)) for r in data]


def chunk_csv(text: str, max_rows: int = MAX_ROWS, max_bytes: int = MAX_BYTES) -> list[str]:
    """Split a large source CSV into job-sized CSV texts (header repeated; rows never split or altered)."""
    lines = text.lstrip("﻿").splitlines(keepends=True)
    if not lines:
        return []
    header, chunks, cur = lines[0], [], []
    size = len(header.encode("utf-8"))
    for ln in lines[1:]:
        b = len(ln.encode("utf-8"))
        if cur and (len(cur) >= max_rows or size + b > max_bytes):
            chunks.append(header + "".join(cur))
            cur, size = [], len(header.encode("utf-8"))
        cur.append(ln)
        size += b
    if cur:
        chunks.append(header + "".join(cur))
    return chunks


class CataloguePublicationService:
    FACET_TTL_S = 60.0

    def __init__(self, uow_factory: Callable[[], CatalogueUoW], ring: KeyRing, clock: Clock = utcnow,
                 monotonic: Callable[[], float] = time.monotonic):
        self.uow_factory = uow_factory
        self.ring = ring
        self.clock = clock
        self.monotonic = monotonic
        self._facets: tuple[float, dict] | None = None  # per-process cache (design D6); staleness <= FACET_TTL_S

    def invalidate_facets(self) -> None:
        self._facets = None

    # ================================================================ import
    def run_import(self, principal: Principal, ctx: JobContext, mapping: str, csv_text: str) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        if mapping not in MAPPINGS:
            raise validation_failed([FieldError("body.mapping", "unknown_mapping",
                                                "Supported mappings: " + ", ".join(MAPPINGS) + ".")])
        _, rows = parse_csv(csv_text)
        mapped = [map_hm_row(r, ctx) for r in rows]
        # Job-wide context (source/snapshot/permission) problems reject the whole job, not every row.
        probe = SourceProductInput(source=ctx.source, snapshot=ctx.snapshot, permission=ctx.permission,
                                   external_id="probe", original_fields={"probe": "probe"}, facts={})
        ctx_errors = [e for e in validate(probe) if e.field.startswith(CONTEXT_FIELDS)]
        if ctx_errors:
            raise validation_failed(ctx_errors)
        now = self.clock()
        job_id = new_id()
        with self.uow_factory() as uow:
            source_id = uow.catalogue.ensure_source(ctx.source.namespace, ctx.source.name, ctx.source.url)
            snapshot_id = uow.catalogue.ensure_snapshot(source_id, probe)
            uow.publishing.create_import_job(job_id=job_id, source_id=source_id, snapshot_id=snapshot_id,
                                             mapping=mapping, row_count=len(rows), created_by=principal.user_id,
                                             now=now)
            uow.commit()
        totals = {"created": 0, "revised": 0, "unchanged": 0, "rejected": 0}
        for row_no, (inp, errors) in enumerate(mapped, start=1):
            if inp is not None and not errors:
                errors = validate(inp)
            ext = (rows[row_no - 1].get("article_id") or "").strip() or None
            with self.uow_factory() as uow:  # one transaction per row (design D2)
                if errors:
                    outcome, pid, rno = "rejected", None, None
                else:
                    res = apply_source_product(uow, principal, inp, self.clock())
                    outcome = "created" if res.product_created else "revised" if res.revision_created else "unchanged"
                    pid, rno = res.product_id, res.revision_no
                uow.publishing.add_import_row(job_id=job_id, row_no=row_no, external_id=ext, outcome=outcome,
                                              product_id=pid, revision_no=rno,
                                              errors=[{"field": e.field, "code": e.code, "message": e.message}
                                                      for e in errors])
                uow.commit()
            totals[outcome] += 1
        with self.uow_factory() as uow:
            uow.publishing.complete_import_job(job_id, totals, self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.import_completed",
                             target_type="catalogue_import_job", target_id=str(job_id),
                             details={"namespace": ctx.source.namespace, "mapping": mapping, "rows": len(rows),
                                      **totals})
            uow.commit()
        return self.import_job(principal, job_id)

    def import_job(self, principal: Principal, job_id: uuid.UUID) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            job = uow.publishing.get_import_job(job_id)
        if job is None:
            raise not_found("Import job not found.")
        job["created_at"], job["completed_at"] = _iso(job["created_at"]), _iso(job["completed_at"])
        return job

    def publish_job(self, principal: Principal, job_id: uuid.UUID, batch: int = 500) -> dict:
        """Publish the latest revision of every product an import job created/revised/kept. Retired products are
        left retired. One audit event per job (its rows list every product)."""
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            job = uow.publishing.get_import_job(job_id)
        if job is None:
            raise not_found("Import job not found.")
        pids = [uuid.UUID(r["product_id"]) for r in job["rows"] if r["product_id"]]
        totals = {"published": 0, "already_published": 0, "retired_skipped": 0}
        for i in range(0, len(pids), batch):
            with self.uow_factory() as uow:
                for pid in pids[i:i + batch]:
                    state = uow.publishing.lock_product_state(pid)
                    if state.publication_state == "retired":
                        totals["retired_skipped"] += 1
                    elif state.publication_state == "published" and state.published_revision_id == state.current_revision_id:
                        totals["already_published"] += 1
                    else:
                        rev = uow.publishing.revision_content(state.current_revision_id)
                        uow.publishing.set_published(pid, rev.id, browse_fields(rev), self.clock())
                        totals["published"] += 1
                uow.commit()
        with self.uow_factory() as uow:
            uow.audit.record(actor_id=principal.user_id, action="catalogue.import_job_published",
                             target_type="catalogue_import_job", target_id=str(job_id), details=totals)
            uow.commit()
        self.invalidate_facets()
        return {"job_id": str(job_id), **totals}

    # ================================================================ publication
    def publish(self, principal: Principal, product_id: uuid.UUID, revision_id: uuid.UUID) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            state = uow.publishing.lock_product_state(product_id)
            if state is None:
                raise not_found("Product not found.")
            rev = uow.publishing.revision_content(revision_id)
            if rev is None or rev.product_id != product_id:
                raise validation_failed([FieldError("body.revision_id", "unknown_revision",
                                                    "That revision does not belong to this product.")])
            if state.publication_state == "published" and state.published_revision_id == revision_id:
                uow.commit()
                return self.staff_product(principal, product_id)
            if _value(rev.facts, "product_name") is None:
                raise conflict("NOT_PUBLISHABLE", "A revision needs a product name before it can be published.")
            uow.publishing.set_published(product_id, revision_id, browse_fields(rev), self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.product_published", target_type="product",
                             target_id=str(product_id),
                             details={"revision_id": str(revision_id), "revision_no": rev.revision_no,
                                      "previous_state": state.publication_state})
            uow.outbox.emit(event_type="catalogue.product_published", aggregate_type="product",
                            aggregate_id=product_id, payload={"revision_id": str(revision_id),
                                                              "revision_no": rev.revision_no})
            uow.commit()
        self.invalidate_facets()
        return self.staff_product(principal, product_id)

    def retire(self, principal: Principal, product_id: uuid.UUID) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            state = uow.publishing.lock_product_state(product_id)
            if state is None:
                raise not_found("Product not found.")
            if state.publication_state != "retired":
                uow.publishing.set_retired(product_id, self.clock())
                uow.audit.record(actor_id=principal.user_id, action="catalogue.product_retired",
                                 target_type="product", target_id=str(product_id),
                                 details={"previous_state": state.publication_state})
                uow.outbox.emit(event_type="catalogue.product_retired", aggregate_type="product",
                                aggregate_id=product_id, payload={})
            uow.commit()
        self.invalidate_facets()
        return self.staff_product(principal, product_id)

    def review_queue(self, principal: Principal, limit: int | None) -> list[dict]:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            return uow.publishing.review_queue(check_limit(limit))

    def staff_product(self, principal: Principal, product_id: uuid.UUID) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            ident = uow.publishing.product_identity(product_id)
            if ident is None:
                raise not_found("Product not found.")
            revs = uow.publishing.revisions_of(product_id)
        return {"id": str(ident["id"]), "publication_state": ident["publication_state"],
                "source": {"namespace": ident["namespace"], "name": ident["source_name"],
                           "external_id": ident["external_id"]},
                "gtin": ident["gtin"],
                "published_revision_id": _str(ident["published_revision_id"]),
                "current_revision_id": _str(ident["current_revision_id"]),
                "published_at": _iso(ident["published_at"]), "retired_at": _iso(ident["retired_at"]),
                "revisions": [{"id": str(r.id), "revision_no": r.revision_no, "facts": r.facts,
                               "annotations": r.annotations, "created_at": _iso(r.created_at)} for r in revs]}

    # ================================================================ collections
    def put_collection(self, principal: Principal, slug: str, title: str, product_ids: list[uuid.UUID]) -> dict:
        require(principal, Capability.INGEST_PRODUCTS)
        errors = []
        if not SLUG.fullmatch(slug):
            errors.append(FieldError("path.slug", "invalid", "Slug must match ^[a-z0-9][a-z0-9-]{1,62}$."))
        if not title.strip() or len(title) > 120:
            errors.append(FieldError("body.title", "invalid", "Title must be 1-120 characters."))
        if len(product_ids) > MAX_COLLECTION_ITEMS:
            errors.append(FieldError("body.product_ids", "too_many", f"At most {MAX_COLLECTION_ITEMS} products."))
        if len(set(product_ids)) != len(product_ids):
            errors.append(FieldError("body.product_ids", "duplicate", "A product may appear only once."))
        if errors:
            raise validation_failed(errors)
        with self.uow_factory() as uow:
            unknown = set(product_ids) - uow.publishing.existing_products(product_ids)
            if unknown:
                raise validation_failed([FieldError("body.product_ids", "unknown_product",
                                                    "Unknown products: " + ", ".join(sorted(map(str, unknown))))])
            uow.publishing.put_collection(slug, title.strip(), product_ids, self.clock())
            uow.audit.record(actor_id=principal.user_id, action="catalogue.collection_saved",
                             target_type="catalogue_collection", target_id=slug,
                             details={"title": title.strip(), "items": len(product_ids)})
            uow.commit()
            return uow.publishing.collection(slug, public=False)

    def delete_collection(self, principal: Principal, slug: str) -> None:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            if not uow.publishing.delete_collection(slug):
                raise not_found("Collection not found.")
            uow.audit.record(actor_id=principal.user_id, action="catalogue.collection_deleted",
                             target_type="catalogue_collection", target_id=slug, details={})
            uow.commit()

    def staff_collections(self, principal: Principal) -> list[dict]:
        require(principal, Capability.INGEST_PRODUCTS)
        with self.uow_factory() as uow:
            return uow.publishing.collections(public=False)

    # ================================================================ public browse
    def collections(self) -> list[dict]:
        with self.uow_factory() as uow:
            return uow.publishing.collections(public=True)

    def collection(self, slug: str) -> dict:
        with self.uow_factory() as uow:
            c = uow.publishing.collection(slug, public=True)
        if c is None:
            raise not_found("Collection not found.")
        return c

    def facets(self) -> dict:
        cached = self._facets
        if cached is not None and self.monotonic() - cached[0] < self.FACET_TTL_S:
            return cached[1]
        with self.uow_factory() as uow:
            data = uow.publishing.facets()
        self._facets = (self.monotonic(), data)
        return data

    def browse(self, query: BrowseQuery, *, limit: int | None, cursor: str | None) -> dict:
        if query.sort not in SORTS:
            raise validation_failed([FieldError("query.sort", "invalid", "sort must be newest or name.")])
        limit = check_limit(limit)
        fkey = json.dumps([query.q, query.category, query.colour, query.slot, query.sort,
                           [f"{a}:{b}" for a, b in query.sizes], bool(query.exclude)], separators=(",", ":"))
        after = None
        if cursor:
            raw = decode_keyset(self.ring, cursor, scope="catalogue.browse", filter_key=fkey)
            try:
                if len(raw) != 2:
                    raise ValueError
                after = [raw[0] if query.sort == "name" else datetime.fromisoformat(raw[0]), uuid.UUID(raw[1])]
            except (ValueError, TypeError):
                raise invalid_cursor() from None
        with self.uow_factory() as uow:
            rows = uow.publishing.browse(query, after, limit + 1)
            more, rows = len(rows) > limit, rows[:limit]
            index = SizeIndex.load(uow.sizes)
            sizes = uow.sizes.product_sizes([r.id for r in rows])
        nxt = None
        if more:
            last = rows[-1]
            key = (last.name or "").lower() if query.sort == "name" else last.published_at.isoformat()
            nxt = encode_keyset(self.ring, scope="catalogue.browse", filter_key=fkey, values=[key, str(last.id)])
        return {"items": [{"id": str(r.id), "name": r.name, "category": r.category, "colour": r.colour,
                           "slot": r.slot, "thumbnail": r.thumbnail, "published_at": _iso(r.published_at),
                           "sizes": [index.out(x.system, x.code)["label"] for x in sizes.get(r.id, [])]}
                          for r in rows],
                "next_cursor": nxt}

    def detail(self, product_id: uuid.UUID) -> dict:
        with self.uow_factory() as uow:
            ident = uow.publishing.product_identity(product_id)
            if ident is None or ident["publication_state"] != "published":
                raise not_found("Product not found.")
            rev = uow.publishing.revision_content(ident["published_revision_id"])
            objects = [{"id": str(m.id), "uri": f"/api/v2/media/{m.id}", "version": m.sha256[:12], "kind": m.kind,
                        "alt_text": m.alt_text} for m in uow.publishing.list_media(product_id)]
            media = objects + [{**x, "id": None, "kind": "source_reference", "alt_text": None}
                               for x in uow.publishing.public_media(rev.id)]
            index = SizeIndex.load(uow.sizes)
            sizes = uow.sizes.product_sizes([product_id]).get(product_id, [])
        return {"id": str(product_id), "revision_no": rev.revision_no,
                "facts": {k: {"value": v.get("value"), "source_field": v.get("source_field")}
                          for k, v in rev.facts.items()},
                "annotations": {k: {"value": v.get("value"), "origin": v.get("origin"), "note": v.get("note")}
                                for k, v in rev.annotations.items()},
                "source": {"namespace": ident["namespace"], "name": ident["source_name"],
                           "external_id": ident["external_id"]},
                "media": media, "published_at": _iso(ident["published_at"]),
                "one_size": not sizes,
                "sizes": [{**index.out(x.system, x.code), "origin": x.origin} for x in sizes]}


# ================================================================ product media objects (add-wearhouse-object-management)
MAX_ACTIVE_MEDIA = 20
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
RASTER_MAGIC = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}
GENERATED_RIGHTS = {"basis": "generated", "public_display": True, "note": "Generated placeholder, not a product photo."}


def sniff_raster(data: bytes) -> str | None:
    """JPEG / PNG / WebP by magic bytes only (never the client's claimed type). SVG is never accepted."""
    for ctype, magics in RASTER_MAGIC.items():
        if any(data.startswith(m) for m in magics):
            if ctype == "image/webp" and data[8:12] != b"WEBP":
                continue
            return ctype
    return None


def media_view(m: MediaRow) -> dict:
    return {"id": str(m.id), "product_id": str(m.product_id), "kind": m.kind, "content_type": m.content_type,
            "byte_size": m.byte_size, "sha256": m.sha256, "alt_text": m.alt_text, "position": m.position,
            "generator": m.generator, "rights": m.rights, "status": m.status, "url": f"/api/v2/media/{m.id}",
            "created_at": _iso(m.created_at), "removed_at": _iso(m.removed_at)}


class ProductMediaService:
    def __init__(self, uow_factory: Callable[[], CatalogueUoW], clock: Clock = utcnow,
                 on_change: Callable[[], None] | None = None):
        self.uow_factory = uow_factory
        self.clock = clock
        self.on_change = on_change or (lambda: None)

    def list(self, principal: Principal, product_id: uuid.UUID, include_removed: bool = False) -> list[dict]:
        require(principal, Capability.MANAGE_MEDIA)
        with self.uow_factory() as uow:
            if uow.publishing.browse_facts(product_id) is None:
                raise not_found("Product not found.")
            return [media_view(m) for m in uow.publishing.list_media(product_id, include_removed)]

    def _add(self, uow: CatalogueUoW, principal: Principal, product_id: uuid.UUID, *, kind: str, ctype: str,
             data: bytes, alt: str | None, rights: dict, generator: str | None) -> MediaRow:
        active = uow.publishing.lock_media_list(product_id)
        if len(active) >= MAX_ACTIVE_MEDIA:
            raise conflict("MEDIA_FULL", f"A product holds at most {MAX_ACTIVE_MEDIA} active media objects.")
        row = MediaRow(new_id(), product_id, kind, ctype, hashlib.sha256(data).hexdigest(), len(data),
                       (alt or "").strip()[:200] or None, max((m.position for m in active), default=-1) + 1, rights,
                       generator, "active", self.clock(), None, principal.user_id if principal else None)
        uow.publishing.insert_media(row, data)
        return row

    def _facts(self, uow: CatalogueUoW, product_id: uuid.UUID) -> dict:
        facts = uow.publishing.browse_facts(product_id)
        if facts is None:
            raise not_found("Product not found.")
        if facts["browse_name"] is None and facts["current_revision_id"]:  # draft: use its latest revision
            rev = uow.publishing.revision_content(facts["current_revision_id"])
            facts = {**browse_fields(rev), "current_revision_id": rev.id}
        return facts

    def generate(self, principal: Principal, product_id: uuid.UUID) -> dict:
        require(principal, Capability.MANAGE_MEDIA)
        with self.uow_factory() as uow:
            f = self._facts(uow, product_id)
            svg = placeholder_svg(name=f["browse_name"], category=f["browse_category"], colour=f["browse_colour"],
                                  slot=f["browse_slot"])
            row = self._add(uow, principal, product_id, kind="generated", ctype="image/svg+xml", data=svg,
                            alt=f"Generated placeholder for {f['browse_name'] or 'product'}", rights=GENERATED_RIGHTS,
                            generator=GENERATOR)
            uow.audit.record(actor_id=principal.user_id, action="catalogue.media_generated", target_type="product",
                             target_id=str(product_id), details={"media_id": str(row.id), "generator": GENERATOR})
            uow.commit()
        self.on_change()
        return media_view(row)

    def upload(self, principal: Principal, product_id: uuid.UUID, data: bytes, *, alt: str | None,
               rights_basis: str | None) -> dict:
        require(principal, Capability.MANAGE_MEDIA)
        if len(data) > MAX_UPLOAD_BYTES:
            raise validation_failed([FieldError("body", "too_large", "Images are at most 5 MB.")])
        ctype = sniff_raster(data)
        if ctype is None:
            raise validation_failed([FieldError("body", "not_an_image", "Upload a JPEG, PNG or WebP image.")])
        basis = (rights_basis or "").strip()
        if not basis:
            raise validation_failed([FieldError("query.rights_basis", "required",
                                                "State the rights basis for this image (e.g. own-photo, licensed).")])
        with self.uow_factory() as uow:
            self._facts(uow, product_id)
            row = self._add(uow, principal, product_id, kind="uploaded", ctype=ctype, data=data, alt=alt,
                            rights={"basis": basis[:200], "public_display": True}, generator=None)
            uow.audit.record(actor_id=principal.user_id, action="catalogue.media_uploaded", target_type="product",
                             target_id=str(product_id), details={"media_id": str(row.id), "bytes": len(data),
                                                                 "rights_basis": basis[:200]})
            uow.commit()
        self.on_change()
        return media_view(row)

    def update(self, principal: Principal, media_id: uuid.UUID, *, alt_text: str | None) -> dict:
        require(principal, Capability.MANAGE_MEDIA)
        with self.uow_factory() as uow:
            m = uow.publishing.get_media(media_id)
            if m is None or m.status != "active":
                raise not_found("Media not found.")
            uow.publishing.update_media(media_id, {"alt_text": (alt_text or "").strip()[:200] or None})
            uow.commit()
            return media_view(uow.publishing.get_media(media_id))

    def reorder(self, principal: Principal, product_id: uuid.UUID, media_ids: list[uuid.UUID]) -> list[dict]:
        require(principal, Capability.MANAGE_MEDIA)
        with self.uow_factory() as uow:
            active = uow.publishing.lock_media_list(product_id)
            if sorted(media_ids) != sorted(m.id for m in active):
                raise validation_failed([FieldError("body.media_ids", "mismatch",
                                                    "List every active media object of this product exactly once.")])
            for pos, mid in enumerate(media_ids):
                uow.publishing.update_media(mid, {"position": pos})
            uow.audit.record(actor_id=principal.user_id, action="catalogue.media_reordered", target_type="product",
                             target_id=str(product_id), details={"order": [str(m) for m in media_ids]})
            uow.commit()
            out = [media_view(m) for m in uow.publishing.list_media(product_id)]
        self.on_change()
        return out

    def remove(self, principal: Principal, media_id: uuid.UUID) -> None:
        require(principal, Capability.MANAGE_MEDIA)
        with self.uow_factory() as uow:
            m = uow.publishing.get_media(media_id)
            if m is None or m.status != "active":
                raise not_found("Media not found.")
            uow.publishing.update_media(media_id, {"status": "removed", "removed_at": self.clock()})
            uow.audit.record(actor_id=principal.user_id, action="catalogue.media_removed", target_type="product",
                             target_id=str(m.product_id), details={"media_id": str(media_id), "kind": m.kind})
            uow.commit()
        self.on_change()

    def generate_missing(self, principal: Principal, *, limit: int = 1000) -> dict:
        """One batch: a generated placeholder for each published product with no active media (idempotent)."""
        require(principal, Capability.MANAGE_MEDIA)
        if not 1 <= limit <= 5000:
            raise validation_failed([FieldError("query.limit", "out_of_range", "limit must be 1-5000.")])
        with self.uow_factory() as uow:
            todo = uow.publishing.products_without_media(limit)
            for f in todo:
                svg = placeholder_svg(name=f["browse_name"], category=f["browse_category"],
                                      colour=f["browse_colour"], slot=f["browse_slot"])
                uow.publishing.insert_media(MediaRow(
                    new_id(), f["id"], "generated", "image/svg+xml", hashlib.sha256(svg).hexdigest(), len(svg),
                    f"Generated placeholder for {f['browse_name'] or 'product'}", 0, GENERATED_RIGHTS, GENERATOR,
                    "active", self.clock(), None, principal.user_id), svg)
            if todo:
                uow.audit.record(actor_id=principal.user_id, action="catalogue.media_generated_bulk",
                                 target_type="product", target_id="*", details={"count": len(todo),
                                                                              "generator": GENERATOR})
            remaining = len(uow.publishing.products_without_media(1))
            uow.commit()
        if todo:
            self.on_change()
        return {"generated": len(todo), "more_remaining": bool(remaining)}

    def serve(self, viewer: Principal | None, media_id: uuid.UUID) -> dict:
        """Bytes + headers info; 404 unless active and (product published or viewer manages media)."""
        with self.uow_factory() as uow:
            r = uow.publishing.media_bytes(media_id)
        staff = viewer is not None and viewer.has(Capability.MANAGE_MEDIA)
        if r is None or r["status"] != "active" or (r["publication_state"] != "published" and not staff):
            raise not_found("Media not found.")
        return {"data": bytes(r["data"]), "content_type": r["content_type"], "sha256": r["sha256"],
                "public": r["publication_state"] == "published"}


__all__ = ["CataloguePublicationService", "HM_ARTICLES_V1", "parse_csv", "browse_fields", "chunk_csv"]
