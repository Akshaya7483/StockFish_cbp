import os
import subprocess
import threading
import time
from queue import Queue, Empty
ENGINE_TIMEOUT = int(os.getenv("SF_TIMEOUT", "30"))
from utils import win_probability
class StockfishEngine:
    def __init__(self):

        # Select correct engine depending on OS
        if os.name == "nt":
            self.engine_path = "./stockfish-windows-x86-64-avx2.exe"
        else:
            self.engine_path = "./stockfish/stockfish-ubuntu-x86-64-avx2"
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

        # Prevent concurrent requests from mixing stdout
        self.lock = threading.Lock()
        self.current_multipv = 1

        # Queue for Stockfish output
        self.output_queue = Queue()

        # Background reader
        threading.Thread(
            target=self._reader,
            daemon=True
        ).start()

        self.initialize()

    # -------------------------
    # Low-level communication
    # -------------------------

    def send(self, command: str):

        if self.process.poll() is not None:
            self.restart()

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

        except (BrokenPipeError, OSError):
            self.restart()
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

    def _reader(self):

        try:
            while True:

                line = self.process.stdout.readline()

                if not line:
                    break

                self.output_queue.put(line.strip())

        finally:
            self.output_queue.put(None)
    
    def read_until(self, token: str):
        lines = []

        while True:
            line = self.read_line()

            if line:
                lines.append(line)

            if token in line:
                break

        return lines
    
    def read_line(self, timeout=ENGINE_TIMEOUT):

        if self.process.poll() is not None:
            self.restart()
            raise RuntimeError(
                "Stockfish restarted. Please retry the request."
            )

        try:
            line = self.output_queue.get(timeout=timeout)

            if line is None:
                raise RuntimeError(
                    "Stockfish reader thread stopped."
                )

            return line

        except Empty:
            raise TimeoutError(
                f"Stockfish timed out after {timeout} seconds."
            )
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

        self.output_queue = Queue()

        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        threading.Thread(
            target=self._reader,
            daemon=True
        ).start()

        self.current_multipv = 1

        self.initialize()

        print("Stockfish restarted successfully.")

    def initialize(self):

        self.send("uci")
        self.read_until("uciok")

        self.send("setoption name Threads value 1")
        self.send("setoption name Hash value 256")
        self.send("setoption name MultiPV value 1")

        self.send("isready")
        self.read_until("readyok")

    # -------------------------
    # Best Move
    # -------------------------

    def bestmove(self, fen: str, depth: int = 18):

        with self.lock:

            self.send("ucinewgame")
            self.send(f"position fen {fen}")
            self.send(f"go depth {depth}")

            cp = None
            mate = None
            pv = []

            best_depth = 0

            while True:

                line = self.read_line()

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
                    return {
                        "bestmove": bestmove,
                        "ponder": ponder,
                        "depth": best_depth,
                        "cp": cp,
                        "mate": mate,
                        "win_probability": win_probability(cp, mate),
                        "pv": pv
                    }
            
    def multipv(self, fen: str, depth: int = 18, multipv: int = 3):
        with self.lock:
            if multipv != self.current_multipv:
                self.send(f"setoption name MultiPV value {multipv}")
                self.send("isready")
                self.read_until("readyok")
                self.current_multipv = multipv

            self.send("ucinewgame")
            self.send(f"position fen {fen}")
            self.send(f"go depth {depth}")

            results = {}

            while True:

                line = self.read_line()

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

                    return {
                        "bestmove": bestmove,
                        "ponder": ponder,
                        "depth": depth,
                        "multipv": multipv,
                        "moves": [
                            results[k]
                            for k in sorted(results.keys())
                        ]
                    }
    
    def analyze(
        self,
        fen: str,
        depth: int | None = None,
        movetime: int | None = None,
        multipv: int = 1,
    ):

        with self.lock:

            # Configure MultiPV for this search
            if multipv != self.current_multipv:
                self.send(f"setoption name MultiPV value {multipv}")
                self.send("isready")
                self.read_until("readyok")
                self.current_multipv = multipv

            self.send("ucinewgame")
            self.send(f"position fen {fen}")

            if movetime is not None:
                self.send(f"go movetime {movetime}")
            else:
                go_command = "go"
                if depth is not None:
                    go_command += f" depth {depth}"

                if movetime is not None:
                    go_command += f" movetime {movetime}"

                self.send(go_command)

            results = {}

            while True:
                line = self.read_line()

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

                elif line.startswith("bestmove"):

                    parts = line.split()

                    bestmove = parts[1]

                    ponder = None

                    if "ponder" in parts:
                        ponder = parts[parts.index("ponder") + 1]

                    return {
                        "fen": fen,
                        "bestmove": bestmove,
                        "ponder": ponder,
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
                        ]
                    }
    # -------------------------
    # Shutdown
    # -------------------------

    def stop(self):
        self.send("quit")
        self.process.terminate()