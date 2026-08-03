PYTHON ?= $(shell command -v python3.12 2>/dev/null || command -v python3.11 2>/dev/null || command -v python3.10 2>/dev/null || command -v python3)
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
PIPELINE := $(VENV)/bin/ice-news-pipeline

.PHONY: setup test lint typecheck check sample reproduce clean help

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

test:
	$(VENV_PYTHON) -m pytest --cov=ice_news_pipeline --cov-report=term-missing

lint:
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m ruff format --check .

typecheck:
	$(VENV_PYTHON) -m mypy

check: lint typecheck test

sample:
	$(PIPELINE) run --limit 50 --output-dir outputs/sample --report-dir reports/sample

reproduce:
	$(PIPELINE) run --workers 4 --output-dir outputs/full --report-dir reports/generated

clean:
	$(VENV_PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in (pathlib.Path('outputs'), pathlib.Path('reports'), pathlib.Path('.pytest_cache'), pathlib.Path('.mypy_cache'), pathlib.Path('.ruff_cache'), *pathlib.Path('.').glob('*.egg-info'))]"
