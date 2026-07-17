from utils import win_probability
from config import (
    DEFAULT_MULTIPV,
    DEFAULT_DEPTH,
    FIRST_MOVE_DEPTH,
    FIRST_MOVE_TIME,
)


class AnalysisService:
    def __init__(
        self,
        manager,
        cache,
        lock,
        evaluate_first_move,
        get_current_multipv,
        set_current_multipv,
        on_request,
        on_cache_hit,
        on_cache_miss,
    ):
        self.manager = manager
        self.cache = cache
        self.lock = lock
        self.evaluate_first_move = evaluate_first_move
        self.get_current_multipv = get_current_multipv
        self.set_current_multipv = set_current_multipv
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
            # Configure MultiPV for this search
            if multipv != self.get_current_multipv():
                self.manager.protocol.send(f"setoption name MultiPV value {multipv}")
                self.manager.protocol.send("isready")
                self.manager.protocol.read_until("readyok")
                self.set_current_multipv(multipv)
            self.manager.protocol.send("ucinewgame")
            self.manager.protocol.send(f"position fen {current_fen}")
            if movetime is not None:
                self.manager.protocol.send(f"go movetime {movetime}")
            else:
                go_command = "go"
                if depth is not None:
                    go_command += f" depth {depth}"
                if movetime is not None:
                    go_command += f" movetime {movetime}"
                self.manager.protocol.send(go_command)
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
                            "bestmove": None,
                            "cp": None,
                            "mate": None,
                            "depth": 0,
                            "seldepth": 0,
                            "nodes": 0,
                            "nps": 0,
                            "time_ms": 0,
                            "pv": [],
                        }
                    current = results[rank]
                    if "depth" in parts:
                        current["depth"] = int(parts[parts.index("depth") + 1])
                    if "seldepth" in parts:
                        current["seldepth"] = int(parts[parts.index("seldepth") + 1])
                    if "nodes" in parts:
                        current["nodes"] = int(parts[parts.index("nodes") + 1])
                    if "nps" in parts:
                        current["nps"] = int(parts[parts.index("nps") + 1])
                    if "time" in parts:
                        current["time_ms"] = int(parts[parts.index("time") + 1])
                    if "score" in parts:
                        idx = parts.index("score")
                        if parts[idx + 1] == "cp":
                            current["cp"] = int(parts[idx + 2])
                        elif parts[idx + 1] == "mate":
                            current["mate"] = int(parts[idx + 2])
                    if "pv" in parts:
                        pv_index = parts.index("pv")
                        current["pv"] = parts[pv_index + 1:]
                        if current["pv"]:
                            current["bestmove"] = current["pv"][0]
                            current["first_move_score"] = None
                elif line.startswith("bestmove"):
                    parts = line.split()
                    bestmove = parts[1]
                    ponder = None
                    if "ponder" in parts:
                        ponder = parts[parts.index("ponder") + 1]
                    previous_bestmove = None
                    if previous_fen:
                        self.manager.protocol.send("ucinewgame")
                        self.manager.protocol.send(f"position fen {previous_fen}")
                        if movetime is not None:
                            self.manager.protocol.send(f"go movetime {movetime}")
                        else:
                            self.manager.protocol.send(f"go depth {depth or DEFAULT_DEPTH}")
                        while True:
                            prev = self.manager.protocol.read_line()
                            if prev.startswith("bestmove"):
                                prev_parts = prev.split()
                                previous_bestmove = prev_parts[1]
                                break
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
                        "bestmove": bestmove,
                        "ponder": ponder,
                        "previous_fen_bestmove": previous_bestmove,
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
