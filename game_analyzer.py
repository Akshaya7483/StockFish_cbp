from game_analysis_pipeline import GameAnalysisPipeline


class GameAnalyzer:
    """
    Thin compatibility layer over GameAnalysisPipeline.

    Receives the pipeline via dependency injection and receives the engine
    when analysis starts, so no per-request objects need to be created.
    """

    def __init__(self, pipeline: GameAnalysisPipeline | None = None):
        self.pipeline = pipeline or GameAnalysisPipeline()

    def analyze_game(
        self,
        engine,
        pgn: str,
        depth=None,
        movetime=None,
        multipv=3,
    ):
        return self.pipeline.analyze_game(
            engine,
            pgn,
            depth=depth,
            movetime=movetime,
            multipv=multipv,
        )
