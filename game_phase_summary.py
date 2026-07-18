from dataclasses import dataclass, field


@dataclass
class GamePhaseSummary:
    """
    Aggregate result of the Game Phase Detection stage.

    A flat, typed view over ctx.game_phase_statistics plus the derived
    dominant phase. Internal only.
    """

    opening_moves: int = 0
    middlegame_moves: int = 0
    endgame_moves: int = 0
    unknown_moves: int = 0

    opening_percentage: float = 0.0
    middlegame_percentage: float = 0.0
    endgame_percentage: float = 0.0

    dominant_phase: str | None = None

    total_moves: int = 0

    metadata: dict = field(default_factory=dict)

    error: str | None = None
