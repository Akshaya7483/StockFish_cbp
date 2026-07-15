FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install only what's needed
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl xz-utils && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Stockfish
RUN curl -L \
    https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar \
    -o stockfish.tar && \
    tar -xf stockfish.tar && \
    chmod +x stockfish/stockfish-ubuntu-x86-64-avx2 && \
    rm stockfish.tar

# Copy application
COPY . .

EXPOSE 10000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]