from cache import AnalysisCache
import os
import subprocess
import threading
import time
from utils import win_probability
from uci_protocol import UCIProtocol
from config import (
    ENGINE_PATH,
    THREADS,
    HASH_MB,
    DEFAULT_MULTIPV,
    DEFAULT_DEPTH,
    FIRST_MOVE_DEPTH,
    FIRST_MOVE_TIME,
    CACHE_SIZE,
)
class StockfishEngine:
    def __init__(self):

        # Select correct engine depending on OS
        self.engine_path = ENGINE_PATH
        if os.name != "nt":
            os.chmod(self.engine_path, 0o755)

        # Start Stockfish
        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        self.protocol = UCIProtocol(self.process)
        self.protocol.restart = self.restart

        # Prevent concurrent requests from mixing stdout
        self.lock = threading.Lock()
        self.current_multipv = DEFAULT_MULTIPV
        self.cache = AnalysisCache(max_size=CACHE_SIZE)

        # Statistics
        self.start_time = time.time()

        self.total_requests = 0
        self.bestmove_requests = 0
        self.multipv_requests = 0
        self.analyze_requests = 0

        self.cache_hits = 0
        self.cache_misses = 0

        self.initialize()

    # -------------------------
    # Engine initialization
    # -------------------------
        # -------------------------
    # Restart Engine
    # -------------------------

    def restart(self):
        print("Restarting Stockfish...")

        try:
            if self.process:
                self.process.kill()
                self.process.wait(timeout=2)
        except Exception:
            pass

        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.protocol.attach_process(self.process)

        self.current_multipv = DEFAULT_MULTIPV

        self.initialize()

        print("Stockfish restarted successfully.")

    def initialize(self):

        self.protocol.send("uci")
        self.protocol.read_until("uciok")
        self.threads = THREADS
        self.hash_mb = HASH_MB
        self.default_multipv = DEFAULT_MULTIPV

        self.protocol.send(f"setoption name Threads value {self.threads}")
        self.protocol.send(f"setoption name Hash value {self.hash_mb}")
        self.protocol.send(f"setoption name MultiPV value {self.default_multipv}")

        self.protocol.send("isready")
        self.protocol.read_until("readyok")

    def health(self):
        running = self.process.poll() is None

        return {
            "status": "healthy" if running else "unhealthy",
            "engine_running": running,
            "pid": self.process.pid if running else None,
            "threads": self.threads,
            "hash_mb": self.hash_mb,

            "cache_entries": len(self.cache.cache),
            "uptime_seconds": int(time.time() - self.start_time),
        }
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

            self.protocol.send("ucinewgame")
            self.protocol.send(f"position fen {fen}")
            self.protocol.send(f"go depth {depth}")

            cp = None
            mate = None
            pv = []

            best_depth = 0

            while True:

                line = self.protocol.read_line()

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
                self.protocol.send(f"setoption name MultiPV value {multipv}")
                self.protocol.send("isready")
                self.protocol.read_until("readyok")
                self.current_multipv = multipv
            self.protocol.send("ucinewgame")
            self.protocol.send(f"position fen {fen}")
            self.protocol.send(f"go depth {depth}")
            results = {}
            while True:
                line = self.protocol.read_line()
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
        with self.lock:
            self.total_requests += 1
            self.analyze_requests += 1
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
                self.cache_hits += 1
                cached = cached.copy()
                cached["cached"] = True
                print("ANALYZE CACHE HIT")
                return cached
            self.cache_misses += 1
            print("ANALYZE CACHE MISS")
            # Configure MultiPV for this search
            if multipv != self.current_multipv:
                self.protocol.send(f"setoption name MultiPV value {multipv}")
                self.protocol.send("isready")
                self.protocol.read_until("readyok")
                self.current_multipv = multipv
            self.protocol.send("ucinewgame")
            self.protocol.send(f"position fen {current_fen}")
            if movetime is not None:
                self.protocol.send(f"go movetime {movetime}")
            else:
                go_command = "go"
                if depth is not None:
                    go_command += f" depth {depth}"
                if movetime is not None:
                    go_command += f" movetime {movetime}"
                self.protocol.send(go_command)
            results = {}
            while True:
                line = self.protocol.read_line()
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
                        self.protocol.send("ucinewgame")
                        self.protocol.send(f"position fen {previous_fen}")
                        if movetime is not None:
                            self.protocol.send(f"go movetime {movetime}")
                        else:
                            self.protocol.send(f"go depth {depth or DEFAULT_DEPTH}")
                        while True:
                            prev = self.protocol.read_line()
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
        self.protocol.send("ucinewgame")
        self.protocol.send(f"position fen {fen} moves {move}")
        if movetime is not None:
            self.protocol.send(f"go movetime {movetime}")
        else:
            self.protocol.send(f"go depth {depth or DEFAULT_DEPTH}")
        cp = None
        mate = None
        while True:
            line = self.protocol.read_line()
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

        uptime = int(time.time() - self.start_time)

        total_cache = self.cache_hits + self.cache_misses

        hit_rate = (
            round(self.cache_hits * 100 / total_cache, 2)
            if total_cache else 0
        )

        return {
            "status": "online",
            "engine": "Stockfish 18.1",
            "uptime_seconds": uptime,
            "threads": self.threads,
            "hash_mb": self.hash_mb,
            "default_multipv": self.default_multipv,


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
    # -------------------------
    # Shutdown
    # -------------------------

    def stop(self):
        self.protocol.send("quit")
        self.process.terminate()
