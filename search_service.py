from config import DEFAULT_DEPTH, DEFAULT_MULTIPV


class SearchService:
    def __init__(self, manager, get_current_multipv, set_current_multipv):
        self.manager = manager
        self.get_current_multipv = get_current_multipv
        self.set_current_multipv = set_current_multipv

    def _ensure_multipv(self, multipv):
        if multipv != self.get_current_multipv():
            self.manager.protocol.send(f"setoption name MultiPV value {multipv}")
            self.manager.protocol.send("isready")
            self.manager.protocol.read_until("readyok")
            self.set_current_multipv(multipv)

    def _parse_bestmove_line(self, line):
        parts = line.split()
        bestmove = parts[1]
        ponder = None
        if "ponder" in parts:
            ponder = parts[parts.index("ponder") + 1]
        return bestmove, ponder

    def search_bestmove(self, fen: str, depth: int):
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
                bestmove, ponder = self._parse_bestmove_line(line)
                return {
                    "bestmove": bestmove,
                    "ponder": ponder,
                    "depth": best_depth,
                    "cp": cp,
                    "mate": mate,
                    "pv": pv,
                }

    def search_multipv(self, fen: str, depth: int, multipv: int):
        self._ensure_multipv(multipv)
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
                bestmove, ponder = self._parse_bestmove_line(line)
                return {
                    "bestmove": bestmove,
                    "ponder": ponder,
                    "results": results,
                }

    def search_analysis(
        self,
        current_fen: str,
        previous_fen: str | None = None,
        depth: int | None = None,
        movetime: int | None = None,
        multipv: int = DEFAULT_MULTIPV,
    ):
        self._ensure_multipv(multipv)
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
                bestmove, ponder = self._parse_bestmove_line(line)
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
                return {
                    "bestmove": bestmove,
                    "ponder": ponder,
                    "results": results,
                    "previous_bestmove": previous_bestmove,
                }

    def evaluate_position_after_move(
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
