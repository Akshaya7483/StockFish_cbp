from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BrilliancyCategory(str, Enum):
    NONE = "none"
    GREAT_MOVE = "great_move"
    BRILLIANT_MOVE = "brilliant_move"


@dataclass
class Brilliancy:
    """
    Brilliant / Great move detection result for a single Review.

    Internal only — not exposed through the API. Designed so later stages
    (accuracy, explanations, UI annotations) can reuse it directly.
    """

    review: Any

    category: BrilliancyCategory

    confidence: float = 0.0
    score: int = 0

    reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    error: str | None = None
