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
# Timeouts
# ============================

ENGINE_TIMEOUT = int(
    os.getenv("SF_TIMEOUT", "30")
)