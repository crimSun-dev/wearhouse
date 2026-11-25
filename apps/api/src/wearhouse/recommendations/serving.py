"""Recommendation serving with truthful model modes (recommendation-serving spec).

Similar items: the active imported artifact (its declared mode; `trained` only with a model hash) or the
content baseline (same category, trigram text similarity). Personal products: sandbox-order popularity, filled with
newest published, never including products the caller owns. Every response carries ModelInfo.
Artifacts are imported only after their sha256 manifest verifies; activation is audited.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from typing import Callable, Protocol

from ..catalogue.domain import colour_hex
from ..identity.domain import Capability, Principal, require
from ..platform.clock import Clock, utcnow
from ..platform.errors import FieldError, not_found, validation_failed
from ..platform.ids import new_id
from .baseline import color_pair
from .ports import ModelInfo, RankerMode

CONTENT_BASELINE = ModelInfo(RankerMode.HEURISTIC_BASELINE, "content-trigram-same-category", "1")
POPULARITY_BASELINE = ModelInfo(RankerMode.HEURISTIC_BASELINE, "sandbox-order-popularity+newest", "1")
POPULARITY_WINDOW = timedelta(days=30)
LAMBDA_C, LAMBDA_D = 0.5, 0.5  # proposed (not tuned) Eq. 3 weights for the heuristic rerank (complete-wearhouse-tdd)


def rerank(cards: list[dict], owned: list[dict]) -> tuple[list[dict], bool]:
    """Eq. 3 in labelled heuristic form: base (rank order) + LAMBDA_C*completion - LAMBDA_D*duplicate.
    completion = mean colour compatibility with the best 3 owned items of OTHER slots (0 when there are none);
    duplicate = 1 when an owned item has the same category and colour. Returns (cards, cold_start)."""
    cold = not owned
    scored = []
    for n, c in enumerate(cards):
        base = 1.0 - n / max(len(cards), 1)
        mine = colour_hex(c.get("colour"))
        pairs = sorted((color_pair(mine, colour_hex(o.get("colour"))) for o in owned
                        if o.get("slot") != c.get("slot") and mine and colour_hex(o.get("colour"))), reverse=True)[:3]
        completion = sum(pairs) / len(pairs) if pairs else 0.0
        duplicate = 1.0 if any(o.get("category") == c.get("category") and o.get("colour") == c.get("colour")
                               for o in owned) else 0.0
        scored.append((base + LAMBDA_C * completion - LAMBDA_D * duplicate, n,
                       {**c, "rerank": {"completion": round(completion, 4), "duplicate": duplicate}}))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [c for _, _, c in scored], cold


class ArtifactRepository(Protocol):
    def active(self, kind: str) -> dict | None: ...
    def all(self) -> list[dict]: ...
    def create(self, **kw) -> None: ...
    def add_neighbours(self, rows: list[dict]) -> None: ...
    def activate(self, artifact_id: uuid.UUID, kind: str) -> None: ...
    def neighbours(self, artifact_id: uuid.UUID, product_id: uuid.UUID, limit: int) -> list[uuid.UUID]: ...


def model_view(m: ModelInfo, **extra) -> dict:
    return {"mode": m.mode.value, "name": m.name, "version": m.version, "trained_artifact": m.trained_artifact, **extra}


def artifact_model(a: dict) -> ModelInfo:
    trained = a["mode"] == RankerMode.TRAINED.value
    return ModelInfo(RankerMode(a["mode"]), a["name"], a["version"], a["model_hash"] if trained else None)


class RecommendationService:
    def __init__(self, uow_factory: Callable, *, clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.clock = clock

    def similar(self, product_id: uuid.UUID, limit: int = 12) -> dict:
        if not 1 <= limit <= 50:
            raise validation_failed([FieldError("query.limit", "out_of_range", "limit must be 1-50.")])
        with self.uow_factory() as uow:
            ident = uow.publishing.product_identity(product_id)
            if ident is None or ident["publication_state"] != "published":
                raise not_found("Product not found.")
            art = uow.artifacts.active("similar_items")
            ids, model, fallback = [], CONTENT_BASELINE, None
            if art:
                ids = uow.artifacts.neighbours(art["id"], product_id, limit)
                model = artifact_model(art)
                if not ids:
                    fallback, model = "artifact has no neighbours for this product", CONTENT_BASELINE
            if not ids:
                ids = uow.publishing.similar_by_content(product_id, limit)
            items = uow.publishing.cards(ids)[:limit]
        return {"product_id": str(product_id), "model": model_view(model, fallback=fallback), "items": items}

    def for_me(self, principal: Principal, limit: int = 12) -> dict:
        if not 1 <= limit <= 50:
            raise validation_failed([FieldError("query.limit", "out_of_range", "limit must be 1-50.")])
        with self.uow_factory() as uow:
            owned = {uuid.UUID(o.presentation["product"]["id"]) for o in uow.owned.active_items(principal.user_id)
                     if o.presentation.get("product", {}).get("id")}
            owned_cards = uow.publishing.cards(sorted(owned))
            usual = uow.sizes.preferences(principal.user_id)

            def fits(ids: list[uuid.UUID]) -> list[uuid.UUID]:
                """Drop sized products that miss the caller's usual size in their system (add-wearhouse-sizes D7).
                One-size products, and systems without a usual size, always pass."""
                if not usual:
                    return ids
                sizes = uow.sizes.product_sizes(ids)
                keep = []
                for pid in ids:
                    have = sizes.get(pid, [])
                    system = have[0].system if have else None
                    if system is None or system not in usual or any(x.code == usual[system] for x in have):
                        keep.append(pid)
                return keep

            popular = fits([p for p in uow.commerce.popular_products(self.clock() - POPULARITY_WINDOW, limit * 3)
                            if p not in owned])
            cards = uow.publishing.cards(popular)
            if len(cards) < limit:
                seen = owned | {uuid.UUID(c["id"]) for c in cards}
                fresh = fits(uow.publishing.newest_published((limit - len(cards)) * 4, seen))
                cards += uow.publishing.cards(fresh[:limit - len(cards)])
        ranked, cold = rerank(cards[:limit], owned_cards)
        return {"model": model_view(POPULARITY_BASELINE), "sized_to_you": bool(usual), "items": ranked,
                "rerank": {"name": "completion-duplicate (heuristic Eq. 3)", "lambda_c": LAMBDA_C, "lambda_d": LAMBDA_D,
                           "cold_start": cold}}

    # ------------------------------------------------------------------ import (CLI)
    def import_similar_items(self, principal: Principal, manifest: dict, neighbours_csv: bytes) -> dict:
        """Verify, map source ids to products, write neighbours, activate (all or nothing), audit."""
        require(principal, Capability.INGEST_PRODUCTS)
        declared = manifest.get("files", {}).get("neighbours.csv")
        actual = hashlib.sha256(neighbours_csv).hexdigest()
        if declared != actual:
            raise validation_failed([FieldError("manifest.files", "checksum_mismatch",
                                                f"neighbours.csv sha256 {actual} does not match the manifest.")])
        mode = manifest.get("mode")
        if manifest.get("kind") != "similar_items" or mode not in ("trained", "heuristic_baseline"):
            raise validation_failed([FieldError("manifest", "invalid", "kind must be similar_items; mode trained or "
                                                                      "heuristic_baseline.")])
        if mode == "trained" and not manifest.get("model_hash"):
            raise validation_failed([FieldError("manifest.model_hash", "required", "Trained artifacts need a model hash.")])
        lines = neighbours_csv.decode("utf-8").splitlines()
        if not lines or lines[0].strip() != "article_id,rank,neighbour_article_id,score":
            raise validation_failed([FieldError("neighbours.csv", "header", "Expected article_id,rank,neighbour_article_id,score.")])
        parsed = [line.split(",") for line in lines[1:] if line.strip()]
        ext = sorted({p[0] for p in parsed} | {p[2] for p in parsed})
        with self.uow_factory() as uow:
            ids = uow.publishing.products_by_external(manifest["source_namespace"], ext)
            artifact_id = new_id()
            uow.artifacts.create(artifact_id=artifact_id, kind="similar_items", name=manifest["name"],
                                 version=str(manifest["version"]), mode=mode, model_hash=manifest.get("model_hash"),
                                 manifest=manifest, imported_by=principal.user_id, now=self.clock())
            rows, skipped = [], 0
            for a, rank, b, score in parsed:
                if a in ids and b in ids:
                    rows.append({"artifact_id": artifact_id, "product_id": ids[a], "rank": int(rank),
                                 "neighbour_id": ids[b], "score": float(score)})
                else:
                    skipped += 1
            uow.artifacts.add_neighbours(rows)
            uow.artifacts.activate(artifact_id, "similar_items")
            uow.audit.record(actor_id=principal.user_id, action="recommendations.artifact_activated",
                             target_type="recommendation_artifact", target_id=str(artifact_id),
                             details={"name": manifest["name"], "version": str(manifest["version"]), "mode": mode,
                                      "model_hash": manifest.get("model_hash"), "rows": len(rows), "skipped": skipped,
                                      "sha256": actual})
            uow.commit()
        return {"artifact_id": str(artifact_id), "rows": len(rows), "skipped_unknown_products": skipped, "mode": mode}
