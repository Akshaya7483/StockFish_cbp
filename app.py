import os
import subprocess
from fastapi import FastAPI

ENGINE_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2"
if os.name == "nt":
    ENGINE_PATH = "./stockfish-windows-x86-64-avx2.exe"
else:
    ENGINE_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2"    
    os.chmod(ENGINE_PATH, 0o755)

engine = subprocess.Popen(
    [ENGINE_PATH],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

app = FastAPI()