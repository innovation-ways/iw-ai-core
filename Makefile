# ============================================================
# IW AI Core — Developer Commands
# ============================================================

.PHONY: install lint lint-js format typecheck quality \
        test-unit test-integration test check \
        db-up db-down db-migrate db-revision \
        daemon-start daemon-stop dashboard-start

# --- Setup ---
install:
	uv sync
	uv run alembic upgrade head

# --- Quality ---
lint: lint-js
	uv run ruff check .

# Syntax-check every hand-written dashboard JS file (excludes vendor/).
# Fails fast on unclosed braces / stray tokens that would otherwise only
# surface at browser_verification time (e.g. see F-00055 post-mortem).
lint-js:
	@command -v node >/dev/null 2>&1 || { echo "ERROR: 'node' is required for lint-js (dashboard JS syntax check)"; exit 1; }
	@find dashboard/static -name '*.js' -not -path '*/vendor/*' -print0 | xargs -0 -r -n1 node --check

format:
	uv run ruff format --check .

typecheck:
	uv run mypy orch/ dashboard/

quality: lint format typecheck

# --- Tests ---
test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

test: test-unit test-integration

# --- Allure test reporting ---
allure-unit:
	uv run pytest tests/unit/ -v --alluredir=allure-results

allure-integration:
	uv run pytest tests/integration/ -v --alluredir=allure-results

allure-all:
	uv run pytest tests/ -v --alluredir=allure-results

allure-serve:
	npx allure serve allure-results --host 0.0.0.0 --port 9999

allure-clean:
	rm -rf allure-results allure-report

# --- All checks (run before commit) ---
check: quality test

# --- Database ---
COMPOSE_BOOTSTRAP := docker compose -f docker-compose.bootstrap.yml

db-up:
	COMPOSE_PROJECT_NAME=iw-ai-core $(COMPOSE_BOOTSTRAP) up -d db

db-down:
	COMPOSE_PROJECT_NAME=iw-ai-core $(COMPOSE_BOOTSTRAP) down

db-migrate:
	uv run alembic upgrade head

db-revision:
	uv run alembic revision --autogenerate -m "$(MSG)"

# --- Services ---
daemon-start:
	uv run python -m orch.daemon &

daemon-stop:
	uv run iw daemon stop

dashboard-start:
	uv run uvicorn dashboard.app:create_app --factory --host 0.0.0.0 --port 9900 --reload
