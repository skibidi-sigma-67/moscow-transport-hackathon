FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    OMP_NUM_THREADS=1 \
    APP__STRATEGY=schedule_ensemble

COPY pyproject.toml uv.lock ./
COPY libs/commons/pyproject.toml libs/commons/
COPY backend/pyproject.toml backend/
COPY ml/pyproject.toml ml/

RUN uv sync --frozen --no-dev --package ml --no-install-project

COPY libs/commons/src/ libs/commons/src/
COPY ml/src/ ml/src/
COPY ml/artifacts/ ml/artifacts/

ARG APP_USER_ID=10001
ARG APP_PORT=8001

RUN uv sync --frozen --no-dev --package ml && mkdir -p ml/artifacts && chown -R ${APP_USER_ID}:${APP_USER_ID} ml/artifacts

WORKDIR /app/ml
USER ${APP_USER_ID}:${APP_USER_ID}
EXPOSE ${APP_PORT}

HEALTHCHECK --interval=10s --timeout=2s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=1)"

CMD ["python", "-m", "ml.main"]
