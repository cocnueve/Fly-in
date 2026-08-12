.PHONY: install run debug clean lint lint-strict

PYTHON  ?= python3
MAP     ?= maps/easy/01_linear_path.txt
ARGS    ?=

install:
	$(PYTHON) -m pip install -r requirements.txt --break-system-packages

run:
	$(PYTHON) fly-in.py $(MAP) $(ARGS)

debug:
	$(PYTHON) -m pdb fly-in.py $(MAP) $(ARGS)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache

lint:
	python3 -m flake8 .
	python3 -m mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports \
	--disallow-untyped-defs --check-untyped-defs

lint-strict:
	python3 -m flake8 .
	python3 -m mypy . --strict
