import io
from datetime import datetime, timezone
import chess
import chess.pgn


class GameAnalyzer:

    def __init__(self, engine):
        self.engine = engine

    def analyze_game(
        self,
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

        game = chess.pgn.read_game(io.StringIO(pgn))

        if game is None:
            raise ValueError("Invalid PGN.")

        board = game.board()

        timeline = []

        previous_fen = None
        before_analysis = None
        # ------------------------------------
        # Analysis Statistics
        # ------------------------------------

        total_analysis_time_ms = 0
        positions_analyzed = 0

        headers = game.headers
        generated_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        for ply, move in enumerate(game.mainline_moves(), start=1):

            # ------------------------------------
            # Position BEFORE move
            # ------------------------------------

            before_fen = board.fen()

            san = board.san(move)

            if before_analysis is None:

                before_analysis = self.engine.analyze(
                    current_fen=before_fen,
                    previous_fen=previous_fen,
                    depth=depth,
                    movetime=movetime,
                    multipv=multipv,
                )

                analysis_before = before_analysis.get("analysis", [])

                if analysis_before:
                    total_analysis_time_ms += analysis_before[0].get("time_ms", 0)

                positions_analyzed += 1

            # ------------------------------------
            # Play move
            # ------------------------------------

            board.push(move)

            after_fen = board.fen()

            # ------------------------------------
            # Position AFTER move
            # ------------------------------------

            after_analysis = self.engine.analyze(
                current_fen=after_fen,
                previous_fen=before_fen,
                depth=depth,
                movetime=movetime,
                multipv=multipv,
            )

            analysis_after = after_analysis.get("analysis", [])

            if analysis_after:
                total_analysis_time_ms += analysis_after[0].get("time_ms", 0)

            positions_analyzed += 1

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

            timeline.append({

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

            previous_fen = before_fen
            before_analysis = after_analysis

        average_analysis_time_ms = (
        round(total_analysis_time_ms / positions_analyzed)
        if positions_analyzed
        else 0
    )
        
        return {

            # ---------------------------------
            # Analysis Metadata
            # ---------------------------------

            "generated_at": generated_at,

            "analysis_engine": "Stockfish 18.1",

            "analysis_settings": {

                "depth": depth,

                "movetime": movetime,

                "multipv": multipv,

            },

            "analysis_summary": {

                "positions_analyzed": positions_analyzed,

                "total_analysis_time_ms": total_analysis_time_ms,

                "total_analysis_time_seconds": round(
                    total_analysis_time_ms / 1000,
                    2,
                ),

                "average_analysis_time_ms": average_analysis_time_ms,

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

        }