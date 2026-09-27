FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
COPY libs/commons/pyproject.toml libs/commons/
COPY backend/pyproject.toml backend/
COPY ml/pyproject.toml ml/

RUN uv sync --frozen --no-dev --package backend --no-install-project

COPY libs/commons/src/ libs/commons/src/
COPY backend/src/ backend/src/
COPY backend/alembic.ini backend/
COPY backend/alembic/ backend/alembic/

RUN uv sync --frozen --no-dev --package backend

ARG APP_USER_ID=10001
RUN useradd -u ${APP_USER_ID} -m appuser
USER ${APP_USER_ID}

WORKDIR /app/backend
EXPOSE 8000
EXPOSE 9201

HEALTHCHECK --interval=10s --timeout=2s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=1)"

CMD ["python", "-m", "backend.main"]
