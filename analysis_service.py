from utils import win_probability
from config import (
    DEFAULT_MULTIPV,
    FIRST_MOVE_DEPTH,
    FIRST_MOVE_TIME,
)


class AnalysisService:
    def __init__(
        self,
        search_service,
        cache,
        lock,
        evaluate_first_move,
        on_request,
        on_cache_hit,
        on_cache_miss,
    ):
        self.search_service = search_service
        self.cache = cache
        self.lock = lock
        self.evaluate_first_move = evaluate_first_move
        self.on_request = on_request
        self.on_cache_hit = on_cache_hit
        self.on_cache_miss = on_cache_miss

    def analyze(
        self,
        current_fen: str,
        previous_fen: str | None = None,
        depth: int | None = None,
        movetime: int | None = None,
        multipv: int = DEFAULT_MULTIPV,
    ):
        with self.lock:
            self.on_request()
            cache_key = (
                "analyze",
                current_fen,
                previous_fen,
                depth,
                movetime,
                multipv
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.on_cache_hit()
                cached = cached.copy()
                cached["cached"] = True
                print("ANALYZE CACHE HIT")
                return cached
            self.on_cache_miss()
            print("ANALYZE CACHE MISS")

            result = self.search_service.search_analysis(
                current_fen=current_fen,
                previous_fen=previous_fen,
                depth=depth,
                movetime=movetime,
                multipv=multipv,
            )

            results = result["results"]
            for rank in sorted(results.keys()):
                move = results[rank].get("bestmove")
                if move:
                    results[rank]["first_move_score"] = self.evaluate_first_move(
                        current_fen,
                        move,
                        depth=FIRST_MOVE_DEPTH,
                        movetime=FIRST_MOVE_TIME,
                    )

            response = {
                "fen": current_fen,
                "bestmove": result["bestmove"],
                "ponder": result["ponder"],
                "previous_fen_bestmove": result["previous_bestmove"],
                "requested_depth": depth,
                "requested_movetime": movetime,
                "multipv": multipv,
                "win_probability": win_probability(
                    results[1]["cp"],
                    results[1]["mate"]
                ) if 1 in results else None,
                "analysis": [
                    results[k]
                    for k in sorted(results.keys())
                ],
                "cached": False
            }
            self.cache.set(cache_key, response)
            return response
