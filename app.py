import os
import subprocess
from fastapi import FastAPI
from pydantic import BaseModel

class BestMoveRequest(BaseModel):
    fen: str
    depth: int = 18
    
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

@app.post("/bestmove")
def bestmove(req: BestMoveRequest):

    engine.stdin.write("ucinewgame\n")
    engine.stdin.write(f"position fen {req.fen}\n")
    engine.stdin.write(f"go depth {req.depth}\n")
    engine.stdin.flush()

    while True:
        line = engine.stdout.readline().strip()

        if line.startswith("bestmove"):
            return {
                "fen": req.fen,
                "depth": req.depth,
                "bestmove": line.split()[1]
            }