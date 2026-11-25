"""Recommendation extension ports (no HTTP endpoint in the foundation).

Every result carries `ModelInfo` so consumers can tell a heuristic baseline from a trained artifact.
A heuristic adapter can never declare trained mode, and a trained mode requires a named artifact.
Catalogue ranking and outfit ranking are separate interfaces that share only feature/result types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence


class RankerMode(str, Enum):
    HEURISTIC_BASELINE = "heuristic_baseline"
    TRAINED = "trained"


@dataclass(frozen=True)
class ModelInfo:
    mode: RankerMode
    name: str
    version: str
    trained_artifact: str | None = None  # e.g. a checksummed model file; required for TRAINED

    def __post_init__(self):
        if self.mode is RankerMode.TRAINED and not self.trained_artifact:
            raise ValueError("trained mode requires a trained artifact reference")
        if self.mode is RankerMode.HEURISTIC_BASELINE and self.trained_artifact:
            raise ValueError("a heuristic baseline cannot claim a trained artifact")


@dataclass(frozen=True)
class ItemFeatures:
    """Verified features only. None means unknown and is never replaced by an invented default."""

    item_id: str
    slot: str
    colour_hex: str | None = None
    style: str | None = None
    formality: int | None = None
    rain_suitable: bool | None = None
    heavy: bool | None = None
    long_sleeve: bool | None = None
    long_bottom: bool | None = None


@dataclass(frozen=True)
class RankedOutfit:
    item_ids: tuple[str, ...]
    score: float
    components: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class RankerResult:
    model: ModelInfo
    outfits: tuple[RankedOutfit, ...]


class CompatibilityScorer(Protocol):
    model: ModelInfo

    def score(self, items: Sequence[ItemFeatures]) -> float | None: ...


class OutfitRanker(Protocol):
    model: ModelInfo

    def rank(self, candidates: Sequence[Sequence[ItemFeatures]], k: int) -> RankerResult: ...


class CatalogueRanker(Protocol):
    """Interface only: a trained catalogue ranker arrives with the research-intelligence change."""

    model: ModelInfo

    def rank(self, owned: Sequence[ItemFeatures], catalogue: Sequence[ItemFeatures], k: int) -> RankerResult: ...
