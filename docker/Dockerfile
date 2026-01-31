FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (for caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir aiosqlite

COPY src/ src/
COPY tests/ tests/

EXPOSE 8000

# Default: run the FastAPI server
# Override with: docker compose run api python -m src.voice.agent
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
