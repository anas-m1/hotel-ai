.PHONY: install test lint typecheck clean

VENV = .venv
PYTHON = $(VENV)/Scripts/python.exe
PIP = $(VENV)/Scripts/pip.exe
EVAL = ../../phases/04_agentic/eval

$(VENV):
	python -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip

install: $(VENV)
	$(PIP) install -e ".[dev]"

test: install
	$(PYTHON) -m pytest $(EVAL)/test_booking_agent.py -v

lint: install
	$(PYTHON) -m ruff check src/

typecheck: install
	$(PYTHON) -m mypy src/

clean:
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf __pycache__ src/**/__pycache__
