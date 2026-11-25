from __future__ import annotations

from sqlalchemy import Text, delete, desc, func, insert, literal, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ...platform.ids import new_id
from ..domain import SourceProductInput, revision_content
from ..ports import (BrowseRow, MediaRow, ProductRow, ProductState, RevisionContent, RevisionRow,
                     RevisionSummary)
from .tables import (catalogue_collection, catalogue_collection_item, catalogue_import_job, catalogue_import_row,
                     product_media,
                     catalogue_source, media_reference, product, product_revision, product_variant,
                     source_snapshot)


class SqlCatalogueRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def ensure_source(self, namespace, name, url):
        self.conn.execute(pg_insert(catalogue_source).values(id=new_id(), namespace=namespace, name=name, url=url)
                          .on_conflict_do_nothing(index_elements=["namespace"]))
        return self.conn.execute(select(catalogue_source.c.id)
                                 .where(catalogue_source.c.namespace == namespace)).scalar_one()

    def ensure_snapshot(self, source_id, inp: SourceProductInput):
        s = inp.snapshot
        self.conn.execute(pg_insert(source_snapshot).values(
            id=new_id(), source_id=source_id, sha256=s.sha256, file_name=s.file_name, acquired_on=s.acquired_on,
            permission=inp.permission.as_record()).on_conflict_do_nothing(index_elements=["source_id", "sha256"]))
        return self.conn.execute(select(source_snapshot.c.id).where(
            source_snapshot.c.source_id == source_id, source_snapshot.c.sha256 == s.sha256)).scalar_one()

    def lock_product(self, source_id, external_id, gtin, now):
        candidate = new_id()
        values = dict(id=candidate, source_id=source_id, external_id=external_id, created_at=now)
        if gtin is not None:
            values.update(gtin=gtin.value, gtin_scheme=gtin.scheme, gtin_evidence=gtin.evidence)
        self.conn.execute(pg_insert(product).values(**values)
                          .on_conflict_do_nothing(index_elements=["source_id", "external_id"]))
        row = self.conn.execute(select(product.c.id, product.c.gtin, product.c.current_revision_id).where(
            product.c.source_id == source_id, product.c.external_id == external_id).with_for_update()).one()
        if gtin is not None and row.gtin is None and row.id != candidate:
            self.conn.execute(update(product).where(product.c.id == row.id)
                              .values(gtin=gtin.value, gtin_scheme=gtin.scheme, gtin_evidence=gtin.evidence))
            row = row._replace(gtin=gtin.value)
        return ProductRow(row.id, row.gtin, row.current_revision_id), row.id == candidate

    def latest_revision(self, product_id):
        r = self.conn.execute(select(product_revision.c.id, product_revision.c.revision_no,
                                     product_revision.c.content_digest)
                              .where(product_revision.c.product_id == product_id)
                              .order_by(product_revision.c.revision_no.desc()).limit(1)).one_or_none()
        return RevisionRow(r.id, r.revision_no, r.content_digest) if r else None

    def add_revision(self, *, product_id, revision_no, snapshot_id, digest, inp, created_by, now):
        content = revision_content(inp)
        rid = new_id()
        self.conn.execute(insert(product_revision).values(
            id=rid, product_id=product_id, revision_no=revision_no, snapshot_id=snapshot_id, content_digest=digest,
            original_fields=content["original_fields"], facts=content["facts"], annotations=content["annotations"],
            created_by=created_by, created_at=now))
        if inp.variants:
            self.conn.execute(insert(product_variant), [
                {"id": new_id(), "revision_id": rid, "variant_key": v["key"], "facts": v["facts"]}
                for v in content["variants"]])
        if inp.media:
            self.conn.execute(insert(media_reference), [
                {"id": new_id(), "revision_id": rid, "uri": m["uri"], "media_version": m["version"],
                 "rights": m["rights"], "created_at": now} for m in content["media"]])
        self.conn.execute(update(product).where(product.c.id == product_id).values(current_revision_id=rid))
        return rid


