import math


def win_probability(cp: int | None = None, mate: int | None = None):
    """
    Convert Stockfish evaluation to win probability.
    Returns percentages for White and Black.
    """

    if mate is not None:
        if mate > 0:
            return {
                "white": 100.0,
                "black": 0.0
            }
        else:
            return {
                "white": 0.0,
                "black": 100.0
            }

    if cp is None:
        return {
            "white": 50.0,
            "black": 50.0
        }

    white = 50 + 50 * (
        2 / (1 + math.exp(-0.00368208 * cp)) - 1
    )

    white = round(white, 2)

    return {
        "white": white,
        "black": round(100 - white, 2)
    }