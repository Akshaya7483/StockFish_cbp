from fastapi import FastAPI

from engine import StockfishEngine
from models import BestMoveRequest

app = FastAPI()

engine = StockfishEngine()


@app.get("/")
def home():
    return {
        "status": "online",
        "engine": "Stockfish",
        "version": "18.1"
    }


@app.post("/bestmove")
def best_move(req: BestMoveRequest):
    return engine.bestmove(req.fen, req.depth)