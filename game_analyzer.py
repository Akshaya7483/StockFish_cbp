import io
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

        Returns one analysis object per ply.
        """

        game = chess.pgn.read_game(io.StringIO(pgn))

        if game is None:
            raise ValueError("Invalid PGN.")

        board = game.board()

        timeline = []

        previous_fen = None

        for ply, move in enumerate(game.mainline_moves(), start=1):

            board.push(move)

            current_fen = board.fen()

            result = self.engine.analyze(
                current_fen=current_fen,
                previous_fen=previous_fen,
                depth=depth,
                movetime=movetime,
                multipv=multipv,
            )

            timeline.append({
                "ply": ply,
                "move": board.peek().uci(),
                "fen": current_fen,
                "analysis": result,
            })

            previous_fen = current_fen

        return {
            "total_plies": len(timeline),
            "timeline": timeline,
        }