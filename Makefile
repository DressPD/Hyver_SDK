.PHONY: generate lint format typecheck test coverage build check clean all install

# ── Setup ──────────────────────────────────────────────────────────────
install:
	uv sync --all-extras

# ── Code Generation ───────────────────────────────────────────────────
generate:
	uv run stainful generate --spec openapi.yaml --config stainless.yml --out src
	uv run python scripts/post_generate.py
	uv run python scripts/post_generate.py

# ── Quality ───────────────────────────────────────────────────────────
lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	uv run mypy src/

# ── Testing ───────────────────────────────────────────────────────────
test:
	uv run python -m pytest tests/ -v

coverage:
	uv run python -m pytest tests/ -v --cov=hermes --cov-report=term-missing --cov-report=html

# ── Build ─────────────────────────────────────────────────────────────
build:
	uv build

# ── Docs ──────────────────────────────────────────────────────────────
docs:
	uv run stainful docs --spec openapi.yaml --config stainless.yml --out api.md

# ── Maintenance ───────────────────────────────────────────────────────
clean:
	rm -rf src/hermes/ dist/ .mypy_cache/ .pytest_cache/ .ruff_cache/ htmlcov/

# ── Full Pipeline ─────────────────────────────────────────────────────
check: lint typecheck test

all: generate check
