.PHONY: dev seed test lint

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

seed:
	python -m app.seed

test:
	pytest -q --cov=app --cov-report=term-missing

lint:
	ruff check backend && black --check backend
