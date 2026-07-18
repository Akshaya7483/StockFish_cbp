from dataclasses import dataclass, field
from typing import Any


@dataclass
class Accuracy:
    """
    Per-move accuracy result derived from a Review.

    Internal only — not exposed through the API. Later steps of the Accuracy
    Engine will populate centipawn_loss / accuracy; Step 1 only defines the
    shape so downstream stages can rely on it.
    """

    review: Any

    centipawn_loss: float | None = None
    accuracy: float | None = None

    player: str | None = None
    move_number: int | None = None

    metadata: dict = field(default_factory=dict)

    error: str | None = None
