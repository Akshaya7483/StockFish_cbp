from cache import AnalysisCache
import threading
from utils import win_probability
from engine_manager import EngineManager
from analysis_service import AnalysisService
from search_service import SearchService
from config import (
    DEFAULT_MULTIPV,
    DEFAULT_DEPTH,
    CACHE_SIZE,
)
class StockfishEngine:
    def __init__(self):

        # Prevent concurrent requests from mixing stdout
        self.lock = threading.Lock()
        self.current_multipv = DEFAULT_MULTIPV
        self.cache = AnalysisCache(max_size=CACHE_SIZE)

        # Statistics
        self.total_requests = 0
        self.bestmove_requests = 0
        self.multipv_requests = 0
        self.analyze_requests = 0

        self.cache_hits = 0
        self.cache_misses = 0

        self.manager = EngineManager(on_restart=self._reset_engine_state)
        self.search_service = SearchService(
            manager=self.manager,
            get_current_multipv=lambda: self.current_multipv,
            set_current_multipv=self._set_current_multipv,
        )
        self.analysis_service = AnalysisService(
            search_service=self.search_service,
            cache=self.cache,
            lock=self.lock,
            evaluate_first_move=self.evaluate_first_move,
            on_request=self._record_analyze_request,
            on_cache_hit=self._record_cache_hit,
            on_cache_miss=self._record_cache_miss,
        )

    def _reset_engine_state(self):
        self.current_multipv = DEFAULT_MULTIPV

    def _set_current_multipv(self, multipv):
        self.current_multipv = multipv

    def _record_analyze_request(self):
        self.total_requests += 1
        self.analyze_requests += 1

    def _record_cache_hit(self):
        self.cache_hits += 1

    def _record_cache_miss(self):
        self.cache_misses += 1

    def health(self):
        manager_health = self.manager.health()
        manager_health["cache_entries"] = len(self.cache.cache)
        return manager_health

    def stop(self):
        self.manager.stop()

    # -------------------------
    # Best Move
    # -------------------------

    def bestmove(self, fen: str, depth: int = DEFAULT_DEPTH):

        with self.lock:
            self.total_requests += 1
            self.bestmove_requests += 1
            cache_key = (
                "bestmove",
                fen,
                depth
            )

            cached = self.cache.get(cache_key)

            if cached is not None:
                self.cache_hits += 1
                print("BESTMOVE CACHE HIT")

                cached = cached.copy()
                cached["cached"] = True

                return cached
            self.cache_misses += 1
            print("BESTMOVE CACHE MISS")

            result = self.search_service.search_bestmove(fen, depth)

            response = {
                "bestmove": result["bestmove"],
                "ponder": result["ponder"],
                "depth": result["depth"],
                "cp": result["cp"],
                "mate": result["mate"],
                "win_probability": win_probability(result["cp"], result["mate"]),
                "pv": result["pv"],
                "cached": False
            }
            self.cache.set(cache_key, response)
            return response
            
    def multipv(self, fen: str, depth: int = DEFAULT_DEPTH, multipv: int = 3):
        with self.lock:
            self.total_requests += 1
            self.multipv_requests += 1
            cache_key = (
                "multipv",
                fen,
                depth,
                multipv
            )
            cached = self.cache.get(cache_key)

            if cached is not None:
                self.cache_hits += 1
                print("MULTIPV CACHE HIT")

                cached = cached.copy()
                cached["cached"] = True

                return cached
            self.cache_misses += 1
            print("MULTIPV CACHE MISS")

            result = self.search_service.search_multipv(fen, depth, multipv)

            response = {
                "bestmove": result["bestmove"],
                "ponder": result["ponder"],
                "depth": depth,
                "multipv": multipv,
                "moves": [
                    result["results"][k]
                    for k in sorted(result["results"].keys())
                ],
                "cached": False
            }
            self.cache.set(cache_key, response)
            return response
    
    def analyze(
        self,
        current_fen: str,
        previous_fen: str | None = None,
        depth: int | None = None,
        movetime: int | None = None,
        multipv: int = DEFAULT_MULTIPV,
    ):
        return self.analysis_service.analyze(
            current_fen=current_fen,
            previous_fen=previous_fen,
            depth=depth,
            movetime=movetime,
            multipv=multipv,
        )

    def evaluate_first_move(
        self,
        fen: str,
        move: str,
        depth: int | None = None,
        movetime: int | None = None,
    ):
        """
        Evaluate the position after making one move.
        """
        return self.search_service.evaluate_position_after_move(
            fen,
            move,
            depth=depth,
            movetime=movetime,
        )
   
    def stats(self):

        health = self.manager.health()

        total_cache = self.cache_hits + self.cache_misses

        hit_rate = (
            round(self.cache_hits * 100 / total_cache, 2)
            if total_cache else 0
        )

        return {
            "status": "online",
            "engine": "Stockfish 18.1",
            "uptime_seconds": health["uptime_seconds"],
            "threads": health["threads"],
            "hash_mb": health["hash_mb"],
            "default_multipv": self.manager.default_multipv,


            "requests": {
                "total": self.total_requests,
                "bestmove": self.bestmove_requests,
                "multipv": self.multipv_requests,
                "analyze": self.analyze_requests,
            },

            "cache": {
                "entries": len(self.cache.cache),
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": hit_rate
            }
        }
