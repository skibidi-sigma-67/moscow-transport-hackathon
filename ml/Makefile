.PHONY: run test lint format

run:
	uv run python -m ml.main

test:
	uv run pytest tests -v

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

