from fastapi import FastAPI, HTTPException
from engine_pool import EnginePool
from validators import validate_request
from game_analyzer import GameAnalyzer
from game_analysis_pipeline import GameAnalysisPipeline
from models import (
    BestMoveRequest,
    MultiPVRequest,
    AnalyzeRequest,
    AnalyzeGameRequest,
)

app = FastAPI()

engine_pool = EnginePool()

game_analysis_pipeline = GameAnalysisPipeline()
game_analyzer = GameAnalyzer(game_analysis_pipeline)

# -------------------------------------
# Engine Call Wrapper
# -------------------------------------

def engine_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)

    except TimeoutError as e:
        raise HTTPException(
        status_code=504,
        detail=str(e)
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


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

    engine = engine_pool.acquire()
    try:
        return engine_call(
            engine.bestmove,
            req.fen,
            req.depth
        )
    finally:
        engine_pool.release(engine)


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

    engine = engine_pool.acquire()
    try:
        return engine_call(
            engine.multipv,
            req.fen,
            req.depth,
            req.multipv
        )
    finally:
        engine_pool.release(engine)


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

    engine = engine_pool.acquire()
    try:
        return engine_call(
            engine.analyze,
            current_fen=req.current_fen,
            previous_fen=req.previous_fen,
            depth=req.depth,
            movetime=req.movetime,
            multipv=req.multipv,
        )
    finally:
        engine_pool.release(engine)

@app.get("/stats")
def stats():
    return engine_pool.stats()

@app.get("/health")
def health():
    return engine_pool.health()

@app.post("/analyze-game")
def analyze_game(req: AnalyzeGameRequest):

    engine = engine_pool.acquire()
    try:
        return engine_call(
            game_analyzer.analyze_game,
            engine,
            req.pgn,
            depth=req.depth,
            movetime=req.movetime,
            multipv=req.multipv,
        )
    finally:
        engine_pool.release(engine)


# -------------------------------------
# Shutdown
# -------------------------------------

@app.on_event("shutdown")
def shutdown_event():
    engine_pool.shutdown()