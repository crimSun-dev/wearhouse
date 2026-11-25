from __future__ import annotations

import uuid
from datetime import date
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from ..identity.api import current_principal
from ..identity.domain import Principal
from ..platform.errors import unauthenticated
from .domain import (Annotation, Fact, Gtin, MediaRef, Permission, SnapshotRef, SourceProductInput, SourceRef,
                     Variant, parse_size_param)
from .mapping import HM_ARTICLES_V1, JobContext
from .ports import BrowseQuery

ScalarIn = Union[StrictStr, StrictBool, StrictInt, StrictFloat]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceIn(_Strict):
    namespace: StrictStr = Field(max_length=63)
    name: StrictStr = Field(max_length=200)
    url: StrictStr = Field(max_length=2048)


class SnapshotIn(_Strict):
    sha256: StrictStr = Field(min_length=64, max_length=64)
    file_name: StrictStr = Field(max_length=255)
    acquired_on: date


class PermissionIn(_Strict):
    basis: StrictStr = Field(max_length=200)
    scope: StrictStr = Field(max_length=500)
    accepted_on: date
    accepted_by: StrictStr = Field(max_length=200)
    terms_url: StrictStr = Field(max_length=2048)


class FactIn(_Strict):
    value: ScalarIn
    source_field: StrictStr = Field(max_length=100)


class AnnotationIn(_Strict):
    value: ScalarIn
    origin: StrictStr
    note: Optional[StrictStr] = Field(default=None, max_length=500)


class GtinIn(_Strict):
    value: StrictStr = Field(max_length=14)
    scheme: StrictStr = "gs1"
    evidence: StrictStr = Field(max_length=500)


class MediaIn(_Strict):
    uri: StrictStr = Field(max_length=2048)
    version: StrictStr = Field(max_length=100)
    rights: dict[str, ScalarIn]


class VariantIn(_Strict):
    key: StrictStr = Field(max_length=100)
    facts: dict[str, FactIn]


class SourceProductIn(_Strict):
    """One source-backed product. `external_id` must be a JSON string so leading zeros survive."""

    source: SourceIn
    snapshot: SnapshotIn
    permission: PermissionIn
    external_id: StrictStr = Field(max_length=64)
    original_fields: dict[str, Optional[ScalarIn]]
    facts: dict[str, FactIn]
    annotations: dict[str, AnnotationIn] = Field(default_factory=dict)
    gtin: Optional[GtinIn] = None
    media: list[MediaIn] = Field(default_factory=list, max_length=20)
    variants: list[VariantIn] = Field(default_factory=list, max_length=100)

    def to_domain(self) -> SourceProductInput:
        return SourceProductInput(
            source=SourceRef(**self.source.model_dump()),
            snapshot=SnapshotRef(**self.snapshot.model_dump()),
            permission=Permission(**self.permission.model_dump()),
            external_id=self.external_id,
            original_fields=dict(self.original_fields),
            facts={k: Fact(**v.model_dump()) for k, v in self.facts.items()},
            annotations={k: Annotation(**v.model_dump()) for k, v in self.annotations.items()},
            gtin=Gtin(**self.gtin.model_dump()) if self.gtin else None,
            media=tuple(MediaRef(**m.model_dump()) for m in self.media),
            variants=tuple(Variant(v.key, {k: Fact(**f.model_dump()) for k, f in v.facts.items()})
                           for v in self.variants),
        )


class IngestOut(BaseModel):
    product_id: str
    revision_id: str
    revision_no: int
    product_created: bool
    revision_created: bool


router = APIRouter(tags=["admin: catalogue"])


@router.post("/admin/source-products", response_model=IngestOut, status_code=201,
             summary="Ingest one permitted source-backed product (catalogue_editor or admin)",
             responses={200: {"model": IngestOut, "description": "Existing product; revision reused or added"}})
def ingest_source_product(body: SourceProductIn, request: Request, response: Response,
                          principal: Principal = Depends(current_principal)) -> IngestOut:
    r = request.app.state.services.catalogue.ingest(principal, body.to_domain())
    if not r.product_created:
        response.status_code = 200
    return IngestOut(product_id=str(r.product_id), revision_id=str(r.revision_id), revision_no=r.revision_no,
                     product_created=r.product_created, revision_created=r.revision_created)


# =============================================================================== publish-wearhouse-catalogue
class ImportJobIn(_Strict):
    """A bulk import of source rows in the source's own CSV format. Every row is processed independently."""

    source: SourceIn
    snapshot: SnapshotIn
    permission: PermissionIn
    mapping: StrictStr = HM_ARTICLES_V1
    csv: StrictStr = Field(max_length=10 * 1024 * 1024)