class SqlRevisionReader:
    """Catalogue's read interface for other modules (ownership)."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def _query(self):
        return (select(product.c.id.label("product_id"), product_revision.c.id.label("revision_id"),
                       product_revision.c.revision_no, catalogue_source.c.namespace, product.c.external_id,
                       source_snapshot.c.sha256, product.c.catalogue_status, product_revision.c.facts)
                .select_from(product_revision.join(product, product.c.id == product_revision.c.product_id)
                             .join(catalogue_source, catalogue_source.c.id == product.c.source_id)
                             .join(source_snapshot, source_snapshot.c.id == product_revision.c.snapshot_id)))

    @staticmethod
    def _summary(r) -> RevisionSummary:
        return RevisionSummary(product_id=r.product_id, revision_id=r.revision_id, revision_no=r.revision_no,
                               source_namespace=r.namespace, external_id=r.external_id, snapshot_sha256=r.sha256,
                               catalogue_status=r.catalogue_status,
                               facts={k: v["value"] for k, v in (r.facts or {}).items()})

    def current_for_product(self, product_id):
        r = self.conn.execute(self._query().where(product.c.id == product_id,
                                                  product_revision.c.id == product.c.current_revision_id)
                              ).one_or_none()
        return self._summary(r) if r else None

    def published_for_product(self, product_id):
        r = self.conn.execute(self._query().where(product.c.id == product_id,
                                                  product_revision.c.id == product.c.published_revision_id)
                              ).one_or_none()
        return self._summary(r) if r else None

    def by_revision(self, revision_id):
        r = self.conn.execute(self._query().where(product_revision.c.id == revision_id)).one_or_none()
        return self._summary(r) if r else None

    def on_sale(self, product_ids):
        """Published, non-retired products -> their published revision summary (batch, for commerce)."""
        if not product_ids:
            return {}
        rows = self.conn.execute(self._query().where(product.c.id.in_(list(product_ids)),
                                                     product.c.publication_state == "published",
                                                     product_revision.c.id == product.c.published_revision_id)).all()
        return {r.product_id: self._summary(r) for r in rows}

    def published_ids(self, category, slot):
        q = select(product.c.id).where(product.c.publication_state == "published")
        if category:
            q = q.where(product.c.browse_category == category)
        if slot:
            q = q.where(product.c.browse_slot == slot)
        return list(self.conn.execute(q.order_by(product.c.id)).scalars())

    def annotations_for(self, revision_ids):
        if not revision_ids:
            return {}
        rows = self.conn.execute(select(product_revision.c.id, product_revision.c.annotations)
                                 .where(product_revision.c.id.in_(list(revision_ids)))).all()
        return {r.id: (r.annotations or {}) for r in rows}


def _content(r) -> RevisionContent:
    return RevisionContent(r.id, r.product_id, r.revision_no, r.facts or {}, r.annotations or {}, r.created_at)


def like_pattern(text: str) -> str:
    """Literal substring match: user input never acts as a wildcard (escape char is backslash)."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


PUBLIC_MEDIA = media_reference.c.rights["public_display"].as_boolean().is_(True)


def media_path(media_id) -> str:
    return f"/api/v2/media/{media_id}"


def _media(r) -> MediaRow:
    return MediaRow(r.id, r.product_id, r.kind, r.content_type, r.sha256, r.byte_size, r.alt_text, r.position,
                    r.rights, r.generator, r.status, r.created_at, r.removed_at)


_MEDIA_META = [c for c in product_media.c if c.name != "data"]  # never load bytes for listings


def _media_thumbs_impl(conn, product_ids):
    if not product_ids:
        return {}
    rows = conn.execute(select(product_media.c.product_id, product_media.c.id)
                        .where(product_media.c.product_id.in_(list(product_ids)), product_media.c.status == "active")
                        .order_by(product_media.c.product_id, product_media.c.position, product_media.c.created_at)).all()
    out = {}
    for r in rows:
        out.setdefault(r.product_id, media_path(r.id))
    return out


