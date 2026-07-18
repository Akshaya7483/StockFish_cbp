from time import perf_counter
import chess

from game_phase import GamePhase
from game_phase_result import GamePhaseResult
from game_phase_summary import GamePhaseSummary


# A move can only be an opening move within this many full moves.
_OPENING_MAX_MOVE_NUMBER = 10

# Full major-piece complement (2 queens + 4 rooks) — no majors traded yet.
_FULL_MAJORS = 6

# Endgame material thresholds (piece counts, both colours, excluding kings/pawns).
_ENDGAME_NON_PAWN = 6
_ENDGAME_QUEENLESS_NON_PAWN = 10


class GamePhaseDetectionStage:
    """
    Game Phase Detection — complete implementation.

    Classifies every timeline move into exactly one GamePhase
    (OPENING / MIDDLEGAME / ENDGAME, or UNKNOWN on error) using only
    deterministic board information already available in the timeline (FENs).
    It performs no Stockfish searches, no evaluation recalculation, and no
    timeline changes. It also computes aggregate statistics and a typed
    GamePhaseSummary.
    """

    def run(self, ctx, timeline=None):
        start = perf_counter()

        timeline = timeline if timeline is not None else self._timeline(ctx)

        game_phases = [self._classify_move(entry) for entry in timeline]

        ctx.game_phases = game_phases
        ctx.game_phase_statistics = self._compute_statistics(game_phases)
        ctx.game_phase_summary = self._build_summary(ctx.game_phase_statistics)

        ctx.game_phase_generation_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )

        return ctx

    # ------------------------------------
    # Per-move classification
    # ------------------------------------

    def _classify_move(self, entry):
        ply = entry.get("ply")
        move_number = entry.get("move_number")
        side = entry.get("side")
        fen = entry.get("before_fen")

        try:
            board = chess.Board(fen)
        except Exception as e:
            return GamePhaseResult(
                phase=GamePhase.UNKNOWN,
                ply=ply,
                move_number=move_number,
                side=side,
                reason="invalid_board",
                error=str(e),
            )

        phase, reason = self._detect_phase(board, move_number)

        return GamePhaseResult(
            phase=phase,
            ply=ply,
            move_number=move_number,
            side=side,
            reason=reason,
            metadata={"material": self._material_snapshot(board)},
        )

    def _detect_phase(self, board, move_number):
        """
        Resolve a single phase for the move. Endgame (material-based) takes
        priority, then opening (early + full majors), otherwise middlegame.
        Guarantees exactly one non-UNKNOWN phase for a valid board.
        """
        if self._detect_endgame(board):
            return GamePhase.ENDGAME, self._endgame_reason(board)

        if self._detect_opening(board, move_number):
            return GamePhase.OPENING, "early_full_major_material"

        return GamePhase.MIDDLEGAME, "post_opening_pre_endgame"

    # ------------------------------------
    # Phase predicates
    # ------------------------------------

    def _detect_opening(self, board, move_number):
        """
        Opening while the game is still early and no major pieces have been
        traded (both queens and all rooks remain). Board/FEN only.
        """
        if move_number is None or move_number > _OPENING_MAX_MOVE_NUMBER:
            return False

        snap = self._material_snapshot(board)
        return snap["queens"] == 2 and snap["majors"] == _FULL_MAJORS

    def _detect_endgame(self, board):
        """
        Endgame when non-pawn material is significantly reduced: very few
        pieces remain, or queens are off with limited remaining material.
        Board material only — no engine evaluation.
        """
        snap = self._material_snapshot(board)
        non_pawn = snap["non_pawn"]

        if non_pawn <= _ENDGAME_NON_PAWN:
            return True
        if snap["queens"] == 0 and non_pawn <= _ENDGAME_QUEENLESS_NON_PAWN:
            return True
        return False

    def _endgame_reason(self, board):
        snap = self._material_snapshot(board)
        if snap["non_pawn"] <= _ENDGAME_NON_PAWN:
            return "few_pieces_remaining"
        return "queens_exchanged"

    # ------------------------------------
    # Material helpers
    # ------------------------------------

    def _count_major_pieces(self, board):
        """Queens + rooks for both colours."""
        return (
            len(board.pieces(chess.QUEEN, chess.WHITE))
            + len(board.pieces(chess.QUEEN, chess.BLACK))
            + len(board.pieces(chess.ROOK, chess.WHITE))
            + len(board.pieces(chess.ROOK, chess.BLACK))
        )

    def _count_minor_pieces(self, board):
        """Bishops + knights for both colours."""
        return (
            len(board.pieces(chess.BISHOP, chess.WHITE))
            + len(board.pieces(chess.BISHOP, chess.BLACK))
            + len(board.pieces(chess.KNIGHT, chess.WHITE))
            + len(board.pieces(chess.KNIGHT, chess.BLACK))
        )

    def _material_snapshot(self, board):
        """Deterministic piece-count snapshot (both colours, no kings/pawns)."""
        queens = (
            len(board.pieces(chess.QUEEN, chess.WHITE))
            + len(board.pieces(chess.QUEEN, chess.BLACK))
        )
        majors = self._count_major_pieces(board)
        minors = self._count_minor_pieces(board)
        return {
            "queens": queens,
            "rooks": majors - queens,
            "majors": majors,
            "minors": minors,
            "non_pawn": majors + minors,
        }

    # ------------------------------------
    # Statistics & summary
    # ------------------------------------

    def _compute_statistics(self, game_phases):
        total = len(game_phases)

        opening = sum(1 for r in game_phases if r.phase == GamePhase.OPENING)
        middlegame = sum(1 for r in game_phases if r.phase == GamePhase.MIDDLEGAME)
        endgame = sum(1 for r in game_phases if r.phase == GamePhase.ENDGAME)
        unknown = sum(1 for r in game_phases if r.phase == GamePhase.UNKNOWN)

        return {
            "opening_moves": opening,
            "middlegame_moves": middlegame,
            "endgame_moves": endgame,
            "unknown_moves": unknown,
            "total_moves": total,
            "opening_percentage": self._percentage(opening, total),
            "middlegame_percentage": self._percentage(middlegame, total),
            "endgame_percentage": self._percentage(endgame, total),
        }

    def _build_summary(self, statistics):
        """Map the statistics dict into a typed GamePhaseSummary."""
        return GamePhaseSummary(
            opening_moves=statistics.get("opening_moves", 0),
            middlegame_moves=statistics.get("middlegame_moves", 0),
            endgame_moves=statistics.get("endgame_moves", 0),
            unknown_moves=statistics.get("unknown_moves", 0),
            opening_percentage=statistics.get("opening_percentage", 0.0),
            middlegame_percentage=statistics.get("middlegame_percentage", 0.0),
            endgame_percentage=statistics.get("endgame_percentage", 0.0),
            dominant_phase=self._dominant_phase(statistics),
            total_moves=statistics.get("total_moves", 0),
        )

    def _dominant_phase(self, statistics):
        """
        Phase with the most moves among opening/middlegame/endgame. Ties are
        broken in opening -> middlegame -> endgame order. None when there are
        no classified moves.
        """
        counts = [
            (GamePhase.OPENING.value, statistics.get("opening_moves", 0)),
            (GamePhase.MIDDLEGAME.value, statistics.get("middlegame_moves", 0)),
            (GamePhase.ENDGAME.value, statistics.get("endgame_moves", 0)),
        ]
        best_phase, best_count = max(counts, key=lambda item: item[1])
        if best_count == 0:
            return None
        return best_phase

    def _percentage(self, count, total):
        if not total:
            return 0.0
        return round(count / total * 100, 2)

    def _timeline(self, ctx):
        return getattr(ctx, "timeline", []) or []
