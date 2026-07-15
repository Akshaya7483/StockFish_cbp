import os
import subprocess
from fastapi import FastAPI

if os.name == "nt":
    ENGINE_PATH = "./stockfish-windows-x86-64-avx2.exe"
else:
    ENGINE_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2"
    os.chmod(ENGINE_PATH, 0o755)

if not os.path.exists(ENGINE_PATH):
    raise FileNotFoundError(f"Stockfish binary not found: {ENGINE_PATH}")

engine = subprocess.Popen(
    [ENGINE_PATH],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

app = FastAPI()

@app.get("/")
def home():
    return {
        "status": "online",
        "engine": "Stockfish",
        "version": "17.1"
    }
@app.get("/test-stockfish")
def test_stockfish():
    engine.stdin.write("uci\n")
    engine.stdin.flush()

    lines = []

    while True:
        line = engine.stdout.readline().strip()
        lines.append(line)

        if line == "uciok":
            break

    return {"output": lines}