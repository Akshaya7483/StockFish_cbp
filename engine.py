from cache import AnalysisCache
import threading
from utils import win_probability
from engine_manager import EngineManager
from analysis_service import AnalysisService
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
        self.analysis_service = AnalysisService(
            manager=self.manager,
            cache=self.cache,
            lock=self.lock,
            evaluate_first_move=self.evaluate_first_move,
            get_current_multipv=lambda: self.current_multipv,
            set_current_multipv=self._set_current_multipv,
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

            self.manager.protocol.send("ucinewgame")
            self.manager.protocol.send(f"position fen {fen}")
            self.manager.protocol.send(f"go depth {depth}")

            cp = None
            mate = None
            pv = []

            best_depth = 0

            while True:

                line = self.manager.protocol.read_line()

                if line.startswith("info"):

                    parts = line.split()

                    if "depth" in parts:

                        current_depth = int(parts[parts.index("depth") + 1])

                        if current_depth >= best_depth:

                            best_depth = current_depth

                            if "score" in parts:

                                idx = parts.index("score")
                                if parts[idx + 1] == "cp":
                                    cp = int(parts[idx + 2])
                                elif parts[idx + 1] == "mate":
                                    mate = int(parts[idx + 2])
                            if "pv" in parts:
                                pv_index = parts.index("pv")
                                pv = parts[pv_index + 1:]
                elif line.startswith("bestmove"):
                    parts = line.split()
                    bestmove = parts[1]
                    ponder = None
                    if "ponder" in parts:
                        ponder = parts[parts.index("ponder") + 1]
                        
                    response = {
                        "bestmove": bestmove,
                        "ponder": ponder,
                        "depth": best_depth,
                        "cp": cp,
                        "mate": mate,
                        "win_probability": win_probability(cp, mate),
                        "pv": pv,
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
            if multipv != self.current_multipv:
                self.manager.protocol.send(f"setoption name MultiPV value {multipv}")
                self.manager.protocol.send("isready")
                self.manager.protocol.read_until("readyok")
                self.current_multipv = multipv
            self.manager.protocol.send("ucinewgame")
            self.manager.protocol.send(f"position fen {fen}")
            self.manager.protocol.send(f"go depth {depth}")
            results = {}
            while True:
                line = self.manager.protocol.read_line()
                if line.startswith("info"):
                    parts = line.split()
                    if "multipv" not in parts:
                        continue
                    rank = int(parts[parts.index("multipv") + 1])
                    if rank not in results:
                        results[rank] = {
                            "rank": rank,
                            "cp": None,
                            "mate": None,
                            "pv": [],
                            "depth": 0
                        }
                    if "depth" in parts:
                        results[rank]["depth"] = int(parts[parts.index("depth") + 1])
                    if "score" in parts:
                        idx = parts.index("score")
                        if parts[idx + 1] == "cp":
                            results[rank]["cp"] = int(parts[idx + 2])
                        elif parts[idx + 1] == "mate":
                            results[rank]["mate"] = int(parts[idx + 2])

                    if "pv" in parts:
                        pv_index = parts.index("pv")
                        pv = parts[pv_index + 1:]
                        results[rank]["pv"] = pv
                        if len(pv):
                            results[rank]["bestmove"] = pv[0]

                elif line.startswith("bestmove"):
                    parts = line.split()
                    bestmove = parts[1]
                    ponder = None

                    if "ponder" in parts:
                        ponder = parts[parts.index("ponder") + 1]

                    response = {
                        "bestmove": bestmove,
                        "ponder": ponder,
                        "depth": depth,
                        "multipv": multipv,
                        "moves": [
                            results[k]
                            for k in sorted(results.keys())
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
        self.manager.protocol.send("ucinewgame")
        self.manager.protocol.send(f"position fen {fen} moves {move}")
        if movetime is not None:
            self.manager.protocol.send(f"go movetime {movetime}")
        else:
            self.manager.protocol.send(f"go depth {depth or DEFAULT_DEPTH}")
        cp = None
        mate = None
        while True:
            line = self.manager.protocol.read_line()
            if line.startswith("info"):
                parts = line.split()
                if "score" in parts:
                    idx = parts.index("score")
                    if parts[idx + 1] == "cp":
                        cp = int(parts[idx + 2])
                    elif parts[idx + 1] == "mate":
                        mate = int(parts[idx + 2])
            elif line.startswith("bestmove"):
                return {
                    "cp": cp,
                    "mate": mate
                }
   
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