class _MediaMixin:
    """Product media objects (add-wearhouse-object-management D1)."""

    def _media_thumbs(self, product_ids):
        return _media_thumbs_impl(self.conn, product_ids)

    def list_media(self, product_id, include_removed=False):
        q = select(*_MEDIA_META).where(product_media.c.product_id == product_id)
        if not include_removed:
            q = q.where(product_media.c.status == "active")
        return [_media(r) for r in self.conn.execute(q.order_by(product_media.c.status, product_media.c.position,
                                                                product_media.c.created_at))]

    def lock_media_list(self, product_id):
        self.conn.execute(select(product.c.id).where(product.c.id == product_id).with_for_update())
        return self.list_media(product_id)

    def insert_media(self, row: MediaRow, data: bytes):
        self.conn.execute(insert(product_media).values(
            id=row.id, product_id=row.product_id, kind=row.kind, content_type=row.content_type, data=data,
            sha256=row.sha256, byte_size=row.byte_size, alt_text=row.alt_text, position=row.position,
            rights=row.rights, generator=row.generator, status="active", created_by=None if row.created_by is None
            else row.created_by, created_at=row.created_at))

    def get_media(self, media_id):
        r = self.conn.execute(select(*_MEDIA_META).where(product_media.c.id == media_id)).one_or_none()
        return _media(r) if r else None

    def media_bytes(self, media_id):
        r = self.conn.execute(select(product_media.c.data, product_media.c.content_type, product_media.c.sha256,
                                     product_media.c.status, product.c.publication_state)
                              .select_from(product_media.join(product, product.c.id == product_media.c.product_id))
                              .where(product_media.c.id == media_id)).one_or_none()
        return dict(r._mapping) if r else None

    def update_media(self, media_id, values):
        self.conn.execute(update(product_media).where(product_media.c.id == media_id).values(**values))

    def products_without_media(self, limit):
        has = select(product_media.c.id).where(product_media.c.product_id == product.c.id,
                                               product_media.c.status == "active").exists()
        rows = self.conn.execute(select(product.c.id, product.c.browse_name, product.c.browse_category,
                                        product.c.browse_colour, product.c.browse_slot)
                                 .where(product.c.publication_state == "published", ~has)
                                 .order_by(product.c.id).limit(limit)).all()
        return [dict(r._mapping) for r in rows]

    def browse_facts(self, product_id):
        r = self.conn.execute(select(product.c.browse_name, product.c.browse_category, product.c.browse_colour,
                                     product.c.browse_slot, product.c.current_revision_id)
                              .where(product.c.id == product_id)).one_or_none()
        return dict(r._mapping) if r else None



class _ServingMixin:
    """Recommendation serving reads (complete-wearhouse-research-intelligence)."""

    def cards(self, product_ids):
        if not product_ids:
            return []
        rows = self.conn.execute(select(product.c.id, product.c.browse_name, product.c.browse_category,
                                        product.c.browse_colour, product.c.browse_slot, product.c.published_revision_id)
                                 .where(product.c.id.in_(list(product_ids)), product.c.publication_state == "published")
                                 ).all()
        media = self._media_thumbs([r.id for r in rows])
        refs = self._thumbs([r.published_revision_id for r in rows])
        by = {r.id: {"id": str(r.id), "name": r.browse_name, "category": r.browse_category, "colour": r.browse_colour,
                     "slot": r.browse_slot, "thumbnail": media.get(r.id) or refs.get(r.published_revision_id)} for r in rows}
        return [by[i] for i in product_ids if i in by]  # keep ranking order; drop unpublished

    def similar_by_content(self, product_id, limit):
        me = self.conn.execute(select(product.c.browse_category, product.c.browse_text)
                               .where(product.c.id == product_id)).one_or_none()
        if me is None or me.browse_category is None:
            return []
        sim = func.similarity(product.c.browse_text, me.browse_text)
        rows = self.conn.execute(select(product.c.id).where(product.c.publication_state == "published",
                                                            product.c.browse_category == me.browse_category,
                                                            product.c.id != product_id)
                                 .order_by(sim.desc(), product.c.id).limit(limit))
        return list(rows.scalars())

    def newest_published(self, limit, exclude):
        q = select(product.c.id).where(product.c.publication_state == "published")
        if exclude:
            q = q.where(product.c.id.not_in(list(exclude)))
        return list(self.conn.execute(q.order_by(product.c.published_at.desc(), product.c.id.desc()).limit(limit)).scalars())

    def products_by_external(self, namespace, external_ids):
        out = {}
        for i in range(0, len(external_ids), 5000):
            rows = self.conn.execute(select(product.c.external_id, product.c.id)
                                     .select_from(product.join(catalogue_source, catalogue_source.c.id == product.c.source_id))
                                     .where(catalogue_source.c.namespace == namespace,
                                            product.c.external_id.in_(external_ids[i:i + 5000])))
            out.update({r.external_id: r.id for r in rows})
        return out


