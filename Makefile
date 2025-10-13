# ---------- Config ----------
NAME       = habit                      # wrapper script name (./habit)
PYTHON     = python3
SRC_DIR    = src
MODULE     = habit                      # expects src/habit/__main__.py
DATA_DIR   = data

# Tools (override from CLI if needed: e.g., `make LINT="ruff check"`)
BLACK      = $(PYTHON) -m black
RUFF       = $(PYTHON) -m ruff
MYPY       = $(PYTHON) -m mypy
PYTEST     = $(PYTHON) -m pytest

# ---------- Default ----------
all: $(NAME)

# Create a tiny CLI wrapper so you can run ./habit
$(NAME):
	@printf '%s\n' '#!/usr/bin/env sh'                                    >  $(NAME)
	@printf '%s\n' 'PYTHONPATH="$(SRC_DIR)" exec $(PYTHON) -m $(MODULE) "$$@"' >> $(NAME)
	@chmod +x $(NAME)
	@mkdir -p $(DATA_DIR)

# ---------- Developer helpers ----------
# Format code with Black
frmt:
	@$(BLACK) .

# Lint with Ruff (no fixes)
lint:
	@$(RUFF) check .

# Lint with Ruff and apply autofixes
lint-fix:
	@$(RUFF) check . --fix

# Static type-check with mypy
type:
	@$(MYPY) .

# Run unit tests (pytest discovers tests/ via pyproject.toml)
test:
	@$(PYTEST) || ( ec=$$?; if [ $$ec -eq 5 ]; then printf 'No tests collected — skipping\n'; exit 0; else exit $$ec; fi )

# Everything: format, lint, type-check, and test (quick CI-like)
check: frmt lint type test

# Quick manual run (optional)
run: $(NAME)
	@./$(NAME) list --days 14 || true

# ---------- Cleanup ----------
clean:
	@find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage build dist 2>/dev/null || true

fclean: clean
	@rm -f $(NAME)

re: fclean all

.PHONY: all clean fclean re frmt lint lint-fix type test check run
