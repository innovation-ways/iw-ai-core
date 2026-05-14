# ============================================================
# IW AI Core — Developer Commands
# ============================================================

.PHONY: install lint lint-fix lint-js lint-templates format format-check typecheck type-check quality \
          test-unit test-integration test-dashboard test-browser test test-parallel smoke check \
          test-assertions diff-coverage \
          db-up db-down db-migrate db-revision \
          daemon-start daemon-stop dashboard-start css \
          allure-unit allure-integration allure-all allure-report allure-serve allure-clean \
          e2e-health e2e-logs e2e-stats \
          security-deps security-iac security-image-dashboard security-secrets security-all security-report security-sast \
          arch-check test-frontend dead-code dep-check

# --- Setup ---
install:
	uv sync
	uv run alembic upgrade head

# --- Quality ---
lint: lint-js lint-templates
	uv run ruff check .

# Auto-fix all ruff-fixable lint and format violations (safe to run in worktrees).
# Use this as a recovery step when `make lint` or `make format-check` fails with
# auto-fixable errors (e.g. Alembic merge-migration boilerplate, import ordering).
lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

# Syntax-check every hand-written dashboard JS file (excludes vendor/).
# Fails fast on unclosed braces / stray tokens that would otherwise only
# surface at browser_verification time (e.g. see F-00055 post-mortem).
lint-js:
	@command -v node >/dev/null 2>&1 || { echo "ERROR: 'node' is required for lint-js (dashboard JS syntax check)"; exit 1; }
	@find dashboard/static -name '*.js' -not -path '*/vendor/*' -print0 | xargs -0 -r -n1 node --check

# Static lint for Jinja2 templates — currently rejects str.format-style {}
# placeholders passed to the %-style `format` filter (these only blow up at
# render time, and only when real data exercises the branch — see I-00075).
lint-templates:
	uv run python scripts/check_templates.py

format:
	uv run ruff format --check .

# Aliases — skill templates (iw-new-feature/incident/cr) emit `make format-check`
# and `make type-check` in QV gate manifests; keep them working alongside the
# original target names.
format-check: format

typecheck:
	uv run mypy orch/ dashboard/

type-check: typecheck

# AST assertion-scanner gate (CR-00046, P1-CR-A) — flag tests that can't fail
# (no-assert / tautology / mock-only / pytest.raises(Exception) without match=).
# See scripts/check_test_assertions.py and tests/assertion_free_baseline.txt.
# Run with --strict (no baseline) only when intentionally auditing the cleanup
# backlog — `make quality` always runs in baseline mode.
test-assertions:
	uv run python scripts/check_test_assertions.py --baseline tests/assertion_free_baseline.txt tests/

# warn-only for now (Phase-1 P1-CR-C); flips to a hard gate in a follow-up after noise is triaged.
# Exclude skills/ — those are IW skill master copies (not project code) and have their own dep chains.
dead-code:
	uv run vulture || true

dep-check:
	uv run deptry . \
		--per-rule-ignores DEP001=sqlalchemy.ext.mypy.plugin,DEP001=pytest,DEP001=_pytest,DEP001=testcontainers,DEP002=factory-boy,DEP002=freezegun,DEP002=ruff,DEP002=mypy,DEP002=pre-commit,DEP002=types-freezegun,DEP003=yaml,DEP003=pydantic \
		--extend-exclude "skills/.*" || true

quality: lint format typecheck test-assertions dead-code dep-check

# --- Tests ---
test-unit:
	uv run pytest tests/unit/ -v

# Integration gate — testcontainer-backed tests.
# Includes tests/dashboard/ (FastAPI TestClient + db_session fixture) but
# excludes tests/dashboard/browser/ since those need playwright-cli + a
# live Uvicorn server, which the qv-gate environment doesn't provide.
# Browser-level coverage runs separately via the qv-browser step.
test-integration:
	uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -v

# Dashboard-only target for fast local iteration on routers/templates.
# --no-cov: this slice naturally falls below the global coverage threshold;
# the full gate (`test-integration` / `check`) is what enforces it.
test-dashboard:
	uv run pytest tests/dashboard/ --ignore=tests/dashboard/browser --no-cov -v

test-frontend: test-dashboard

# Browser smoke tests — require playwright-cli and spin up a local Uvicorn.
# Not run by `make test`; invoke explicitly when validating browser flows.
test-browser:
	uv run pytest tests/dashboard/browser/ --no-cov -v

test: test-unit test-integration

test-parallel:
	uv run pytest tests/unit tests/integration tests/dashboard --ignore=tests/dashboard/browser -v -n auto --dist=loadfile

smoke:
	uv run pytest -m smoke --strict-markers --no-cov -v

