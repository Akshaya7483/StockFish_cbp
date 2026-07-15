from fastapi import FastAPI
from models import MultiPVRequest
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

@app.post("/multipv")
def multipv(req: MultiPVRequest):

    return engine.multipv(
        req.fen,
        req.depth,
        req.multipv
    )