from time import perf_counter

from candidate import Candidate
from config import (
    CANDIDATE_CP_THRESHOLD,
    MATE_PRIORITY,
    PV_CHANGE_PRIORITY,
)


class CandidateDetectionStage:
    """
    Identifies positions worthy of deeper analysis using only the existing
    timeline. Performs no Stockfish searches and runs in O(n) over the plies.

    Populates ctx.candidates and leaves the timeline untouched.
    """

    def run(self, ctx, timeline):
        start = perf_counter()

        candidates = []
        for entry in timeline:
            candidate = self._evaluate_entry(entry)
            if candidate is not None:
                candidates.append(candidate)

        ctx.candidates = candidates
        ctx.candidates_found = len(candidates)
        ctx.candidate_generation_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )

        # Timeline is returned unchanged.
        return timeline

    # ------------------------------------
    # Per-move heuristics (all O(1))
    # ------------------------------------

    def _evaluate_entry(self, entry):
        eval_before = entry.get("evaluation_before", {}) or {}
        eval_after = entry.get("evaluation_after", {}) or {}

        priority = 0
        reasons = []

        # 1. Played move differs from engine's best move.
        engine_best_move = entry.get("engine_best_move")
        is_best_move = entry.get("is_best_move", False)
        if engine_best_move is not None and not is_best_move:
            priority += 1
            reasons.append("played_move_differs_from_best")

        # 2. Mate score appears / disappears (from the mover's perspective).
        mate_before = eval_before.get("mate")
        mate_after = eval_after.get("mate")
        mover_mate_after = -mate_after if mate_after is not None else None

        if mate_before is None and mover_mate_after is not None:
            priority += MATE_PRIORITY
            reasons.append("mate_appeared")
        elif mate_before is not None and mover_mate_after is None:
            priority += MATE_PRIORITY
            reasons.append("mate_disappeared")

        # 3. Evaluation swing / large centipawn loss (mover's perspective).
        delta_cp = self._evaluation_delta_cp(eval_before, eval_after)
        if delta_cp is not None:
            if abs(delta_cp) >= CANDIDATE_CP_THRESHOLD:
                priority += 1
                reasons.append("evaluation_swing")
            if delta_cp <= -CANDIDATE_CP_THRESHOLD:
                priority += 1
                reasons.append("large_centipawn_loss")

        # 4. Principal variation changes significantly: the best move was
        #    played, but the engine's expected continuation no longer holds.
        if self._pv_changed(entry):
            priority += PV_CHANGE_PRIORITY
            reasons.append("pv_change")

        if not reasons:
            return None

        return Candidate(
            ply=entry.get("ply"),
            move_number=entry.get("move_number"),
            side=entry.get("side"),
            played_move=entry.get("played_move"),
            before_fen=entry.get("before_fen"),
            after_fen=entry.get("after_fen"),
            engine_best_move=engine_best_move,
            evaluation_before=eval_before,
            evaluation_after=eval_after,
            evaluation_delta_cp=delta_cp,
            is_best_move=is_best_move,
            priority=priority,
            reasons=reasons,
        )

    def _evaluation_delta_cp(self, eval_before, eval_after):
        """
        Change in evaluation from the mover's perspective.

        `evaluation_before` is scored for the side to move; `evaluation_after`
        is scored for the opponent, so it is negated before comparing.
        Returns None if either side lacks a centipawn score (e.g. mate).
        """
        cp_before = eval_before.get("cp")
        cp_after = eval_after.get("cp")

        if cp_before is None or cp_after is None:
            return None

        mover_cp_after = -cp_after
        return mover_cp_after - cp_before

    def _pv_changed(self, entry):
        before_pv = (entry.get("engine_info_before", {}) or {}).get("pv") or []
        after_pv = (entry.get("engine_info_after", {}) or {}).get("pv") or []

        played_move = entry.get("played_move")

        # Only meaningful when the best move was actually played and the
        # engine had a concrete continuation to compare against.
        if len(before_pv) < 2 or not after_pv:
            return False

        if played_move != before_pv[0]:
            return False

        # Engine changed its mind about the follow-up it predicted.
        return after_pv[0] != before_pv[1]
