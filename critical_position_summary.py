from dataclasses import dataclass, field


@dataclass
class CriticalPositionSummary:
    """
    Aggregate result of the Critical Position Detection stage. Internal only.
    """

    critical_positions: int = 0
    critical_moves: int = 0

    highest_severity: str | None = None

    opening_critical: int = 0
    middlegame_critical: int = 0
    endgame_critical: int = 0

    white_critical: int = 0
    black_critical: int = 0

    metadata: dict = field(default_factory=dict)

    error: str | None = None
