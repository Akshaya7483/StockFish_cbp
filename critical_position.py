from dataclasses import dataclass, field
from typing import Any

from criticality import Criticality


@dataclass
class CriticalPosition:
    """
    A single move analyzed for criticality. Internal only — only aggregate
    statistics/summary are exposed through the API.
    """

    ply: int | None
    move_number: int | None
    side: str | None
    played_move: str | None

    phase: str | None
    severity: Criticality
    reason: str

    evaluation_before: dict | None = None
    evaluation_after: dict | None = None
    evaluation_delta_cp: int | None = None

    review: Any = None
    brilliancy: Any = None

    metadata: dict = field(default_factory=dict)

    error: str | None = None
