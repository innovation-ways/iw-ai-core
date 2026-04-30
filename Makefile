# ============================================================
# IW AI Core — Developer Commands
# ============================================================

.PHONY: install lint lint-js format typecheck quality \
         test-unit test-integration test test-parallel smoke check \
         db-up db-down db-migrate db-revision \
         daemon-start daemon-stop dashboard-start css \
         allure-unit allure-integration allure-all allure-report allure-serve allure-clean \
         e2e-health e2e-logs e2e-stats \
         security-deps security-iac security-image-dashboard security-all security-report

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

smoke:
	uv run pytest -m smoke --strict-markers -v

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

# --- Security ---
SECURITY_DIR := tests/output/security

security-deps:
	@command -v pip-audit >/dev/null 2>&1 || { \
		echo "ERROR: 'pip-audit' not found."; \
		echo "Install: uv add --dev pip-audit"; \
		exit 1; \
	}
	@command -v bandit >/dev/null 2>&1 || { \
		echo "ERROR: 'bandit' not found."; \
		echo "Install: uv add --dev bandit[toml]"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-deps] pip-audit ..."
	@uv run pip-audit -l --format=json --output=$(SECURITY_DIR)/pip-audit.json || true
	@uv run pip-audit -l --strict
	@echo "[security-deps] bandit ..."
	@uv run bandit -r orch dashboard executor -c pyproject.toml -f json -o $(SECURITY_DIR)/bandit.json -ll || true
	@uv run bandit -r orch dashboard executor -c pyproject.toml -ll
	@echo "[security-deps] OK"

security-iac:
	@command -v trivy >/dev/null 2>&1 || { \
		echo "ERROR: 'trivy' not found."; \
		echo "Install: brew install trivy   (or)   curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-iac] trivy config ..."
	@trivy config --severity HIGH,CRITICAL --format json --output $(SECURITY_DIR)/trivy-iac.json --exit-code 1 .

security-image-dashboard:
	@echo "no built image — N/A for this project"

security-all: security-deps security-iac
	@echo "[security-all] complete (image scans run separately if images are built)"

security-report:
	@uv run python scripts/security_report.py