# Diff-coverage gate (CR-00047, P1-CR-B) — new/changed Python lines must be
# >=90% covered, compared against origin/main.
#
# This target is deliberately SELF-CONTAINED: it builds its OWN combined
# unit + integration + dashboard coverage rather than reusing the
# tests/output/coverage/coverage.xml that a preceding step left behind
# (each `pytest --cov` run overwrites it, so the leftover artefact is the
# integration+dashboard slice only) or relying on the `integration-tests`
# QV gate (currently a no-op `make allure-integration` stub — P1-CR-E).
# Run the unit suite first (fresh coverage data), then the integration +
# dashboard suite with --cov-append into the same .coverage file, then
# emit a combined XML and feed it to diff-cover.
#
# `--cov-fail-under=0` on the two pytest runs suppresses the per-run
# `[tool.coverage.report] fail_under` check (the unit-only slice, taken
# alone, sits below the raised floor) — diff-cover's own `--fail-under`
# is this gate's verdict, independent of the global coverage floor.
#
# This is a SLOW gate: it re-runs the unit + integration + dashboard
# suites plus diff-cover. That's the cost of being robust to the
# overwritten-artefact and no-op-integration-gate gotchas. The daemon QV
# step that runs it gets a generous (1800s) timeout for that reason.
diff-coverage:
	uv run pytest tests/unit/ --cov-fail-under=0 -q
	uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser --cov-append --cov-fail-under=0 -q
	uv run coverage xml -o tests/output/coverage/coverage-combined.xml
	uv run diff-cover tests/output/coverage/coverage-combined.xml --compare-branch=origin/main --fail-under=90

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

# Round-trip migration validation: spin a fresh testcontainer Postgres, run
# `alembic upgrade head` from base, compare the resulting schema to
# `Base.metadata.create_all()`, then `downgrade base` and `upgrade head`
# again. Catches missing/broken migrations and model↔migration drift.
# Faster than the full integration suite — use as a dedicated qv-gate
# right after Database steps to short-circuit bad migrations before
# downstream agents inherit them.
migration-check:
	uv run pytest tests/integration/test_migrations_round_trip.py -v --no-cov

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
	@uv run pip-audit -l --strict || true
	@echo "[security-deps] bandit ..."
	@uv run bandit -r orch dashboard executor -c pyproject.toml -f json -o $(SECURITY_DIR)/bandit.json -ll || true
	@uv run bandit -r orch dashboard executor -c pyproject.toml -ll || true
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

security-all: security-deps security-iac security-secrets
	@echo "[security-all] complete (image scans run separately if images are built)"

security-secrets:
	@command -v gitleaks >/dev/null 2>&1 || { \
		echo "ERROR: 'gitleaks' not found."; \
		echo "Install: brew install gitleaks   (or)   curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz | tar -xz -C /tmp && sudo mv /tmp/gitleaks /usr/local/bin/"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-secrets] gitleaks ..."
	@gitleaks detect --no-git --config .gitleaks.toml --report-format json --report-path $(SECURITY_DIR)/gitleaks.json
	@echo "[security-secrets] OK"

# security-sast: SAST gate via Semgrep. Four rules are project-wide-excluded
# because their false-positive density is 100% in this codebase:
#   generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var
#     — fires at every {{ write_button_attrs(request) }} macro callsite (26 sites
#       in 12 files). The macro emits a constant pre-quoted attribute string with
#       no user input. In-macro {# nosemgrep #} does NOT silence the rule (verified
#       empirically); per-line annotation across 12 caller files would be churny
#       and re-fired by every new caller. The macro's constant-output invariant is
#       locked by tests/unit/test_db_guard_macro.py — if a future edit introduces
#       user-input interpolation, that test will fail and this exclude flag must
#       be re-justified.
#   generic.html-templates.security.var-in-href.var-in-href
#     — fires on every <a href="{{ ... }}">; in this codebase, every flagged value
#       is a route-supplied URL, hardcoded route path, or template-author macro
#       parameter. The rule cannot prove safety statically. Per-line annotation
#       across 31 sites in 29 files would be unsustainable.
#   generic.html-templates.security.var-in-script-tag.var-in-script-tag
#     — fires on {{ ... }} inside <script>; in this codebase, every flagged value
#       passes through Jinja's tojson filter which emits a valid JSON literal.
#   html.security.plaintext-http-link.plaintext-http-link
#     — fires on http://-prefixed hrefs; in this codebase the one flagged site is
#       a dev-only localhost link, never reachable in production.
# Triage convention: docs/IW_AI_Core_Testing_Strategy.md "Semgrep finding triage".
security-sast:
	@command -v semgrep >/dev/null 2>&1 || { \
		echo "ERROR: 'semgrep' not found."; \
		echo "Install: uv add --dev semgrep   (or)   pip install semgrep"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-sast] semgrep ..."
	@uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit \
		--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var \
		--exclude-rule generic.html-templates.security.var-in-href.var-in-href \
		--exclude-rule generic.html-templates.security.var-in-script-tag.var-in-script-tag \
		--exclude-rule html.security.plaintext-http-link.plaintext-http-link \
		orch dashboard executor --error --json --output $(SECURITY_DIR)/semgrep.json || true
	@uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit \
		--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var \
		--exclude-rule generic.html-templates.security.var-in-href.var-in-href \
		--exclude-rule generic.html-templates.security.var-in-script-tag.var-in-script-tag \
		--exclude-rule html.security.plaintext-http-link.plaintext-http-link \
		orch dashboard executor --error
	@echo "[security-sast] OK"

security-report:
	@uv run python scripts/security_report.py

# --- Architecture ---
arch-check:
	@uv run python scripts/arch_check.py
