from fastapi import FastAPI

from engine import StockfishEngine
from models import (
    BestMoveRequest,
    MultiPVRequest,
    AnalyzeRequest,
)

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

@app.post("/analyze")
def analyze(req: AnalyzeRequest):

    return engine.analyze(
        fen=req.fen,
        depth=req.depth,
        movetime=req.movetime,
        multipv=req.multipv,
    )