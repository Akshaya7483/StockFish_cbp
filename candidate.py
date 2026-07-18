from dataclasses import dataclass, field


@dataclass
class Candidate:
    """
    A position flagged for potential deeper analysis.

    Built entirely from existing timeline data — no extra engine searches.
    Not exposed through the API yet.
    """

    ply: int
    move_number: int
    side: str
    played_move: str
    before_fen: str
    after_fen: str
    engine_best_move: str | None

    evaluation_before: dict
    evaluation_after: dict
    evaluation_delta_cp: int | None

    is_best_move: bool

    priority: int = 0
    reasons: list[str] = field(default_factory=list)

    # ------------------------------------
    # Deep enrichment (Phase 9) — internal only, not exposed via API.
    # ------------------------------------
    deep_analysis: dict | None = None
    deep_best_move: str | None = None
    deep_pv: list | None = None
    deep_cp: int | None = None
    deep_mate: int | None = None
    deep_depth: int | None = None
    deep_nodes: int | None = None
    deep_time_ms: int | None = None
    deep_win_probability: float | None = None

    error: str | None = None
