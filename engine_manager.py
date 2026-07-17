import os
import subprocess
import time
from uci_protocol import UCIProtocol
from config import (
    ENGINE_PATH,
    THREADS,
    HASH_MB,
    DEFAULT_MULTIPV,
)


class EngineManager:
    def __init__(self, on_restart=None):
        self.on_restart = on_restart

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

        self.start_time = time.time()

        self.initialize()

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

        self.initialize()

        if self.on_restart is not None:
            self.on_restart()

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
            "uptime_seconds": int(time.time() - self.start_time),
        }

    # -------------------------
    # Shutdown
    # -------------------------

    def stop(self):
        self.protocol.send("quit")
        self.process.terminate()
