import io
from time import perf_counter
from datetime import datetime, timezone
import chess
import chess.pgn

from analysis_context import AnalysisContext
from candidate_detection_stage import CandidateDetectionStage
from candidate_enrichment_stage import CandidateEnrichmentStage
from review_classification_stage import ReviewClassificationStage
from brilliancy_detection_stage import BrilliancyDetectionStage
from accuracy_engine_stage import AccuracyEngineStage
from game_phase_detection_stage import GamePhaseDetectionStage
from critical_position_stage import CriticalPositionStage


class GameAnalysisPipeline:
    """
    Central coordinator for full-game analysis.

    Orchestrates PGN parsing, move-by-move engine analysis, and response
    construction. Engine work is delegated to StockfishEngine.analyze()
    exactly as before; this class only reorganizes responsibilities.
    """

    def __init__(self):
        self.candidate_stage = CandidateDetectionStage()
        self.enrichment_stage = CandidateEnrichmentStage()
        self.review_stage = ReviewClassificationStage()
        self.brilliancy_stage = BrilliancyDetectionStage()
        self.accuracy_stage = AccuracyEngineStage()
        self.game_phase_stage = GamePhaseDetectionStage()
        self.critical_position_stage = CriticalPositionStage()

    def analyze_game(
        self,
        engine,
        pgn: str,
        depth=None,
        movetime=None,
        multipv=3,
    ):
        """
        Analyze an entire PGN.

        Output:
            - Game metadata
            - Timeline
            - Raw Stockfish analysis

        No review logic (accuracy, blunders, CPL, etc.)
        """
        ctx = AnalysisContext(
            pgn=pgn,
            depth=depth,
            movetime=movetime,
            multipv=multipv,
            engine=engine,
            analysis_start_time=perf_counter(),
        )

        game = self.parse_game(ctx)
        state = self.prepare_analysis(ctx, game)

        for ply, move in enumerate(game.mainline_moves(), start=1):
            self.analyze_move(ctx, state, ply, move)

        self.finalize_analysis(ctx, state)

        return self.build_response(ctx, state)

    # ------------------------------------
    # Stage 1: Parse
    # ------------------------------------

    def parse_game(self, ctx: AnalysisContext):
        game = chess.pgn.read_game(io.StringIO(ctx.pgn))

        if game is None:
            raise ValueError("Invalid PGN.")

        return game

    # ------------------------------------
    # Stage 2: Prepare
    # ------------------------------------

    def prepare_analysis(self, ctx: AnalysisContext, game):
        generated_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        ctx.total_moves = sum(1 for _ in game.mainline_moves())

        state = {
            "board": game.board(),
            "headers": game.headers,
            "generated_at": generated_at,
            "timeline": [],
            "previous_fen": None,
            "before_analysis": None,
            "total_analysis_time_ms": 0,
        }

        return state

    # ------------------------------------
    # Stage 3: Analyze a single move
    # ------------------------------------

    def analyze_move(self, ctx: AnalysisContext, state, ply, move):
        ctx.current_move_index = ply

        board = state["board"]

        # ------------------------------------
        # Position BEFORE move
        # ------------------------------------

        before_fen = board.fen()

        san = board.san(move)

        if state["before_analysis"] is None:

            state["before_analysis"] = ctx.engine.analyze(
                current_fen=before_fen,
                previous_fen=state["previous_fen"],
                depth=ctx.depth,
                movetime=ctx.movetime,
                multipv=ctx.multipv,
            )

            analysis_before = state["before_analysis"].get("analysis", [])

            if analysis_before:
                state["total_analysis_time_ms"] += analysis_before[0].get("time_ms", 0)

            ctx.positions_analyzed += 1

        before_analysis = state["before_analysis"]

        # ------------------------------------
        # Play move
        # ------------------------------------

        board.push(move)

        after_fen = board.fen()

        # ------------------------------------
        # Position AFTER move
        # ------------------------------------

        after_analysis = ctx.engine.analyze(
            current_fen=after_fen,
            previous_fen=before_fen,
            depth=ctx.depth,
            movetime=ctx.movetime,
            multipv=ctx.multipv,
        )

        analysis_after = after_analysis.get("analysis", [])

        if analysis_after:
            state["total_analysis_time_ms"] += analysis_after[0].get("time_ms", 0)

        ctx.positions_analyzed += 1

        # ------------------------------------
        # Extract Rank-1 analysis
        # ------------------------------------
        analysis_before = before_analysis.get("analysis", [])
        analysis_after = after_analysis.get("analysis", [])

        before_line = (
            analysis_before[0]
            if analysis_before
            else {}
        )

        after_line = (
            analysis_after[0]
            if analysis_after
            else {}
        )

        state["timeline"].append({

            # -----------------------------
            # Move Information
            # -----------------------------

            "ply": ply,

            "move_number": (ply + 1) // 2,

            "side": "white" if ply % 2 else "black",

            "played_move": move.uci(),

            "played_move_san": san,

            # -----------------------------
            # Positions
            # -----------------------------

            "before_fen": before_fen,

            "after_fen": after_fen,

            # -----------------------------
            # Engine recommendation
            # -----------------------------

            "engine_best_move":
                before_analysis.get("bestmove"),

            "engine_ponder":
                before_analysis.get("ponder"),

            "is_best_move":
                move.uci() == before_analysis.get("bestmove"),

            # -----------------------------
            # Before evaluation
            # -----------------------------

            "evaluation_before": {

                "cp": before_line.get("cp"),

                "mate": before_line.get("mate"),

            },

            # -----------------------------
            # After evaluation
            # -----------------------------

            "evaluation_after": {

                "cp": after_line.get("cp"),

                "mate": after_line.get("mate"),

            },

            # -----------------------------
            # Engine Search Summary
            # -----------------------------

            "engine_info_before": {

                "depth": before_line.get("depth"),

                "nodes": before_line.get("nodes"),

                "time_ms": before_line.get("time_ms"),

                "pv": before_line.get("pv"),

            },

            "engine_info_after": {

                "depth": after_line.get("depth"),

                "nodes": after_line.get("nodes"),

                "time_ms": after_line.get("time_ms"),

                "pv": after_line.get("pv"),

            },

            # -----------------------------
            # Full Engine Output
            # -----------------------------

            "before_analysis": before_analysis,

            "after_analysis": after_analysis,

        })

        state["previous_fen"] = before_fen
        state["before_analysis"] = after_analysis

    # ------------------------------------
    # Stage 4: Finalize
    # ------------------------------------

    def finalize_analysis(self, ctx: AnalysisContext, state):
        positions_analyzed = ctx.positions_analyzed
        total_analysis_time_ms = state["total_analysis_time_ms"]

        state["average_analysis_time_ms"] = (
            round(total_analysis_time_ms / positions_analyzed)
            if positions_analyzed
            else 0
        )

        state["overall_execution_time_ms"] = round(
            (perf_counter() - ctx.analysis_start_time) * 1000,
            2
        )

        # Candidate detection populates ctx.candidates and returns the
        # timeline unchanged. Future stages consume ctx.candidates.
        state["timeline"] = self.candidate_stage.run(ctx, state["timeline"])

        # Candidate enrichment adds deeper engine analysis to ctx.candidates
        # only. It does not touch the timeline or the response.
        self.enrichment_stage.run(ctx)

        # Review classification categorizes enriched candidates into
        # ctx.reviews. No engine work, no response/timeline changes.
        self.review_stage.run(ctx)

        # Brilliancy detection flags Great/Brilliant moves from ctx.reviews.
        # No engine work, no response/timeline changes.
        self.brilliancy_stage.run(ctx)

        # Accuracy engine (Step 1: foundation only). Establishes ctx.accuracy
        # structures. No engine work, no response/timeline changes.
        self.accuracy_stage.run(ctx)

        # Game phase detection (Step 2: opening detection). Classifies each
        # timeline move into ctx.game_phases. No engine work, no
        # response/timeline changes.
        self.game_phase_stage.run(ctx, state["timeline"])

        # Critical position detection. Combines reviews, brilliancies, game
        # phases and the timeline into ctx.critical_positions. No engine work,
        # no response/timeline changes.
        self.critical_position_stage.run(ctx, state["timeline"])

        state["timeline"] = self._stage4_analysis(ctx, state["timeline"])

    # ------------------------------------
    # Stage 5: Build response
    # ------------------------------------

    def build_response(self, ctx: AnalysisContext, state):
        headers = state["headers"]
        timeline = state["timeline"]
        total_analysis_time_ms = state["total_analysis_time_ms"]

        return {

            # ---------------------------------
            # Analysis Metadata
            # ---------------------------------

            "generated_at": state["generated_at"],

            "analysis_engine": "Stockfish 18.1",

            "analysis_settings": {

                "depth": ctx.depth,

                "movetime": ctx.movetime,

                "multipv": ctx.multipv,

            },

            "analysis_summary": {

                # ---------------------------------
                # Engine Statistics
                # ---------------------------------

                "positions_analyzed": ctx.positions_analyzed,

                "engine_analysis_time_ms": total_analysis_time_ms,

                "engine_analysis_time_seconds": round(
                    total_analysis_time_ms / 1000,
                    2,
                ),

                "average_analysis_time_ms": state["average_analysis_time_ms"],

                # ---------------------------------
                # End-to-End Execution
                # ---------------------------------

                "total_execution_time_ms": state["overall_execution_time_ms"],

                "total_execution_time_seconds": round(
                    state["overall_execution_time_ms"] / 1000,
                    2,
                ),

            },

            # ---------------------------------
            # Game Metadata
            # ---------------------------------

            "game": {

                "event": headers.get("Event"),

                "site": headers.get("Site"),

                "date": headers.get("Date"),

                "round": headers.get("Round"),

                "white": headers.get("White"),

                "black": headers.get("Black"),

                "white_elo": headers.get("WhiteElo"),

                "black_elo": headers.get("BlackElo"),

                "result": headers.get("Result"),

                "termination": headers.get("Termination"),

                "time_control": headers.get("TimeControl"),

                "eco": headers.get("ECO"),

                "eco_url": headers.get("ECOUrl"),

                "opening": headers.get("Opening"),

                "variation": headers.get("Variation"),

                "utc_date": headers.get("UTCDate"),

                "utc_time": headers.get("UTCTime"),

                "start_time": headers.get("StartTime"),

                "end_time": headers.get("EndTime"),

                "link": headers.get("Link"),

            },

            # ---------------------------------
            # Timeline
            # ---------------------------------

            "total_plies": len(timeline),

            "timeline": timeline,

            # ---------------------------------
            # Accuracy Engine (Phase 12)
            # ---------------------------------

            "accuracy": self._build_accuracy_response(ctx),

            # ---------------------------------
            # Game Phase Detection (Phase 13)
            # ---------------------------------

            "game_phases": self._build_game_phase_response(ctx),

            # ---------------------------------
            # Critical Position Detection (Phase 14)
            # ---------------------------------

            "critical_positions": self._build_critical_position_response(ctx),

        }

    # ------------------------------------
    # Critical position response mapping
    # ------------------------------------

    def _build_critical_position_response(self, ctx: AnalysisContext):
        """
        Map ctx.critical_position_summary + statistics into the API
        "critical_positions" section. Pure value mapping — no calculations.
        Returns None if no summary exists.
        """
        summary = ctx.critical_position_summary
        if summary is None:
            return None

        statistics = ctx.critical_position_statistics or {}

        return {
            "total_positions": statistics.get("total_positions", 0),
            "critical_positions": statistics.get("critical_positions", 0),
            "critical_percentage": statistics.get("critical_percentage", 0.0),
            "highest_severity": summary.highest_severity,
            "opening_critical": summary.opening_critical,
            "middlegame_critical": summary.middlegame_critical,
            "endgame_critical": summary.endgame_critical,
            "white_critical": summary.white_critical,
            "black_critical": summary.black_critical,
        }

    # ------------------------------------
    # Game phase response mapping
    # ------------------------------------

    def _build_game_phase_response(self, ctx: AnalysisContext):
        """
        Map ctx.game_phase_summary into the API "game_phases" section. Pure
        value mapping — no calculations. Returns None if no summary exists.
        """
        summary = ctx.game_phase_summary
        if summary is None:
            return None

        return {
            "opening_moves": summary.opening_moves,
            "middlegame_moves": summary.middlegame_moves,
            "endgame_moves": summary.endgame_moves,
            "unknown_moves": summary.unknown_moves,
            "opening_percentage": summary.opening_percentage,
            "middlegame_percentage": summary.middlegame_percentage,
            "endgame_percentage": summary.endgame_percentage,
            "dominant_phase": summary.dominant_phase,
        }

    # ------------------------------------
    # Accuracy response mapping
    # ------------------------------------

    def _build_accuracy_response(self, ctx: AnalysisContext):
        """
        Map ctx.accuracy_summary into the API "accuracy" section. Pure value
        mapping — no calculations, reads nothing but the summary. Returns None
        if no summary is available.
        """
        summary = ctx.accuracy_summary
        if summary is None:
            return None

        return {
            "overall_average_accuracy": summary.overall_average_accuracy,
            "overall_average_cpl": summary.overall_average_cpl,

            "white": {
                "moves": summary.white_moves,
                "average_accuracy": summary.white_average_accuracy,
                "average_cpl": summary.white_average_cpl,
            },

            "black": {
                "moves": summary.black_moves,
                "average_accuracy": summary.black_average_accuracy,
                "average_cpl": summary.black_average_cpl,
            },

            "best_player": summary.best_player,
            "best_player_accuracy": summary.best_player_accuracy,

            "worst_player": summary.worst_player,
            "worst_player_accuracy": summary.worst_player_accuracy,

            "total_moves": summary.total_moves,
            "evaluated_moves": summary.evaluated_moves,
            "failed_moves": summary.failed_moves,
        }

    # ------------------------------------
    # Extension points (future review stages)
    #
    # These are intentionally empty for now and MUST return the
    # results unchanged. They exist so later phases (candidate
    # detection, brilliance analysis, etc.) can hook in without
    # restructuring the pipeline.
    # ------------------------------------

    def _stage4_analysis(self, ctx: AnalysisContext, results):
        return results
