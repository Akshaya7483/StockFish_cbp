from dataclasses import dataclass, field


@dataclass
class AccuracySummary:
    """
    Final result object of the Accuracy Engine.

    A flat, typed view over the values already present in
    ctx.accuracy_statistics. Internal only — not exposed through the API.
    Later phases can consume this instead of the raw statistics dict.
    """

    # Game-level
    overall_average_accuracy: float | None = None
    overall_average_cpl: float | None = None

    # Per-player
    white_moves: int = 0
    black_moves: int = 0
    white_average_accuracy: float | None = None
    black_average_accuracy: float | None = None
    white_average_cpl: float | None = None
    black_average_cpl: float | None = None

    # Best / worst
    best_player: str | None = None
    best_player_accuracy: float | None = None
    worst_player: str | None = None
    worst_player_accuracy: float | None = None

    # Totals
    total_moves: int = 0
    evaluated_moves: int = 0
    failed_moves: int = 0

    metadata: dict = field(default_factory=dict)

    error: str | None = None
