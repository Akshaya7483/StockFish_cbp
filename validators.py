import chess


def validate_fen(fen: str):
    try:
        chess.Board(fen)
    except Exception:
        raise ValueError("Invalid FEN.")


def validate_depth(depth: int):

    if depth < 1 or depth > 40:
        raise ValueError("Depth must be between 1 and 40.")


def validate_multipv(multipv: int):

    if multipv < 1 or multipv > 10:
        raise ValueError("MultiPV must be between 1 and 10.")


def validate_movetime(movetime):

    if movetime is None:
        return

    if movetime < 10 or movetime > 60000:
        raise ValueError("Move time must be between 10 ms and 60000 ms.")


def validate_request(
    fen,
    depth=None,
    multipv=None,
    movetime=None,
):

    validate_fen(fen)

    if depth is not None:
        validate_depth(depth)

    if multipv is not None:
        validate_multipv(multipv)

    if movetime is not None:
        validate_movetime(movetime)