class ImportRowOut(BaseModel):
    row_no: int
    external_id: Optional[str]
    outcome: Literal["created", "revised", "unchanged", "rejected"]
    product_id: Optional[str]
    revision_no: Optional[int]
    errors: list[dict]


class ImportJobOut(BaseModel):
    id: str
    namespace: str
    mapping_version: str
    status: str
    row_count: int
    totals: dict[str, int]
    created_at: str
    completed_at: Optional[str]
    rows: list[ImportRowOut]


class PublishIn(_Strict):
    revision_id: uuid.UUID


class RevisionOut(BaseModel):
    id: str
    revision_no: int
    facts: dict
    annotations: dict
    created_at: str


class SourceIdentityOut(BaseModel):
    namespace: str
    name: str
    external_id: str


class StaffProductOut(BaseModel):
    id: str
    publication_state: Literal["draft", "published", "retired"]
    source: SourceIdentityOut
    gtin: Optional[str]
    published_revision_id: Optional[str]
    current_revision_id: Optional[str]
    published_at: Optional[str]
    retired_at: Optional[str]
    revisions: list[RevisionOut]


class ReviewItemOut(BaseModel):
    product_id: str
    namespace: str
    external_id: str
    publication_state: str
    latest_revision_no: int
    published_revision_no: Optional[int]
    name: Optional[str]


class CollectionIn(_Strict):
    title: StrictStr = Field(max_length=120)
    product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class CardOut(BaseModel):
    id: str
    name: Optional[str]
    category: Optional[str]
    colour: Optional[str]
    slot: Optional[str]
    thumbnail: Optional[str]


class StaffCardOut(CardOut):
    publication_state: str


class CollectionOut(BaseModel):
    slug: str
    title: str
    items: list[CardOut]


class StaffCollectionOut(BaseModel):
    slug: str
    title: str
    items: list[StaffCardOut]


class BrowseItemOut(CardOut):
    published_at: str
    sizes: list[str] = []  # size labels in rank order; empty = one size (add-wearhouse-sizes)


class BrowsePageOut(BaseModel):
    items: list[BrowseItemOut]
    next_cursor: Optional[str]


class FacetValueOut(BaseModel):
    value: str
    count: int


class FacetsOut(BaseModel):
    category: list[FacetValueOut]
    colour: list[FacetValueOut]
    slot: list[FacetValueOut]


class FactOut(BaseModel):
    value: Union[str, bool, int, float, None]
    source_field: Optional[str]


class AnnotationOut(BaseModel):
    value: Union[str, bool, int, float, None]
    origin: Optional[str]
    note: Optional[str]


class MediaOut(BaseModel):
    uri: str
    version: str
    id: Optional[str] = None
    kind: Optional[str] = None  # generated | uploaded | source_reference
    alt_text: Optional[str] = None


class ProductDetailOut(BaseModel):
    id: str
    revision_no: int
    facts: dict[str, FactOut]
    annotations: dict[str, AnnotationOut]
    source: SourceIdentityOut
    media: list[MediaOut]
    published_at: str
    one_size: bool
    sizes: list["ProductSizeOut"]


def _optional_viewer(request: Request) -> Optional[Principal]:
    """Anonymous without an Authorization header; a present but invalid token is still a 401."""
    if not request.headers.get("authorization"):
        return None
    return current_principal(request)


def _pub(request: Request):
    return request.app.state.services.publication


@router.post("/admin/catalogue/import-jobs", response_model=ImportJobOut, status_code=201,
             summary="Run a bulk import job over source CSV rows (catalogue_editor or admin)")
def run_import(body: ImportJobIn, request: Request, principal: Principal = Depends(current_principal)):
    ctx = JobContext(SourceRef(**body.source.model_dump()), SnapshotRef(**body.snapshot.model_dump()),
                     Permission(**body.permission.model_dump()))
    return _pub(request).run_import(principal, ctx, body.mapping, body.csv)


