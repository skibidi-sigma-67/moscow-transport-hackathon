.PHONY: run run-model train-model test lint format

run:
	PYTHONPATH=src uv run python -m backend.main

run-model:
	PYTHONPATH=src uv run python -m backend.ml_service.main

train-model:
	PYTHONPATH=src uv run python -m backend.ml_service.train_delay_model --data-dir "$(DATA_DIR)" --output src/backend/ml_service/data/delay_model.json

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
