from enum import Enum


class GamePhase(str, Enum):
    UNKNOWN = "unknown"
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"
