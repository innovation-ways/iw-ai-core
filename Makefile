# ============================================================
# IW AI Core — Developer Commands
# ============================================================

.PHONY: install lint format typecheck quality \
        test-unit test-integration test check \
        db-up db-down db-migrate db-revision \
        daemon-start daemon-stop dashboard-start

# --- Setup ---
install:
	uv sync
	uv run alembic upgrade head

# --- Quality ---
lint:
	uv run ruff check .

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

# --- All checks (run before commit) ---
check: quality test

# --- Database ---
db-up:
	docker compose up -d db

db-down:
	docker compose down

db-migrate:
	uv run alembic upgrade head

db-revision:
	uv run alembic revision --autogenerate -m "$(MSG)"

# --- Services ---
daemon-start:
	uv run python -m orch.daemon.main &

daemon-stop:
	uv run iw daemon stop

dashboard-start:
	uv run uvicorn dashboard.app:create_app --factory --host 0.0.0.0 --port 9900 --reload
