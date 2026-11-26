.PHONY: install test lint typecheck graph

install:
	uv sync --locked

test:
	uv run --locked pytest tests/ -v

lint:
	uv run --locked ruff check src/ tests/

typecheck:
	uv run --locked mypy src/

graph:
	uv run --locked python scripts/export_graph.py