class SqlCataloguePublishing(_MediaMixin, _ServingMixin):
    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------ import jobs
    def create_import_job(self, *, job_id, source_id, snapshot_id, mapping, row_count, created_by, now):
        self.conn.execute(insert(catalogue_import_job).values(
            id=job_id, source_id=source_id, snapshot_id=snapshot_id, mapping_version=mapping, status="running",
            row_count=row_count, created_by=created_by, created_at=now))

    def add_import_row(self, *, job_id, row_no, external_id, outcome, product_id, revision_no, errors):
        self.conn.execute(insert(catalogue_import_row).values(
            job_id=job_id, row_no=row_no, external_id=external_id, outcome=outcome, product_id=product_id,
            revision_no=revision_no, errors=errors))

    def complete_import_job(self, job_id, totals, now):
        self.conn.execute(update(catalogue_import_job).where(catalogue_import_job.c.id == job_id)
                          .values(status="completed", totals=totals, completed_at=now))

    def get_import_job(self, job_id):
        j = self.conn.execute(
            select(catalogue_import_job, catalogue_source.c.namespace)
            .select_from(catalogue_import_job.join(catalogue_source,
                                                   catalogue_source.c.id == catalogue_import_job.c.source_id))
            .where(catalogue_import_job.c.id == job_id)).one_or_none()
        if j is None:
            return None
        rows = self.conn.execute(select(catalogue_import_row).where(catalogue_import_row.c.job_id == job_id)
                                 .order_by(catalogue_import_row.c.row_no)).all()
        return {"id": str(j.id), "namespace": j.namespace, "mapping_version": j.mapping_version, "status": j.status,
                "row_count": j.row_count, "totals": j.totals, "created_at": j.created_at,
                "completed_at": j.completed_at,
                "rows": [{"row_no": r.row_no, "external_id": r.external_id, "outcome": r.outcome,
                          "product_id": str(r.product_id) if r.product_id else None, "revision_no": r.revision_no,
                          "errors": r.errors} for r in rows]}

    # ------------------------------------------------------------------ publication
    def lock_product_state(self, product_id):
        r = self.conn.execute(select(product.c.id, product.c.publication_state, product.c.published_revision_id,
                                     product.c.current_revision_id, product.c.published_at)
                              .where(product.c.id == product_id).with_for_update()).one_or_none()
        return ProductState(r.id, r.publication_state, r.published_revision_id, r.current_revision_id,
                            r.published_at) if r else None

    def revision_content(self, revision_id):
        r = self.conn.execute(select(product_revision).where(product_revision.c.id == revision_id)).one_or_none()
        return _content(r) if r else None

    def revisions_of(self, product_id):
        rows = self.conn.execute(select(product_revision).where(product_revision.c.product_id == product_id)
                                 .order_by(product_revision.c.revision_no)).all()
        return [_content(r) for r in rows]

    def product_identity(self, product_id):
        r = self.conn.execute(
            select(product.c.id, product.c.external_id, product.c.publication_state, product.c.published_revision_id,
                   product.c.current_revision_id, product.c.published_at, product.c.retired_at, product.c.gtin,
                   catalogue_source.c.namespace, catalogue_source.c.name.label("source_name"))
            .select_from(product.join(catalogue_source, catalogue_source.c.id == product.c.source_id))
            .where(product.c.id == product_id)).one_or_none()
        return dict(r._mapping) if r else None

    def set_published(self, product_id, revision_id, browse, now):
        self.conn.execute(update(product).where(product.c.id == product_id).values(
            publication_state="published", catalogue_status="active", published_revision_id=revision_id,
            published_at=func.coalesce(product.c.published_at, now), retired_at=None, **browse))

    def set_retired(self, product_id, now):
        self.conn.execute(update(product).where(product.c.id == product_id).values(
            publication_state="retired", catalogue_status="retired", retired_at=now))

    def review_queue(self, limit):
        published = product_revision.alias("published")
        q = (select(product.c.id, product.c.external_id, product.c.publication_state, catalogue_source.c.namespace,
                    product_revision.c.revision_no.label("latest_revision_no"), product_revision.c.facts,
                    published.c.revision_no.label("published_revision_no"))
             .select_from(product.join(catalogue_source, catalogue_source.c.id == product.c.source_id)
                          .join(product_revision, product_revision.c.id == product.c.current_revision_id)
                          .outerjoin(published, published.c.id == product.c.published_revision_id))
             .where(product.c.publication_state != "retired",
                    or_(product.c.published_revision_id.is_(None),
                        product.c.published_revision_id != product.c.current_revision_id))
             .order_by(product.c.created_at, product.c.id).limit(limit))
        return [{"product_id": str(r.id), "namespace": r.namespace, "external_id": r.external_id,
                 "publication_state": r.publication_state, "latest_revision_no": r.latest_revision_no,
                 "published_revision_no": r.published_revision_no,
                 "name": (r.facts or {}).get("product_name", {}).get("value")}
                for r in self.conn.execute(q).all()]

    # ------------------------------------------------------------------ browse
    def _thumbs(self, revision_ids):
        ids = [i for i in revision_ids if i is not None]
        if not ids:
            return {}
        rows = self.conn.execute(select(media_reference.c.revision_id, media_reference.c.uri)
                                 .where(media_reference.c.revision_id.in_(ids), PUBLIC_MEDIA)
                                 .order_by(media_reference.c.created_at, media_reference.c.uri)).all()
        out = {}
        for r in rows:
            out.setdefault(r.revision_id, r.uri)
        return out

    def browse(self, query, after, limit):
        q = (select(product.c.id, product.c.browse_name, product.c.browse_category, product.c.browse_colour,
                    product.c.browse_slot, product.c.published_at, product.c.published_revision_id)
             .where(product.c.publication_state == "published"))
        if query.q:
            q = q.where(product.c.browse_text.like(like_pattern(query.q.lower()), escape="\\"))
        if query.category:
            q = q.where(product.c.browse_category == query.category)
        if query.colour:
            q = q.where(product.c.browse_colour == query.colour)
        if query.slot:
            q = q.where(product.c.browse_slot == query.slot)
        if query.exclude:  # complete-wearhouse-tdd: hide the caller's owned products
            q = q.where(product.c.id.not_in(list(query.exclude)))
        if query.sizes:  # add-wearhouse-sizes: available in ANY of the requested sizes (0012 browse_sizes)
            q = q.where(product.c.browse_sizes.overlap(literal([f"{s}:{c}" for s, c in query.sizes], ARRAY(Text))))
        if query.sort == "name":
            key = (func.lower(func.coalesce(product.c.browse_name, "")), product.c.id)
            if after is not None:
                q = q.where(tuple_(*key) > tuple_(literal(after[0]), literal(after[1], product.c.id.type)))
            q = q.order_by(*key)
        else:
            if after is not None:
                q = q.where(tuple_(product.c.published_at, product.c.id) <
                            tuple_(literal(after[0], product.c.published_at.type),
                                   literal(after[1], product.c.id.type)))
            q = q.order_by(desc(product.c.published_at), desc(product.c.id))
        rows = self.conn.execute(q.limit(limit)).all()
        thumbs = self._thumbs([r.published_revision_id for r in rows])
        media = self._media_thumbs([r.id for r in rows])
        return [BrowseRow(r.id, r.browse_name, r.browse_category, r.browse_colour, r.browse_slot, r.published_at,
                          media.get(r.id) or thumbs.get(r.published_revision_id)) for r in rows]

    def facets(self):
        out = {}
        for name, col in (("category", product.c.browse_category), ("colour", product.c.browse_colour),
                          ("slot", product.c.browse_slot)):
            n = func.count().label("n")
            rows = self.conn.execute(select(col, n).where(product.c.publication_state == "published", col.is_not(None))
                                     .group_by(col).order_by(desc(n), col)).all()
            out[name] = [{"value": v, "count": c} for v, c in rows]
        return out

    def public_media(self, revision_id):
        rows = self.conn.execute(select(media_reference.c.uri, media_reference.c.media_version)
                                 .where(media_reference.c.revision_id == revision_id, PUBLIC_MEDIA)
                                 .order_by(media_reference.c.created_at, media_reference.c.uri)).all()
        return [{"uri": r.uri, "version": r.media_version} for r in rows]

    # ------------------------------------------------------------------ collections
    def _items(self, collection_id, public):
        q = (select(catalogue_collection_item.c.product_id, product.c.browse_name, product.c.publication_state,
                    product.c.browse_category, product.c.browse_colour, product.c.browse_slot,
                    product.c.published_revision_id)
             .select_from(catalogue_collection_item.join(product,
                                                         product.c.id == catalogue_collection_item.c.product_id))
             .where(catalogue_collection_item.c.collection_id == collection_id)
             .order_by(catalogue_collection_item.c.position))
        if public:
            q = q.where(product.c.publication_state == "published")
        rows = self.conn.execute(q).all()
        thumbs = self._thumbs([r.published_revision_id for r in rows])
        media = self._media_thumbs([r.product_id for r in rows])
        out = []
        for r in rows:
            item = {"id": str(r.product_id), "name": r.browse_name, "category": r.browse_category,
                    "colour": r.browse_colour, "slot": r.browse_slot,
                    "thumbnail": media.get(r.product_id) or thumbs.get(r.published_revision_id)}
            if not public:
                item["publication_state"] = r.publication_state
            out.append(item)
        return out

    def collections(self, *, public):
        rows = self.conn.execute(select(catalogue_collection)
                                 .order_by(catalogue_collection.c.title, catalogue_collection.c.slug)).all()
        return [{"slug": r.slug, "title": r.title, "items": self._items(r.id, public)} for r in rows]

    def collection(self, slug, *, public):
        r = self.conn.execute(select(catalogue_collection).where(catalogue_collection.c.slug == slug)).one_or_none()
        return {"slug": r.slug, "title": r.title, "items": self._items(r.id, public)} if r else None

    def put_collection(self, slug, title, product_ids, now):
        stmt = pg_insert(catalogue_collection).values(id=new_id(), slug=slug, title=title, created_at=now,
                                                     updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["slug"],
                                                     set_={"title": title, "updated_at": now}))
        cid = self.conn.execute(select(catalogue_collection.c.id).where(catalogue_collection.c.slug == slug)
                                .with_for_update()).scalar_one()
        self.conn.execute(delete(catalogue_collection_item).where(catalogue_collection_item.c.collection_id == cid))
        if product_ids:
            self.conn.execute(insert(catalogue_collection_item), [
                {"collection_id": cid, "product_id": pid, "position": i} for i, pid in enumerate(product_ids)])

    def delete_collection(self, slug):
        cid = self.conn.execute(select(catalogue_collection.c.id).where(catalogue_collection.c.slug == slug)
                                ).scalar_one_or_none()
        if cid is None:
            return False
        self.conn.execute(delete(catalogue_collection_item).where(catalogue_collection_item.c.collection_id == cid))
        self.conn.execute(delete(catalogue_collection).where(catalogue_collection.c.id == cid))
        return True

    def existing_products(self, product_ids):
        if not product_ids:
            return set()
        return set(self.conn.execute(select(product.c.id).where(product.c.id.in_(product_ids))).scalars())


