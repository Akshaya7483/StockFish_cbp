from pydantic import BaseModel
from pydantic import BaseModel, Field, model_validator

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

    depth: int | None = Field(default=None, ge=1, le=30)

    movetime: int | None = Field(default=None, ge=10, le=60000)

    multipv: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def validate_search_mode(self):

        if self.depth is None and self.movetime is None:
            raise ValueError(
                "Either depth or movetime must be provided."
            )

        if self.depth is not None and self.movetime is not None:
            raise ValueError(
                "Provide either depth OR movetime, not both."
            )

        return self