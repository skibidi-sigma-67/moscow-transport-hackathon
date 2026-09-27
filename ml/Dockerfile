FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY libs/ libs/
COPY backend/pyproject.toml backend/pyproject.toml
COPY ml/ ml/

RUN uv sync --frozen --no-dev --package ml

WORKDIR /app/ml
EXPOSE 8001

ENV OMP_NUM_THREADS=1 APP__MODEL_DIR=/app/ml/artifacts

CMD ["/app/.venv/bin/python", "-m", "ml.main"]
