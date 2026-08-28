# ApiForge Makefile
#
# Common development and release tasks.
#
# Usage:
#   make help        # show all targets
#   make install     # install in dev mode
#   make test        # run tests
#   make lint        # lint + type check
#   make build       # build sdist + wheel
#   make publish     # build + publish to PyPI
#   make publish-test  # publish to TestPyPI
#   make clean       # remove build artifacts

PY ?= python
PIP ?= pip
PACKAGE := apiforge

.DEFAULT_GOAL := help

.PHONY: help install test lint format build clean publish publish-test check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install in editable dev mode
	$(PIP) install -e ".[dev]"

test: ## Run the test suite
	$(PY) -m pytest tests/ -v

lint: ## Run linter + type checker
	$(PY) -m ruff check src/ tests/
	$(PY) -m mypy src/

format: ## Auto-format with ruff
	$(PY) -m ruff check --fix src/ tests/
	$(PY) -m ruff format src/ tests/

check: lint test ## Run lint + tests (CI gate)

build: clean ## Build sdist and wheel distributions
	$(PIP) install build
	$(PY) -m build

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

publish: build ## Publish to PyPI (requires TWINE_USERNAME/TWINE_PASSWORD)
	$(PIP) install twine
	$(PY) -m twine upload dist/*

publish-test: build ## Publish to TestPyPI
	$(PIP) install twine
	$(PY) -m twine upload --repository testpypi dist/*
