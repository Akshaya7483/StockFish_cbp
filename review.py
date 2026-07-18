from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReviewCategory(str, Enum):
    """
    Initial review categories (Phase 10).

    Brilliant / Great Move are intentionally excluded — they belong to the
    later brilliancy stage.
    """

    BEST_MOVE = "best_move"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


@dataclass
class Review:
    """
    Classification of a single enriched Candidate.

    Internal only — not exposed through the API. Designed so the brilliancy
    stage can consume it directly without recomputation.
    """

    candidate: Any

    classification: ReviewCategory | None

    centipawn_loss: int | None
    evaluation_before: dict
    evaluation_after: dict
    evaluation_delta_cp: int | None

    is_best_move: bool

    confidence: float = 0.0
    severity: int = 0

    reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    error: str | None = None
