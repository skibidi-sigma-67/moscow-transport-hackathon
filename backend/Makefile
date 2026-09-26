.PHONY: run test lint format

run:
	PYTHONPATH=src uv run python -m backend.main

test:
	uv run pytest tests -v

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

make-migrations:
	uv run alembic revision --autogenerate -m "$(m)"

migrate:
	uv run alembic upgrade head
