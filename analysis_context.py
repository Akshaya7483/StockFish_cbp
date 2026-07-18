from dataclasses import dataclass, field
from typing import Any

from accuracy_summary import AccuracySummary
from game_phase_summary import GamePhaseSummary
from critical_position_summary import CriticalPositionSummary


@dataclass
class AnalysisContext:
    """
    Carries all state for a single game-analysis run through the pipeline,
    so stages can share one object instead of many positional arguments.
    """

    pgn: str
    depth: int | None = None
    movetime: int | None = None
    multipv: int = 3

    engine: Any = None

    current_move_index: int = 0
    total_moves: int = 0
    positions_analyzed: int = 0

    analysis_start_time: float | None = None

    # Candidate detection (Phase 8)
    candidates: list = field(default_factory=list)
    candidates_found: int = 0
    candidate_generation_time_ms: float = 0.0

    # Candidate enrichment (Phase 9)
    enriched_candidates: int = 0
    candidate_enrichment_time_ms: float = 0.0
    average_candidate_analysis_ms: float = 0.0

    # Review classification (Phase 10)
    reviews: list = field(default_factory=list)
    review_statistics: dict = field(default_factory=dict)
    review_generation_time_ms: float = 0.0

    # Brilliancy detection (Phase 11)
    brilliancies: list = field(default_factory=list)
    brilliancy_statistics: dict = field(default_factory=dict)
    brilliancy_generation_time_ms: float = 0.0

    # Accuracy engine (Phase 12)
    accuracy: list = field(default_factory=list)
    accuracy_statistics: dict = field(default_factory=dict)
    accuracy_generation_time_ms: float = 0.0
    accuracy_summary: AccuracySummary | None = None

    # Game phase detection (Phase 13)
    game_phases: list = field(default_factory=list)
    game_phase_statistics: dict = field(default_factory=dict)
    game_phase_generation_time_ms: float = 0.0
    game_phase_summary: GamePhaseSummary | None = None

    # Critical position detection (Phase 14)
    critical_positions: list = field(default_factory=list)
    critical_position_statistics: dict = field(default_factory=dict)
    critical_position_generation_time_ms: float = 0.0
    critical_position_summary: CriticalPositionSummary | None = None

    metadata: dict = field(default_factory=dict)
