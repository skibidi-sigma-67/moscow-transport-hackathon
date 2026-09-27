FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY libs/commons/pyproject.toml libs/commons/pyproject.toml
COPY libs/commons/src/ libs/commons/src/
COPY backend/pyproject.toml backend/pyproject.toml
COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/src/ ml/src/

ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 UV_COMPILE_BYTECODE=1 APP__MODEL_DIR=/app/ml/artifacts

RUN uv sync --locked --no-dev --package ml

COPY ml/artifacts/delay.cbm ml/artifacts/metadata.json ml/artifacts/

WORKDIR /app/ml
EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=2s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=1).read()"

CMD ["/app/.venv/bin/python", "-m", "ml.main"]
