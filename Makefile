# ============================================================
# IW AI Core — Developer Commands
# ============================================================

.PHONY: install lint lint-js format typecheck quality \
         test-unit test-integration test test-parallel check \
         db-up db-down db-migrate db-revision \
         daemon-start daemon-stop dashboard-start css \
         allure-unit allure-integration allure-all allure-report allure-serve allure-clean \
         e2e-health e2e-logs e2e-stats

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

test-parallel:
	uv run pytest tests/unit tests/integration -v -n auto --dist=loadfile

# --- Allure test reporting ---
allure-unit:
	uv run pytest tests/unit/ -v --alluredir=allure-results

allure-integration:
	uv run pytest tests/integration/ -v --alluredir=allure-results

allure-all:
	uv run pytest tests/ -v --alluredir=allure-results

allure-serve:
	@command -v allure >/dev/null 2>&1 || { \
		echo "ERROR: 'allure' CLI not found on PATH."; \
		echo ""; \
		echo "Install via npm:  npm install -g allure-commandline"; \
		echo "Install via brew: brew install allure"; \
		echo "Or see: https://allurereport.org/docs/install/"; \
		exit 1; \
	}
	allure serve allure-results --host 0.0.0.0 --port 9999

allure-report:
	@command -v allure >/dev/null 2>&1 || { \
		echo "ERROR: 'allure' CLI not found on PATH."; \
		echo ""; \
		echo "Install via npm:  npm install -g allure-commandline"; \
		echo "Install via brew: brew install allure"; \
		echo "Or see: https://allurereport.org/docs/install/"; \
		exit 1; \
	}
	allure generate --clean -o allure-report allure-results
	@echo "Allure HTML report generated at allure-report/index.html"

allure-clean:
	rm -rf allure-results allure-report

COMPOSE_E2E := docker compose -f docker-compose.e2e.yml -p $${COMPOSE_PROJECT_NAME:-iw-ai-core-e2e}

e2e-health:
	@uv run python scripts/e2e_health_check.py

e2e-logs:
	$(COMPOSE_E2E) logs --tail=200 -f

e2e-stats:
	@docker stats --no-stream $$(docker ps --filter "label=com.docker.compose.project=$${COMPOSE_PROJECT_NAME:-iw-ai-core-e2e}" -q) 2>/dev/null || \
	  echo "No running containers for project $${COMPOSE_PROJECT_NAME:-iw-ai-core-e2e}"

# --- CSS (Tailwind build) ---
css:
	npx tailwindcss -c dashboard/tailwind.config.js -i dashboard/static/tailwind.src.css -o dashboard/static/styles.css --minify

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
