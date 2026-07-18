from time import perf_counter

from criticality import Criticality, rank
from critical_position import CriticalPosition
from critical_position_summary import CriticalPositionSummary
from review import ReviewCategory
from brilliancy import BrilliancyCategory
from game_phase import GamePhase
from config import CRITICAL_SWING_CP, WINNING_ADVANTAGE_CP


# A position counts as "critical" at or above this severity rank.
_CRITICAL_RANK = rank(Criticality.HIGH)


class CriticalPositionStage:
    """
    Critical Position Detection (Phase 14).

    Purely analytical stage that identifies the most critical moves of a game
    by combining data already produced by earlier stages (reviews, brilliancies,
    game phases, and the timeline). It performs no Stockfish searches, no
    evaluation recalculation and no timeline changes.

    Moves are matched to reviews / brilliancies / phases by ply (never by list
    index). Each move is scored into a Criticality level with a single primary
    reason; the critical subset, statistics and a typed summary are stored on
    the context.
    """

    def run(self, ctx, timeline=None):
        start = perf_counter()

        timeline = timeline if timeline is not None else getattr(ctx, "timeline", []) or []

        review_by_ply = self._index_by_ply(
            ctx.reviews, lambda r: r.candidate.ply
        )
        brilliancy_by_ply = self._index_by_ply(
            ctx.brilliancies, lambda b: b.review.candidate.ply
        )
        phase_by_ply = self._index_by_ply(
            ctx.game_phases, lambda p: p.ply
        )

        positions = []
        for entry in timeline:
            positions.append(self._build_position(
                entry,
                review_by_ply,
                brilliancy_by_ply,
                phase_by_ply,
            ))

        critical = [p for p in positions if self._is_critical(p.severity)]

        ctx.critical_positions = critical
        ctx.critical_position_statistics = self._compute_statistics(positions, critical)
        ctx.critical_position_summary = self._build_summary(positions, critical)

        ctx.critical_position_generation_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )

        return ctx

    # ------------------------------------
    # Per-move construction (failure isolated)
    # ------------------------------------

    def _build_position(self, entry, review_by_ply, brilliancy_by_ply, phase_by_ply):
        ply = entry.get("ply")
        try:
            review = review_by_ply.get(ply)
            brilliancy = brilliancy_by_ply.get(ply)
            phase = self._phase_value(phase_by_ply.get(ply))

            before, after, delta = self._evaluations(entry, review)
            severity, reason = self._severity_and_reason(before, after, review, brilliancy)

            return CriticalPosition(
                ply=ply,
                move_number=entry.get("move_number"),
                side=entry.get("side"),
                played_move=entry.get("played_move"),
                phase=phase,
                severity=severity,
                reason=reason,
                evaluation_before=before,
                evaluation_after=after,
                evaluation_delta_cp=delta,
                review=review,
                brilliancy=brilliancy,
            )
        except Exception as e:
            return CriticalPosition(
                ply=ply,
                move_number=entry.get("move_number"),
                side=entry.get("side"),
                played_move=entry.get("played_move"),
                phase=None,
                severity=Criticality.LOW,
                reason="error",
                error=str(e),
            )

    # ------------------------------------
    # Severity + reason
    # ------------------------------------

    def _severity_and_reason(self, before, after, review, brilliancy):
        """
        Resolve a single Criticality + primary reason from existing data,
        following the priority: mate > blunder > brilliant > large swing >
        mistake > great move > inaccuracy > quiet.
        """
        if self._mate_present(before, after):
            return Criticality.CRITICAL, "forced mate"

        if self._is_category(review, ReviewCategory.BLUNDER):
            reason = "winning advantage lost" if self._was_winning(before) else "blunder"
            return Criticality.CRITICAL, reason

        if self._is_brilliancy(brilliancy, BrilliancyCategory.BRILLIANT_MOVE):
            reason = "only move" if brilliancy.metadata.get("only_move") else "brilliant resource"
            return Criticality.VERY_HIGH, reason

        if self._large_swing(before, after, review):
            return Criticality.VERY_HIGH, "large evaluation swing"

        if self._is_category(review, ReviewCategory.MISTAKE):
            return Criticality.HIGH, "missed tactic"

        if self._is_brilliancy(brilliancy, BrilliancyCategory.GREAT_MOVE):
            return Criticality.MEDIUM, "great move"

        if self._is_category(review, ReviewCategory.INACCURACY):
            return Criticality.MEDIUM, "inaccuracy"

        return Criticality.LOW, "quiet move"

    # ------------------------------------
    # Evaluation helpers
    # ------------------------------------

    def _evaluations(self, entry, review):
        """
        Prefer the (already-computed) review evaluations; otherwise fall back
        to the timeline entry. Never recomputes an engine evaluation.
        """
        if review is not None:
            return (
                review.evaluation_before,
                review.evaluation_after,
                review.evaluation_delta_cp,
            )

        before = entry.get("evaluation_before")
        after = entry.get("evaluation_after")
        return before, after, self._delta_from_evals(before, after)

    def _delta_from_evals(self, before, after):
        """Mover-perspective centipawn loss from timeline evaluations."""
        cp_before = (before or {}).get("cp")
        cp_after = (after or {}).get("cp")
        if cp_before is None or cp_after is None:
            return None
        # after is from the opponent's perspective, so negate it to compare.
        return cp_before - (-cp_after)

    def _mate_present(self, before, after):
        return (
            (before or {}).get("mate") is not None
            or (after or {}).get("mate") is not None
        )

    def _was_winning(self, before):
        cp_before = (before or {}).get("cp")
        return cp_before is not None and cp_before >= WINNING_ADVANTAGE_CP

    def _large_swing(self, before, after, review):
        if review is not None and review.centipawn_loss is not None:
            return review.centipawn_loss >= CRITICAL_SWING_CP
        delta = self._delta_from_evals(before, after)
        return delta is not None and abs(delta) >= CRITICAL_SWING_CP

    # ------------------------------------
    # Matching / small predicates
    # ------------------------------------

    def _is_category(self, review, category):
        return review is not None and review.classification == category

    def _is_brilliancy(self, brilliancy, category):
        return brilliancy is not None and brilliancy.category == category

    def _is_critical(self, severity):
        return rank(severity) >= _CRITICAL_RANK

    def _phase_value(self, phase_result):
        if phase_result is None:
            return GamePhase.UNKNOWN.value
        return phase_result.phase.value

    def _index_by_ply(self, items, key):
        index = {}
        for item in items:
            try:
                index[key(item)] = item
            except Exception:
                continue
        return index

    # ------------------------------------
    # Statistics + summary
    # ------------------------------------

    def _compute_statistics(self, positions, critical):
        total = len(positions)

        def count(level):
            return sum(1 for p in positions if p.severity == level)

        critical_count = len(critical)

        return {
            "total_positions": total,
            "critical_positions": critical_count,
            "critical_percentage": round(critical_count / total * 100, 2) if total else 0.0,
            "low": count(Criticality.LOW),
            "medium": count(Criticality.MEDIUM),
            "high": count(Criticality.HIGH),
            "very_high": count(Criticality.VERY_HIGH),
            "critical": count(Criticality.CRITICAL),
        }

    def _build_summary(self, positions, critical):
        return CriticalPositionSummary(
            critical_positions=len(critical),
            critical_moves=len(critical),
            highest_severity=self._highest_severity(positions),
            opening_critical=self._count_phase(critical, GamePhase.OPENING.value),
            middlegame_critical=self._count_phase(critical, GamePhase.MIDDLEGAME.value),
            endgame_critical=self._count_phase(critical, GamePhase.ENDGAME.value),
            white_critical=sum(1 for p in critical if p.side == "white"),
            black_critical=sum(1 for p in critical if p.side == "black"),
        )

    def _highest_severity(self, positions):
        if not positions:
            return None
        highest = max(positions, key=lambda p: rank(p.severity)).severity
        return highest.value

    def _count_phase(self, positions, phase_value):
        return sum(1 for p in positions if p.phase == phase_value)
