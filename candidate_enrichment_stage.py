from time import perf_counter

from config import (
    CANDIDATE_MULTIPV,
    CANDIDATE_DEPTH,
    CANDIDATE_MOVETIME,
)


class CandidateEnrichmentStage:
    """
    Enriches each detected Candidate with a deeper engine analysis of its
    BEFORE position, so later review/brilliancy/classification stages never
    need to re-search Stockfish.

    Only ctx.candidates receive additional engine work — the per-move
    timeline analysis is left untouched.

    Enrichment is designed to be parallelizable later: `_enrich` operates on
    a single candidate and does not touch shared mutable state, so candidates
    could be dispatched across multiple engines in the future. Parallelism is
    NOT implemented here.
    """

    def run(self, ctx):
        start = perf_counter()

        # Highest priority first, then earliest ply.
        ctx.candidates.sort(key=lambda c: (-c.priority, c.ply))

        enriched = 0
        total_candidate_ms = 0.0

        for candidate in ctx.candidates:
            candidate_start = perf_counter()
            try:
                self._enrich(ctx.engine, candidate)
                enriched += 1
            except Exception as e:
                # Failure isolation: record and continue.
                candidate.error = str(e)
            total_candidate_ms += (perf_counter() - candidate_start) * 1000

        ctx.enriched_candidates = enriched
        ctx.candidate_enrichment_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )
        ctx.average_candidate_analysis_ms = round(
            total_candidate_ms / len(ctx.candidates),
            4
        ) if ctx.candidates else 0.0

        return ctx

    def _enrich(self, engine, candidate):
        """
        Perform one additional analysis of the candidate's BEFORE position.

        Pure with respect to shared state: reads config + the engine and
        writes only to the given candidate.
        """
        result = engine.analyze(
            current_fen=candidate.before_fen,
            previous_fen=None,
            depth=CANDIDATE_DEPTH,
            movetime=CANDIDATE_MOVETIME,
            multipv=CANDIDATE_MULTIPV,
        )

        analysis = result.get("analysis", []) if result else []
        top = analysis[0] if analysis else {}

        candidate.deep_analysis = result
        candidate.deep_best_move = result.get("bestmove") if result else None
        candidate.deep_pv = top.get("pv")
        candidate.deep_cp = top.get("cp")
        candidate.deep_mate = top.get("mate")
        candidate.deep_depth = top.get("depth")
        candidate.deep_nodes = top.get("nodes")
        candidate.deep_time_ms = top.get("time_ms")
        candidate.deep_win_probability = (
            result.get("win_probability") if result else None
        )