@router.get("/admin/catalogue/import-jobs/{job_id}", response_model=ImportJobOut, summary="Read an import job")
def read_import(job_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _pub(request).import_job(principal, job_id)


class JobPublishOut(BaseModel):
    job_id: str
    published: int
    already_published: int
    retired_skipped: int


@router.post("/admin/catalogue/import-jobs/{job_id}/publish", response_model=JobPublishOut,
             summary="Publish the latest revision of every product in an import job (retired stay retired)")
def publish_job(job_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _pub(request).publish_job(principal, job_id)


@router.get("/admin/catalogue/review", response_model=list[ReviewItemOut],
            summary="Products whose latest revision is not published")
def review_queue(request: Request, limit: Optional[int] = Query(None),
                 principal: Principal = Depends(current_principal)):
    return _pub(request).review_queue(principal, limit)


@router.get("/admin/catalogue/products/{product_id}", response_model=StaffProductOut,
            summary="Staff product detail with every revision")
def staff_product(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _pub(request).staff_product(principal, product_id)


@router.post("/admin/catalogue/products/{product_id}/publish", response_model=StaffProductOut,
             summary="Publish a specific revision")
def publish(product_id: uuid.UUID, body: PublishIn, request: Request,
            principal: Principal = Depends(current_principal)):
    return _pub(request).publish(principal, product_id, body.revision_id)


@router.post("/admin/catalogue/products/{product_id}/retire", response_model=StaffProductOut,
             summary="Retire a product (hidden from browse; owned items and lookups remain)")
def retire(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _pub(request).retire(principal, product_id)


@router.get("/admin/catalogue/collections", response_model=list[StaffCollectionOut],
            summary="All collections including unpublished members")
def staff_collections(request: Request, principal: Principal = Depends(current_principal)):
    return _pub(request).staff_collections(principal)


@router.put("/admin/catalogue/collections/{slug}", response_model=StaffCollectionOut,
            summary="Create or replace a collection (title and ordered products)")
def put_collection(slug: str, body: CollectionIn, request: Request,
                   principal: Principal = Depends(current_principal)):
    return _pub(request).put_collection(principal, slug, body.title, body.product_ids)


@router.delete("/admin/catalogue/collections/{slug}", status_code=204, summary="Delete a collection")
def delete_collection(slug: str, request: Request, principal: Principal = Depends(current_principal)):
    _pub(request).delete_collection(principal, slug)
    return Response(status_code=204)


public_router = APIRouter(tags=["catalogue"])


@public_router.get("/catalogue/products", response_model=BrowsePageOut,
                   summary="Browse and search published products")
def browse(request: Request, q: Optional[str] = Query(None, max_length=100),
           category: Optional[str] = Query(None, max_length=100), colour: Optional[str] = Query(None, max_length=100),
           slot: Optional[str] = Query(None, max_length=32), sort: str = Query("newest", max_length=16),
           size: Optional[str] = Query(None, max_length=48, description="system:code, e.g. alpha:M"),
           my_sizes: bool = Query(False, description="only products in your usual sizes (signed in)"),
           hide_owned: bool = Query(False, description="leave out products you own (signed in)"),
           limit: Optional[int] = Query(None), cursor: Optional[str] = Query(None, max_length=1024),
           viewer: Optional[Principal] = Depends(_optional_viewer)):
    sizes: tuple = ()
    if size:
        sizes = (parse_size_param(size, "query.size"),)
    if my_sizes:
        sizes = sizes + request.app.state.services.sizing.browse_refs(viewer)
    exclude: tuple = ()
    if hide_owned:
        if viewer is None:
            raise unauthenticated("Sign in to hide products you own.")
        exclude = tuple(sorted(request.app.state.services.owned_items.owned_product_ids(viewer)))
    query = BrowseQuery(q=(q or "").strip() or None, category=category or None, colour=colour or None,
                        slot=slot or None, sort=sort, sizes=tuple(sorted(set(sizes))), exclude=exclude)
    return _pub(request).browse(query, limit=limit, cursor=cursor)


@public_router.get("/catalogue/products/{product_id}", response_model=ProductDetailOut,
                   summary="Published product detail")
def detail(product_id: uuid.UUID, request: Request):
    return _pub(request).detail(product_id)


@public_router.get("/catalogue/facets", response_model=FacetsOut, summary="Counts for browse menus")
def facets(request: Request):
    return _pub(request).facets()


@public_router.get("/catalogue/collections", response_model=list[CollectionOut], summary="Featured collections")
def collections(request: Request):
    return _pub(request).collections()


@public_router.get("/catalogue/collections/{slug}", response_model=CollectionOut, summary="One collection")
def collection(slug: str, request: Request):
    return _pub(request).collection(slug)


# =============================================================================== product media objects
class MediaObjectOut(BaseModel):
    id: str
    product_id: str
    kind: Literal["generated", "uploaded"]
    content_type: str
    byte_size: int
    sha256: str
    alt_text: Optional[str]
    position: int
    generator: Optional[str]
    rights: dict
    status: Literal["active", "removed"]
    url: str
    created_at: str
    removed_at: Optional[str]


class MediaPatch(_Strict):
    alt_text: Optional[StrictStr] = Field(default=None, max_length=200)


class MediaOrderIn(_Strict):
    media_ids: list[uuid.UUID] = Field(max_length=20)


class GenerateMissingOut(BaseModel):
    generated: int
    more_remaining: bool


MEDIA_HEADERS = {"X-Content-Type-Options": "nosniff",
                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                 "Cross-Origin-Resource-Policy": "cross-origin"}


def _media(request: Request):
    return request.app.state.services.media


@router.get("/admin/catalogue/products/{product_id}/media", response_model=list[MediaObjectOut],
            summary="A product's media objects (catalogue:media)")
def list_media(product_id: uuid.UUID, request: Request, include_removed: bool = Query(False),
               principal: Principal = Depends(current_principal)):
    return _media(request).list(principal, product_id, include_removed)


@router.post("/admin/catalogue/products/{product_id}/media", status_code=201, response_model=MediaObjectOut,
             summary="Upload an image object (raw JPEG/PNG/WebP body, max 5 MB; SVG never accepted)",
             openapi_extra={"requestBody": {"required": True, "content": {
                 t: {"schema": {"type": "string", "format": "binary"}} for t in ("image/jpeg", "image/png", "image/webp")}}})
async def upload_media(product_id: uuid.UUID, request: Request, alt: Optional[str] = Query(None, max_length=200),
                       rights_basis: Optional[str] = Query(None, max_length=200),
                       principal: Principal = Depends(current_principal)):
    from fastapi.concurrency import run_in_threadpool

    from ..platform.errors import FieldError, validation_failed
    from .publication import MAX_UPLOAD_BYTES
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_UPLOAD_BYTES:
            raise validation_failed([FieldError("body", "too_large", "Images are at most 5 MB.")])
    return await run_in_threadpool(_media(request).upload, principal, product_id, bytes(data), alt=alt,
                                   rights_basis=rights_basis)


@router.post("/admin/catalogue/products/{product_id}/media/generate", status_code=201, response_model=MediaObjectOut,
             summary="Add a generated placeholder object built from the product's facts")
def generate_media(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _media(request).generate(principal, product_id)


@router.put("/admin/catalogue/products/{product_id}/media/order", response_model=list[MediaObjectOut],
            summary="Reorder active media objects (the first is the thumbnail)")
def reorder_media(product_id: uuid.UUID, body: MediaOrderIn, request: Request,
                  principal: Principal = Depends(current_principal)):
    return _media(request).reorder(principal, product_id, body.media_ids)


@router.patch("/admin/catalogue/media/{media_id}", response_model=MediaObjectOut, summary="Edit alt text")
def update_media(media_id: uuid.UUID, body: MediaPatch, request: Request,
                 principal: Principal = Depends(current_principal)):
    return _media(request).update(principal, media_id, alt_text=body.alt_text)


@router.delete("/admin/catalogue/media/{media_id}", status_code=204, summary="Remove a media object (soft, audited)")
def remove_media(media_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _media(request).remove(principal, media_id)
    return Response(status_code=204)


@router.post("/admin/catalogue/media/generate-missing", response_model=GenerateMissingOut,
             summary="One batch: generated placeholders for published products without media (idempotent)")
def generate_missing(request: Request, limit: int = Query(1000), principal: Principal = Depends(current_principal)):
    return _media(request).generate_missing(principal, limit=limit)


@public_router.get("/media/{media_id}", response_class=Response,
                   responses={200: {"content": {"image/svg+xml": {}, "image/png": {}, "image/jpeg": {},
                                                "image/webp": {}}}},
                   summary="A media object (published products; staff also see drafts)")
def serve_media(media_id: uuid.UUID, request: Request, viewer: Optional[Principal] = Depends(_optional_viewer)):
    out = _media(request).serve(viewer, media_id)
    etag = '"' + out["sha256"] + '"'
    cache = "public, max-age=86400" if out["public"] else "private, no-store"
    headers = {**MEDIA_HEADERS, "ETag": etag, "Cache-Control": cache}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=out["data"], media_type=out["content_type"], headers=headers)


# =============================================================================== sizes (add-wearhouse-sizes)
class SizeOut(BaseModel):
    system: str
    code: str
    label: str
    rank: int


class ProductSizeOut(SizeOut):
    origin: Literal["rule", "staff"]


ProductDetailOut.model_rebuild()


class SizeRegistryValueOut(BaseModel):
    code: str
    label: str
    rank: int
    common: bool
    active: Optional[bool] = None


class SizeRegistrySystemOut(BaseModel):
    code: str
    label: str
    position: int
    slots: list[str]
    active: Optional[bool] = None
    sizes: list[SizeRegistryValueOut]


class SizeRegistryOut(BaseModel):
    systems: list[SizeRegistrySystemOut]


class ProductSizesOut(BaseModel):
    product_id: str
    one_size: bool
    sizes: list[ProductSizeOut]


class SizeRefIn(_Strict):
    system: StrictStr = Field(max_length=32)
    code: StrictStr = Field(max_length=8)


class ProductSizesIn(_Strict):
    sizes: list[SizeRefIn] = Field(max_length=40)


class SizeSystemIn(_Strict):
    label: StrictStr = Field(max_length=60)
    position: StrictInt = Field(ge=0, le=100_000)
    slots: list[StrictStr] = Field(default_factory=list, max_length=6)
    active: StrictBool = True


class SizeValueIn(_Strict):
    label: StrictStr = Field(max_length=20)
    rank: StrictInt
    common: StrictBool = True
    active: StrictBool = True


class AssignSizesOut(BaseModel):
    assigned: int
    more_remaining: bool


class UsualSystemOut(BaseModel):
    system: str
    label: str
    usual: Optional[SizeOut]


class UsualSizesOut(BaseModel):
    systems: list[UsualSystemOut]


class UsualSizesIn(_Strict):
    usual: dict[str, Optional[StrictStr]] = Field(max_length=20)


def _sizing(request: Request):
    return request.app.state.services.sizing


@public_router.get("/catalogue/sizes", response_model=SizeRegistryOut, summary="Active size systems and sizes")
def size_registry(request: Request):
    return _sizing(request).registry()


@public_router.get("/catalogue/products/{product_id}/sizes", response_model=ProductSizesOut,
                   summary="Sizes a published product comes in (empty = one size)")
def product_sizes(product_id: uuid.UUID, request: Request):
    return _sizing(request).product_sizes(product_id)


@router.get("/admin/catalogue/sizes", response_model=SizeRegistryOut,
            summary="Size registry including retired sizes (catalogue:ingest)")
def staff_size_registry(request: Request, principal: Principal = Depends(current_principal)):
    return _sizing(request).registry(staff=principal)


@router.put("/admin/catalogue/size-systems/{code}", response_model=SizeRegistryOut, summary="Add or edit a size system")
def put_size_system(code: str, body: SizeSystemIn, request: Request, principal: Principal = Depends(current_principal)):
    return _sizing(request).put_system(principal, code, label=body.label, position=body.position, slots=body.slots,
                                       active=body.active)


@router.put("/admin/catalogue/size-systems/{code}/sizes/{size_code}", response_model=SizeRegistryOut,
            summary="Add or edit a size (retire with active=false)")
def put_size_value(code: str, size_code: str, body: SizeValueIn, request: Request,
                   principal: Principal = Depends(current_principal)):
    return _sizing(request).put_size(principal, code, size_code, label=body.label, rank=body.rank, common=body.common,
                                     active=body.active)


@router.get("/admin/catalogue/products/{product_id}/sizes", response_model=ProductSizesOut,
            summary="A product's sizes, drafts included")
def staff_product_sizes(product_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    return _sizing(request).product_sizes(product_id, staff=principal)


@router.put("/admin/catalogue/products/{product_id}/sizes", response_model=ProductSizesOut,
            summary="Replace a product's sizes (one system; empty = one size)")
def put_product_sizes(product_id: uuid.UUID, body: ProductSizesIn, request: Request,
                      principal: Principal = Depends(current_principal)):
    return _sizing(request).set_product_sizes(principal, product_id, [r.model_dump() for r in body.sizes])


@router.post("/admin/catalogue/sizes/assign-missing", response_model=AssignSizesOut,
             summary="Give published products without sizes the common sizes for their slot (mock data)")
def assign_missing_sizes(request: Request, limit: int = Query(5000), principal: Principal = Depends(current_principal)):
    return _sizing(request).assign_missing(principal, limit=limit)


me_router = APIRouter(tags=["catalogue: me"])


@me_router.get("/me/sizes", response_model=UsualSizesOut, summary="Your usual size per size system")
def usual_sizes(request: Request, principal: Principal = Depends(current_principal)):
    return _sizing(request).usual_sizes(principal)


@me_router.put("/me/sizes", response_model=UsualSizesOut, summary="Set usual sizes ({system: code | null})")
def set_usual_sizes(body: UsualSizesIn, request: Request, principal: Principal = Depends(current_principal)):
    return _sizing(request).set_usual_sizes(principal, body.usual)
