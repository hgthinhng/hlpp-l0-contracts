.PHONY: all test lint typecheck

all: test lint typecheck

test:
	.venv/bin/python -m pytest -v --cov=src/ht_l1_core --cov-report=term

lint:
	.venv/bin/python -m ruff check src/ tests/

typecheck:
	.venv/bin/python -m mypy --strict src/
