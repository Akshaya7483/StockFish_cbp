from fastapi import FastAPI, HTTPException

from engine import StockfishEngine
from validators import validate_request

from models import (
    BestMoveRequest,
    MultiPVRequest,
    AnalyzeRequest,
)

app = FastAPI()

engine = StockfishEngine()


# -------------------------------------
# Validation Helper
# -------------------------------------

def validate_or_raise(**kwargs):
    try:
        validate_request(**kwargs)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# -------------------------------------
# Home
# -------------------------------------

@app.get("/")
def home():
    return {
        "status": "online",
        "engine": "Stockfish",
        "version": "18.1"
    }


# -------------------------------------
# Best Move
# -------------------------------------

@app.post("/bestmove")
def best_move(req: BestMoveRequest):

    validate_or_raise(
        fen=req.fen,
        depth=req.depth
    )

    return engine.bestmove(
        req.fen,
        req.depth
    )


# -------------------------------------
# MultiPV
# -------------------------------------

@app.post("/multipv")
def multipv(req: MultiPVRequest):

    validate_or_raise(
        fen=req.fen,
        depth=req.depth,
        multipv=req.multipv
    )

    return engine.multipv(
        req.fen,
        req.depth,
        req.multipv
    )


# -------------------------------------
# Analyze
# -------------------------------------

@app.post("/analyze")
def analyze(req: AnalyzeRequest):

    validate_or_raise(
        fen=req.fen,
        depth=req.depth,
        multipv=req.multipv,
        movetime=req.movetime
    )

    return engine.analyze(
        fen=req.fen,
        depth=req.depth,
        movetime=req.movetime,
        multipv=req.multipv,
    )