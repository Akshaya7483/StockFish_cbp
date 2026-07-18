from time import perf_counter

from review import Review, ReviewCategory
from config import (
    BEST_MOVE_CP,
    EXCELLENT_CP,
    GOOD_CP,
    INACCURACY_CP,
    MISTAKE_CP,
    MATE_BLUNDER_PRIORITY,
)


# Base severity per category (0..100), refined per-review afterwards.
_BASE_SEVERITY = {
    ReviewCategory.BEST_MOVE: 0,
    ReviewCategory.EXCELLENT: 5,
    ReviewCategory.GOOD: 15,
    ReviewCategory.INACCURACY: 40,
    ReviewCategory.MISTAKE: 70,
    ReviewCategory.BLUNDER: 95,
}

_STAT_KEYS = {
    ReviewCategory.BEST_MOVE: "best_moves",
    ReviewCategory.EXCELLENT: "excellent_moves",
    ReviewCategory.GOOD: "good_moves",
    ReviewCategory.INACCURACY: "inaccuracies",
    ReviewCategory.MISTAKE: "mistakes",
    ReviewCategory.BLUNDER: "blunders",
}


class ReviewClassificationStage:
    """
    Classifies every enriched Candidate into a ReviewCategory using only
    existing candidate data, deep analysis and timeline evaluations.

    Performs no Stockfish searches and runs in O(n) over the candidates.
    Populates ctx.reviews, ctx.review_statistics and
    ctx.review_generation_time_ms. Does not touch the API response.
    """

    def run(self, ctx):
        start = perf_counter()

        reviews = []
        stats = {
            "total_reviews": 0,
            "best_moves": 0,
            "excellent_moves": 0,
            "good_moves": 0,
            "inaccuracies": 0,
            "mistakes": 0,
            "blunders": 0,
        }

        total_review_ms = 0.0

        for candidate in ctx.candidates:
            review_start = perf_counter()
            try:
                review = self._classify(candidate)
            except Exception as e:
                # Failure isolation: keep going, record the error.
                review = Review(
                    candidate=candidate,
                    classification=None,
                    centipawn_loss=None,
                    evaluation_before=getattr(candidate, "evaluation_before", {}) or {},
                    evaluation_after=getattr(candidate, "evaluation_after", {}) or {},
                    evaluation_delta_cp=getattr(candidate, "evaluation_delta_cp", None),
                    is_best_move=getattr(candidate, "is_best_move", False),
                    error=str(e),
                )

            total_review_ms += (perf_counter() - review_start) * 1000

            reviews.append(review)
            stats["total_reviews"] += 1
            if review.classification is not None:
                stats[_STAT_KEYS[review.classification]] += 1

        stats["average_review_time_ms"] = round(
            total_review_ms / len(ctx.candidates),
            4
        ) if ctx.candidates else 0.0

        ctx.reviews = reviews
        ctx.review_statistics = stats
        ctx.review_generation_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )

        return ctx

    # ------------------------------------
    # Classification
    # ------------------------------------

    def _classify(self, candidate):
        cpl = self._centipawn_loss(candidate)
        reasons = []

        mate_missed = self._mate_missed(candidate)
        forced_mate_allowed = self._forced_mate_allowed(candidate)

        classification = self._categorize(
            candidate, cpl, mate_missed, forced_mate_allowed, reasons
        )

        confidence = self._confidence(candidate, cpl)
        severity = self._severity(
            classification, cpl, mate_missed, forced_mate_allowed
        )

        return Review(
            candidate=candidate,
            classification=classification,
            centipawn_loss=cpl,
            evaluation_before=candidate.evaluation_before,
            evaluation_after=candidate.evaluation_after,
            evaluation_delta_cp=candidate.evaluation_delta_cp,
            is_best_move=candidate.is_best_move,
            confidence=confidence,
            severity=severity,
            reasons=reasons,
            metadata={
                "mate_missed": mate_missed,
                "forced_mate_allowed": forced_mate_allowed,
                "deep_depth": candidate.deep_depth,
            },
        )

    def _categorize(self, candidate, cpl, mate_missed, forced_mate_allowed, reasons):
        # Best move: the played move matches the deep best move.
        if (
            candidate.deep_best_move is not None
            and candidate.played_move == candidate.deep_best_move
        ):
            reasons.append("played_deep_best_move")
            return ReviewCategory.BEST_MOVE

        # Mate-related blunders take priority.
        if mate_missed:
            reasons.append("mate_missed")
            return ReviewCategory.BLUNDER
        if forced_mate_allowed:
            reasons.append("forced_mate_allowed")
            return ReviewCategory.BLUNDER

        if cpl is None:
            # No centipawn signal and no mate transition: treat as best-effort
            # "good" so we never crash, but flag low information.
            reasons.append("insufficient_eval_data")
            return ReviewCategory.GOOD

        if cpl <= BEST_MOVE_CP:
            reasons.append("no_centipawn_loss")
            return ReviewCategory.BEST_MOVE
        if cpl <= EXCELLENT_CP:
            reasons.append("very_small_cp_loss")
            return ReviewCategory.EXCELLENT
        if cpl <= GOOD_CP:
            reasons.append("small_cp_loss")
            return ReviewCategory.GOOD
        if cpl <= INACCURACY_CP:
            reasons.append("moderate_cp_loss")
            return ReviewCategory.INACCURACY
        if cpl <= MISTAKE_CP:
            reasons.append("large_cp_loss")
            return ReviewCategory.MISTAKE

        reasons.append("very_large_cp_loss")
        return ReviewCategory.BLUNDER

    # ------------------------------------
    # Metrics helpers (all O(1))
    # ------------------------------------

    def _centipawn_loss(self, candidate):
        """
        Loss vs. the engine's best line, from the mover's perspective.

        Prefers deep analysis (best move cp on the BEFORE position) compared
        against the played move's resulting eval; falls back to the shallow
        timeline delta.
        """
        cp_after = candidate.evaluation_after.get("cp")

        if candidate.deep_cp is not None and cp_after is not None:
            # played-move eval (mover POV) = -cp_after
            loss = candidate.deep_cp - (-cp_after)
            return max(loss, 0)

        if candidate.evaluation_delta_cp is not None:
            return max(-candidate.evaluation_delta_cp, 0)

        return None

    def _forced_mate_allowed(self, candidate):
        # after position: side to move is the opponent. Positive mate there
        # means the opponent has forced mate, i.e. the mover allowed it.
        mate_after = candidate.evaluation_after.get("mate")
        return mate_after is not None and mate_after > 0

    def _mate_missed(self, candidate):
        # Best move had a forced mate for the mover, but the played move no
        # longer keeps a forced mate for the mover.
        if candidate.deep_mate is None or candidate.deep_mate <= 0:
            return False

        mate_after = candidate.evaluation_after.get("mate")
        mover_mate_after = -mate_after if mate_after is not None else None
        keeps_mate = mover_mate_after is not None and mover_mate_after > 0
        return not keeps_mate

    def _confidence(self, candidate, cpl):
        depth = candidate.deep_depth or 0
        depth_factor = min(depth / 30.0, 1.0)

        mate_certain = (
            candidate.deep_mate is not None
            or candidate.evaluation_after.get("mate") is not None
        )

        pv_agree = (
            candidate.deep_best_move is not None
            and candidate.played_move == candidate.deep_best_move
        )

        swing_factor = min((cpl or 0) / 300.0, 1.0)

        confidence = (
            0.4 * depth_factor
            + 0.3 * (1.0 if mate_certain else swing_factor)
            + 0.3 * (1.0 if pv_agree else 0.5)
        )

        return round(min(max(confidence, 0.0), 1.0), 4)

    def _severity(self, classification, cpl, mate_missed, forced_mate_allowed):
        if classification is None:
            return 0

        severity = _BASE_SEVERITY[classification]

        if mate_missed or forced_mate_allowed:
            severity = max(severity, MATE_BLUNDER_PRIORITY)

        # Nudge severity upward with centipawn loss (bounded).
        severity += min((cpl or 0) / 20.0, 20.0)

        return int(min(max(severity, 0), 100))
