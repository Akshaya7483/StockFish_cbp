from pydantic import BaseModel


class BestMoveRequest(BaseModel):
    fen: str
    depth: int = 18


class EvaluateRequest(BaseModel):
    fen: str
    depth: int = 18

class MultiPVRequest(BaseModel):
    fen: str
    depth: int = 18
    multipv: int = 3

class AnalyzeRequest(BaseModel):
    fen: str
    depth: int | None = None
    movetime: int | None = None
    multipv: int = 1