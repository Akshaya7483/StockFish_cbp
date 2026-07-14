FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN apt-get update && apt-get install -y curl xz-utils

RUN curl -L https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar -o stockfish.tar

RUN tar -xf stockfish.tar

RUN chmod +x stockfish/stockfish-ubuntu-x86-64-avx2

EXPOSE 10000

CMD ["python","-m","uvicorn","app:app","--host","0.0.0.0","--port","10000"]