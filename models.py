from pydantic import BaseModel, model_validator


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
    fen: str | None = None
    current_fen: str | None = None
    previous_fen: str | None = None

    depth: int | None = None
    movetime: int | None = None
    multipv: int = 1

    @model_validator(mode="after")
    def normalize_fens(self):
        """
        Backward compatibility.

        If only 'fen' is provided:
            current_fen = fen

        If current_fen is provided:
            keep it.

        previous_fen is optional.
        """

        if self.current_fen is None:
            self.current_fen = self.fen

        return self