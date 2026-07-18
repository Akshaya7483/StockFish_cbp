import os

# ============================
# Engine Binary
# ============================

if os.name == "nt":
    ENGINE_PATH = "./stockfish-windows-x86-64-avx2.exe"
else:
    ENGINE_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2"

# ============================
# Engine Options
# ============================

THREADS = int(os.getenv("SF_THREADS", "1"))

HASH_MB = int(os.getenv("SF_HASH_MB", "256"))

DEFAULT_MULTIPV = int(os.getenv("SF_MULTIPV", "1"))

# ============================
# Search Defaults
# ============================

DEFAULT_DEPTH = 18

FIRST_MOVE_DEPTH = 10

FIRST_MOVE_TIME = 200

# ============================
# Cache
# ============================

CACHE_SIZE = int(os.getenv("SF_CACHE_SIZE", "500"))

# ============================
# Engine Pool
# ============================

POOL_SIZE = int(os.getenv("SF_POOL_SIZE", "2"))

# ============================
# Candidate Detection
# ============================

CANDIDATE_CP_THRESHOLD = int(os.getenv("SF_CANDIDATE_CP_THRESHOLD", "100"))

MATE_PRIORITY = int(os.getenv("SF_MATE_PRIORITY", "3"))

PV_CHANGE_PRIORITY = int(os.getenv("SF_PV_CHANGE_PRIORITY", "2"))

# ============================
# Candidate Enrichment
# ============================

CANDIDATE_MULTIPV = int(os.getenv("SF_CANDIDATE_MULTIPV", "5"))

CANDIDATE_DEPTH = int(os.getenv("SF_CANDIDATE_DEPTH", "18"))

_candidate_movetime = os.getenv("SF_CANDIDATE_MOVETIME", "")
CANDIDATE_MOVETIME = int(_candidate_movetime) if _candidate_movetime else None

# ============================
# Review Classification
# ============================
# Centipawn-loss upper bounds (mover perspective) per category.

BEST_MOVE_CP = int(os.getenv("SF_BEST_MOVE_CP", "0"))

EXCELLENT_CP = int(os.getenv("SF_EXCELLENT_CP", "20"))

GOOD_CP = int(os.getenv("SF_GOOD_CP", "50"))

INACCURACY_CP = int(os.getenv("SF_INACCURACY_CP", "100"))

MISTAKE_CP = int(os.getenv("SF_MISTAKE_CP", "300"))

BLUNDER_CP = int(os.getenv("SF_BLUNDER_CP", "300"))

MATE_BLUNDER_PRIORITY = int(os.getenv("SF_MATE_BLUNDER_PRIORITY", "100"))

# ============================
# Brilliancy Detection
# ============================
# Category score thresholds (0..100).

BRILLIANT_SCORE = int(os.getenv("SF_BRILLIANT_SCORE", "70"))

GREAT_MOVE_SCORE = int(os.getenv("SF_GREAT_MOVE_SCORE", "45"))

# Signal thresholds
ONLY_MOVE_CP_GAP = int(os.getenv("SF_ONLY_MOVE_CP_GAP", "150"))

SACRIFICE_MIN_VALUE = int(os.getenv("SF_SACRIFICE_MIN_VALUE", "2"))

SACRIFICE_PV_PLIES = int(os.getenv("SF_SACRIFICE_PV_PLIES", "6"))

PV_STABILITY_DEPTH = int(os.getenv("SF_PV_STABILITY_DEPTH", "18"))

LARGE_EVAL_GAIN_CP = int(os.getenv("SF_LARGE_EVAL_GAIN_CP", "150"))

CONFIDENCE_THRESHOLD = float(os.getenv("SF_CONFIDENCE_THRESHOLD", "0.6"))

# Weighted signal scores (should sum to ~100).
ONLY_MOVE_WEIGHT = int(os.getenv("SF_ONLY_MOVE_WEIGHT", "30"))

SACRIFICE_WEIGHT = int(os.getenv("SF_SACRIFICE_WEIGHT", "20"))

EVAL_GAIN_WEIGHT = int(os.getenv("SF_EVAL_GAIN_WEIGHT", "15"))

MATE_WEIGHT = int(os.getenv("SF_MATE_WEIGHT", "20"))

PV_STABILITY_WEIGHT = int(os.getenv("SF_PV_STABILITY_WEIGHT", "10"))

DEPTH_CONFIDENCE_WEIGHT = int(os.getenv("SF_DEPTH_CONFIDENCE_WEIGHT", "5"))

# ============================
# Accuracy Engine
# ============================
# Decay constant for the default exponential accuracy curve
# (score = 100 * exp(-cpl / ACCURACY_DECAY)). Larger = gentler, keeping small
# inaccuracies closer to 100%. The curve itself is swappable in code.

ACCURACY_DECAY = float(os.getenv("SF_ACCURACY_DECAY", "300"))

# ============================
# Critical Position Detection
# ============================
# Mover-perspective centipawn swing (loss) considered a large swing when no
# richer review classification is decisive.

CRITICAL_SWING_CP = int(os.getenv("SF_CRITICAL_SWING_CP", "200"))

# Mover-perspective evaluation (before the move) treated as a winning
# advantage, used to refine blunder reasons.

WINNING_ADVANTAGE_CP = int(os.getenv("SF_WINNING_ADVANTAGE_CP", "200"))

# ============================
# Timeouts
# ============================

ENGINE_TIMEOUT = int(
    os.getenv("SF_TIMEOUT", "30")
)