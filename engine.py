import os
import subprocess
import threading


class StockfishEngine:
    def __init__(self):

        if os.name == "nt":
            self.engine_path = "./stockfish-windows-x86-64-avx2.exe"
        else:
            self.engine_path = "./stockfish/stockfish-ubuntu-x86-64-avx2"
            os.chmod(self.engine_path, 0o755)

        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        self.lock = threading.Lock()

        self.initialize()

    def send(self, command: str):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def read_until(self, token: str):

        lines = []

        while True:
            line = self.process.stdout.readline().strip()

            if line:
                lines.append(line)

            if token in line:
                break

        return lines

    def initialize(self):

        self.send("uci")
        self.read_until("uciok")

        self.send("setoption name Threads value 1")
        self.send("setoption name Hash value 256")
        self.send("setoption name MultiPV value 1")

        self.send("isready")
        self.read_until("readyok")

    def bestmove(self, fen: str, depth: int = 18):

        with self.lock:

            self.send("ucinewgame")
            self.send(f"position fen {fen}")
            self.send(f"go depth {depth}")

            while True:

                line = self.process.stdout.readline().strip()

                if line.startswith("bestmove"):

                    return {
                        "bestmove": line.split()[1],
                        "depth": depth
                    }
                
    def stop(self):
        self.send("quit")
        self.process.terminate()