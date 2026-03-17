.PHONY: install dev test lint format run seed clean docker-up docker-down

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short -m "not integration"

test-integration:
	pytest tests/ -v --tb=short -m "integration"

test-all:
	pytest tests/ -v --tb=short --cov=depgraph --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

run:
	uvicorn depgraph.api:app --host 0.0.0.0 --port 8000 --reload

seed:
	depgraph seed --packages 80

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker-up:
	docker compose up -d

docker-down:
	docker compose down -v
