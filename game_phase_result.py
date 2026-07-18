from dataclasses import dataclass, field

from game_phase import GamePhase


@dataclass
class GamePhaseResult:
    """
    Phase classification for a single move. Internal only — not exposed
    directly through the API (only aggregate statistics are surfaced).
    """

    phase: GamePhase
    ply: int
    move_number: int
    side: str

    reason: str = ""
    metadata: dict = field(default_factory=dict)

    error: str | None = None
