.PHONY: help setup test lint format clean install dev

help:  ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

setup:  ## Set up development environment
	@./dev-setup.sh

install:  ## Install package in development mode
	pip install -e ".[dev]"

test:  ## Run tests
	pytest -v

test-cov:  ## Run tests with coverage
	pytest -v --cov=appstore_metadata_extractor --cov-report=term-missing --cov-report=html

lint:  ## Run all linting
	black --check src tests
	isort --check-only src tests
	flake8 src tests
	mypy src

format:  ## Format code
	black src tests
	isort src tests

clean:  ## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

build:  ## Build distribution packages
	python -m build

publish-test:  ## Publish to TestPyPI
	python -m twine upload --repository testpypi dist/*

publish:  ## Publish to PyPI
	python -m twine upload dist/*

dev:  ## Run development server (example usage)
	@echo "Starting development environment..."
	@echo "Run: python -m appstore_metadata_extractor.cli"

check:  ## Run all checks (lint + test)
	$(MAKE) lint
	$(MAKE) test
