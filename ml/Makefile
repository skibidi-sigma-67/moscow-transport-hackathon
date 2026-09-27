.PHONY: run test lint format

run:
	uv run --frozen python -m ml.main

test:
	uv run --frozen pytest tests -q

lint:
	uvx ruff check .

format:
	uvx ruff check --fix .
	uvx ruff format .
