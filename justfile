bootstrap:
	pip install -e '.[dev]'
	pre-commit install

up:
	docker compose up -d

up-obs:
	docker compose --profile observability up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	alembic upgrade head

test:
	PYTHONPATH=. pytest tests/ -v

lint:
	ruff check .

typecheck:
	mypy .

format:
	ruff format .

load-test:
	k6 run --env API_KEY="$$API_KEY" tests/load/k6_script.js

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
