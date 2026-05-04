SHELL := /bin/bash

fix:
	@echo "Fix Project"
	@echo "Usage: make fix"
	set -a && source .env && set +a && source venv/bin/activate && python -m ruff check . --fix
	set -a && source .env && set +a && source venv/bin/activate && python -m ruff format .

lint:
	@echo "Running linters"
	set -a && source .env && set +a && source venv/bin/activate && python -m ruff check .
	set -a && source .env && set +a && source venv/bin/activate && python -m ruff format . --check

test:
	@echo "Running tests with coverage"
	set -a && source .env && set +a && source venv/bin/activate && python -m pytest tests/ -v --cov=src/grotesk --cov-report=term-missing --cov-report=term

.PHONY: fix lint test
