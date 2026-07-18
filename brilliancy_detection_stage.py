from time import perf_counter
import chess

from brilliancy import Brilliancy, BrilliancyCategory
from review import ReviewCategory
from config import (
    BRILLIANT_SCORE,
    GREAT_MOVE_SCORE,
    ONLY_MOVE_CP_GAP,
    SACRIFICE_MIN_VALUE,
    SACRIFICE_PV_PLIES,
    PV_STABILITY_DEPTH,
    LARGE_EVAL_GAIN_CP,
    CONFIDENCE_THRESHOLD,
    ONLY_MOVE_WEIGHT,
    SACRIFICE_WEIGHT,
    EVAL_GAIN_WEIGHT,
    MATE_WEIGHT,
    PV_STABILITY_WEIGHT,
    DEPTH_CONFIDENCE_WEIGHT,
)


# Only these review categories are eligible for brilliancy evaluation.
_ELIGIBLE = {ReviewCategory.BEST_MOVE, ReviewCategory.EXCELLENT}

_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

_MATE_SCORE = 100000


class BrilliancyDetectionStage:
    """
    Detects Brilliant and Great moves from already-reviewed candidates using
    weighted signal scoring. Uses only existing Review / Candidate / deep
    analysis data — performs no Stockfish searches and runs O(n) over reviews
    (each signal helper is O(1)).

    Populates ctx.brilliancies, ctx.brilliancy_statistics and
    ctx.brilliancy_generation_time_ms. Does not touch the API response.
    """

    def run(self, ctx):
        start = perf_counter()

        brilliancies = []
        stats = {
            "total_candidates": len(ctx.reviews),
            "evaluated_candidates": 0,
            "great_moves": 0,
            "brilliant_moves": 0,
        }

        total_ms = 0.0

        for review in ctx.reviews:
            if review.classification not in _ELIGIBLE:
                continue

            stats["evaluated_candidates"] += 1

            detect_start = perf_counter()
            try:
                brilliancy = self._detect(review)
            except Exception as e:
                brilliancy = Brilliancy(
                    review=review,
                    category=BrilliancyCategory.NONE,
                    error=str(e),
                )
            total_ms += (perf_counter() - detect_start) * 1000

            if brilliancy.category == BrilliancyCategory.BRILLIANT_MOVE:
                stats["brilliant_moves"] += 1
            elif brilliancy.category == BrilliancyCategory.GREAT_MOVE:
                stats["great_moves"] += 1

            # Keep positive detections and any errored evaluations.
            if brilliancy.category != BrilliancyCategory.NONE or brilliancy.error:
                brilliancies.append(brilliancy)

        stats["average_detection_time_ms"] = round(
            total_ms / stats["evaluated_candidates"],
            4
        ) if stats["evaluated_candidates"] else 0.0

        ctx.brilliancies = brilliancies
        ctx.brilliancy_statistics = stats
        ctx.brilliancy_generation_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )

        return ctx

    # ------------------------------------
    # Detection + scoring
    # ------------------------------------

    def _detect(self, review):
        candidate = review.candidate

        only_move = self._detect_only_move(candidate)
        sacrifice = self._detect_sacrifice(candidate)
        eval_gain = self._detect_large_eval_gain(candidate)
        mate = self._detect_mate_resource(candidate)
        pv_stable = self._detect_pv_stability(candidate)
        tactical = self._detect_tactical_resource(candidate)
        high_confidence = review.confidence >= CONFIDENCE_THRESHOLD

        score = 0
        reasons = []

        if only_move:
            score += ONLY_MOVE_WEIGHT
            reasons.append("only_move")
        if sacrifice:
            score += SACRIFICE_WEIGHT
            reasons.append("sacrifice")
        if eval_gain:
            score += EVAL_GAIN_WEIGHT
            reasons.append("large_eval_gain")
        if mate:
            score += MATE_WEIGHT
            reasons.append("mate_found")
        if pv_stable:
            score += PV_STABILITY_WEIGHT
            reasons.append("pv_stable")
        if high_confidence:
            score += DEPTH_CONFIDENCE_WEIGHT
            reasons.append("high_confidence")

        score = min(score, 100)

        category = self._categorize(score, tactical, eval_gain, only_move)

        confidence = round(
            min(1.0, review.confidence * 0.5 + (score / 100.0) * 0.5),
            4
        )

        return Brilliancy(
            review=review,
            category=category,
            confidence=confidence,
            score=score,
            reasons=reasons,
            metadata={
                "only_move": only_move,
                "sacrifice": sacrifice,
                "large_eval_gain": eval_gain,
                "mate_found": mate,
                "pv_stable": pv_stable,
                "tactical_resource": tactical,
                "high_confidence": high_confidence,
            },
        )

    def _categorize(self, score, tactical, eval_gain, only_move):
        if score >= BRILLIANT_SCORE:
            return BrilliancyCategory.BRILLIANT_MOVE
        if score >= GREAT_MOVE_SCORE and (tactical or eval_gain or only_move):
            return BrilliancyCategory.GREAT_MOVE
        return BrilliancyCategory.NONE

    # ------------------------------------
    # Signal helpers (each O(1))
    # ------------------------------------

    def _detect_only_move(self, candidate):
        lines = (candidate.deep_analysis or {}).get("analysis", []) or []
        if len(lines) <= 1:
            # Engine returned a single line despite multipv request.
            return len(lines) == 1

        top, second = lines[0], lines[1]
        top_mate = top.get("mate")
        second_mate = second.get("mate")

        # Mate / non-mate transitions are handled explicitly rather than via
        # numeric conversion, which would collapse e.g. mate-2 vs mate-3 into a
        # 1-point difference and misjudge clearly non-equivalent lines.
        if (top_mate is not None) != (second_mate is not None):
            # Exactly one line is a forced mate.
            if top_mate is not None and top_mate > 0:
                # Only the top move forces mate; alternatives do not.
                return True
            if second_mate is not None and second_mate < 0:
                # Every alternative gets mated; only the top move avoids it.
                return True
            return False

        if top_mate is not None and second_mate is not None:
            # Both lines force mate: more than one winning move exists, so this
            # is not an only move regardless of mate distance.
            return False

        # Neither line is a mate: fall back to the centipawn gap.
        gap = self._line_eval(top) - self._line_eval(second)
        return gap >= ONLY_MOVE_CP_GAP

    def _detect_sacrifice(self, candidate):
        pv = candidate.deep_pv or []
        if not pv:
            return False
        try:
            board = chess.Board(candidate.before_fen)
        except Exception:
            return False

        mover = board.turn
        before_balance = self._relative_material(board, mover)

        # Track the *minimum* material balance reached along the PV, not just
        # the final balance. A true sacrifice dips below the starting balance
        # even when material is later regained (e.g. a queen sac that wins the
        # queen back, or a temporary pawn sac that nets a rook). Comparing only
        # start vs end would miss both.
        min_balance = before_balance
        pushed = 0
        for uci in pv[:SACRIFICE_PV_PLIES]:
            try:
                board.push_uci(uci)
            except Exception:
                break
            pushed += 1
            balance = self._relative_material(board, mover)
            if balance < min_balance:
                min_balance = balance

        if pushed == 0:
            return False

        invested = before_balance - min_balance

        favorable = (
            (candidate.deep_mate is not None and candidate.deep_mate > 0)
            or (candidate.deep_cp is not None and candidate.deep_cp >= -50)
        )
        return invested >= SACRIFICE_MIN_VALUE and favorable

    def _detect_mate_resource(self, candidate):
        return candidate.deep_mate is not None and candidate.deep_mate > 0

    def _detect_pv_stability(self, candidate):
        depth = candidate.deep_depth or 0
        pv = candidate.deep_pv or []
        return depth >= PV_STABILITY_DEPTH and len(pv) >= 2

    def _detect_large_eval_gain(self, candidate):
        if candidate.deep_cp is None:
            return candidate.deep_mate is not None and candidate.deep_mate > 0
        eval_before = candidate.evaluation_before.get("cp")
        if eval_before is None:
            return False
        return (candidate.deep_cp - eval_before) >= LARGE_EVAL_GAIN_CP

    def _detect_tactical_resource(self, candidate):
        pv = candidate.deep_pv or []
        if not pv:
            return False
        try:
            board = chess.Board(candidate.before_fen)
            move = chess.Move.from_uci(pv[0])
        except Exception:
            return False
        if move not in board.legal_moves:
            return False
        return board.is_capture(move) or board.gives_check(move)

    # ------------------------------------
    # Small utilities
    # ------------------------------------

    def _line_eval(self, line):
        mate = line.get("mate")
        if mate is not None:
            return _MATE_SCORE - mate if mate > 0 else -_MATE_SCORE - mate
        cp = line.get("cp")
        return cp if cp is not None else 0

    def _relative_material(self, board, color):
        return self._material(board, color) - self._material(board, not color)

    def _material(self, board, color):
        total = 0
        for piece_type, value in _PIECE_VALUES.items():
            total += value * len(board.pieces(piece_type, color))
        return total
