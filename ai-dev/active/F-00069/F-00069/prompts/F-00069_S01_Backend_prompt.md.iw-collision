# F-00069_S01_Backend_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch alembic. No `alembic upgrade/downgrade/stamp`
calls are required or permitted.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00069 --json` for
  the authoritative step list (CR-00023). The `workflow-manifest.json`
  is a snapshot only.
- `ai-dev/active/F-00069/F-00069_Feature_Design.md` — the design document
- `pyproject.toml` — current pytest + ruff + mypy config
- `Makefile` — current test/quality/allure targets
- `tests/conftest.py` — for the pg_engine fixture scope (session)
- `tests/CLAUDE.md` — strict live-DB-guard rules
- `dashboard/app.py` — for the router registration pattern
- `dashboard/routers/healthz.py` — for the FastAPI router pattern in this codebase

## Output Files

- `ai-dev/active/F-00069/reports/F-00069_S01_Backend_report.md` — step report
- Modified: `pyproject.toml`, `Makefile`, `.gitignore`, `dashboard/app.py`
- New: `dashboard/services/coverage_service.py`, `dashboard/routers/coverage.py`
- Updated: `ai-dev/active/F-00069/F-00069_Feature_Design.md` — append "Baseline Coverage Snapshot" content

## Context

You are implementing the **backend half** of F-00069. The frontend
templates (S02), tests (S05), reviews (S03/S04/S06/S07), QV gates
(S08–S12), and browser verification (S13) are separate steps — do NOT
write template files or test files in this step. Your scope is:

1. Test infrastructure config (pyproject.toml + Makefile + .gitignore).
2. The pure-Python coverage service that powers the dashboard view.
3. The FastAPI router stub (so the URL resolves; the templates come from S02).
4. A baseline coverage measurement and persistence of the chosen floor.

Read `CLAUDE.md` and `tests/CLAUDE.md` before starting.

## Requirements

### 1. Add `pytest-xdist>=3.5.0` to dev dependencies

In `pyproject.toml`, add `pytest-xdist>=3.5.0` to the `[dependency-groups] dev` list (this is the canonical dev list per the existing layout — do NOT duplicate it elsewhere). Run `uv sync` to install.

### 2. Configure pytest for parallelism (opt-in via Make target only)

Do NOT change the existing `[tool.pytest.ini_options] addopts` to default to xdist — that would change `make test-unit` / `make test-integration` semantics. Instead, add a comment block above `addopts` documenting that xdist usage is controlled via the `make test-parallel` target which passes `-n auto --dist=loadfile` on the command line.

### 3. Wire pytest-cov + coverage config

Update `[tool.pytest.ini_options]` to include coverage flags so `make test-unit` and `make test-integration` collect coverage automatically:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib --cov=orch --cov=dashboard --cov=executor --cov-report=term-missing:skip-covered --cov-report=html:tests/output/coverage/htmlcov --cov-report=xml:tests/output/coverage/coverage.xml --cov-report=json:tests/output/coverage/coverage.json"
```

(Adjust formatting to project convention — single-line `addopts` strings are acceptable here despite length.)

Add a new `[tool.coverage.run]` block:

```toml
[tool.coverage.run]
source = ["orch", "dashboard", "executor"]
omit = [
  "orch/db/migrations/versions/*",
  "tests/*",
  "scripts/*",
  "bin/*",
]
branch = true
```

Add `[tool.coverage.report]` with the threshold `fail_under` AFTER you have measured the baseline (see deliverable 5).

### 4. Create `tests/output/` and update `.gitignore`

Verify `tests/output/` is excluded from git. If `.gitignore` does not already cover it, add:

```
# Test artefacts (coverage reports, etc.)
tests/output/
```

Also ensure `htmlcov/` and `.coverage` are gitignored if not already.

### 5. **Baseline coverage measurement (MANDATORY)**

After steps 1–4 are in place:

1. Run the full suite once to gather coverage:
   ```bash
   make test-unit && make test-integration
   ```
   (or `uv run pytest tests/ -v` if you need a single invocation)
2. Read `tests/output/coverage/coverage.json` and extract `totals.percent_covered` (integer or float).
3. Compute `floor_percent = floor(percent_covered) - 5`. If the result is negative, clamp to 0.
4. Add the threshold to `pyproject.toml`:
   ```toml
   [tool.coverage.report]
   fail_under = <floor_percent>
   skip_covered = true
   show_missing = true
   ```
5. Append your numbers to the design doc's "Baseline Coverage Snapshot" section (replace the placeholder text). Include date, baseline, floor, and any modules pulling the average down.
6. Re-run `make test-unit` to confirm the new threshold passes (must exit 0).

### 6. Add `make test-parallel` target

In `Makefile`, add:

```makefile
test-parallel:
	uv run pytest tests/unit tests/integration -v -n auto --dist=loadfile
```

Add `test-parallel` to the `.PHONY` list at the top of the file.

**DO NOT** modify the existing `test-unit`, `test-integration`, or `test` targets. They MUST keep their current serial behavior.

### 7. Add `make allure-report` and harden `make allure-serve`

Add a new target:

```makefile
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
```

Modify the existing `allure-serve` target to use the same install-check guard (replace `npx allure` with a direct `allure` invocation after the guard). Add `allure-report` to `.PHONY`.

### 8. Add `make e2e-health`, `make e2e-logs`, `make e2e-stats`

```makefile
COMPOSE_E2E := docker compose -f docker-compose.e2e.yml -p $${COMPOSE_PROJECT_NAME:-iw-ai-core-e2e}

e2e-health:
	@uv run python scripts/e2e_health_check.py

e2e-logs:
	$(COMPOSE_E2E) logs --tail=200 -f

e2e-stats:
	@docker stats --no-stream $$(docker ps --filter "label=com.docker.compose.project=$${COMPOSE_PROJECT_NAME:-iw-ai-core-e2e}" -q) 2>/dev/null || \
	  echo "No running containers for project $${COMPOSE_PROJECT_NAME:-iw-ai-core-e2e}"
```

Add `e2e-health`, `e2e-logs`, `e2e-stats` to `.PHONY`.

Create the helper script `scripts/e2e_health_check.py` that:
- Parses `docker-compose.e2e.yml` (use `pyyaml`, already a transitive dep — verify; if not, `tomllib` won't help — add `pyyaml` to dev deps).
- For each service, derives the host port from the `ports:` mapping.
- Curls `http://localhost:<port>/healthz` (or `/health` if `/healthz` 404s) with a 5-second timeout.
- Prints `PASS  <service>  HTTP <code>` or `FAIL  <service>  <error>`.
- Exits 0 if all PASS, 1 otherwise.

### 9. Coverage view-model service

Create `dashboard/services/coverage_service.py`. Pure functions; no DB, no FastAPI imports. Public API:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PackageRow:
    name: str            # "orch", "dashboard", "executor"
    line_pct: float
    branch_pct: float | None
    missing_lines: int
    badge: str           # "green" | "amber" | "red"

@dataclass(frozen=True)
class FileRow:
    path: str
    line_pct: float
    branch_pct: float | None
    missing_lines: int
    badge: str

@dataclass(frozen=True)
class CoverageView:
    available: bool                      # False when coverage.json missing/malformed
    error: str | None                    # human-readable parse error if any
    overall_line_pct: float | None
    overall_branch_pct: float | None
    threshold: int                       # from pyproject.toml fail_under, 0 if absent
    gap_pct: float | None                # overall_line_pct - threshold
    mtime_iso: str | None                # ISO 8601 timestamp of coverage.json
    test_count: int | None               # totals.num_statements_covered? whichever is in JSON
    packages: list[PackageRow]
    files_by_package: dict[str, list[FileRow]]

def load_coverage(
    coverage_json_path: Path = Path("tests/output/coverage/coverage.json"),
    pyproject_path: Path = Path("pyproject.toml"),
) -> CoverageView: ...
```

Implementation notes:
- Read `fail_under` from `pyproject.toml` using `tomllib` (stdlib in 3.12+).
- If `coverage_json_path` is missing → return `CoverageView(available=False, error=None, threshold=<from pyproject>, mtime_iso=None, ...)` with empty packages/files.
- If JSON is malformed → return `available=False, error="<exception message>"` and log a warning via the standard `logging` module.
- Color-coding:
  - `green` if `line_pct >= threshold`
  - `amber` if `threshold - 10 <= line_pct < threshold`
  - `red` if `line_pct < threshold - 10`
- Per-package rollup: coverage.json's `files` map has paths like `orch/foo.py`, `dashboard/bar.py`. Group by the first path segment.
- Use `Path.stat().st_mtime` and `datetime.fromtimestamp(..., tz=UTC).isoformat()`.

### 10. FastAPI router (stub — templates come from S02)

Create `dashboard/routers/coverage.py`:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dashboard.services.coverage_service import load_coverage
from dashboard.dependencies import get_templates  # follow existing pattern

router = APIRouter(prefix="/system/coverage", tags=["system"])


@router.get("", response_class=HTMLResponse)
def coverage_page(request: Request, templates: Jinja2Templates = Depends(get_templates)):
    view = load_coverage()
    return templates.TemplateResponse(
        request=request,
        name="pages/system/coverage.html",
        context={"view": view},
    )


@router.get("/files/{package}", response_class=HTMLResponse)
def coverage_files_fragment(
    request: Request,
    package: str,
    templates: Jinja2Templates = Depends(get_templates),
):
    view = load_coverage()
    if package not in view.files_by_package:
        return HTMLResponse(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="fragments/coverage_files.html",
        context={"package": package, "files": view.files_by_package[package]},
    )
```

Adapt to the actual `get_templates` dependency name in `dashboard/dependencies.py` if it differs.

Register the router in `dashboard/app.py`:
- Add `coverage` to the `from dashboard.routers import (...)` block (alphabetically sorted).
- Add `app.include_router(coverage.router)` in the same place other routers are included.

### 11. Templates DO NOT belong here

Do NOT create the page or fragment templates. S02 (frontend) owns those. Until S02 lands, hitting `/system/coverage` will 500 due to missing template — this is expected; integration into a working page happens in S02.

## Project Conventions

Follow `CLAUDE.md`, `tests/CLAUDE.md`, and `dashboard/CLAUDE.md`. Specific rules in scope:

- Type-checked: `mypy orch/ dashboard/` must pass on touched files.
- Coverage thresholds are floors, never ceilings — never reduce.
- No live-DB connections in any new code path. `coverage_service` is filesystem-only.
- Match existing router pattern in `dashboard/routers/healthz.py` (use `APIRouter`, `Depends(get_db)` style — but coverage uses no DB, so just templates dep).

## TDD Requirement

For S01 the testable units are:
- `coverage_service.load_coverage()` — write at least one failing test (RED) before implementing the service. S05 will expand the test set; S01 must leave the service correct against ≥3 cases (file missing, valid JSON, malformed JSON).

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix and re-stage
2. `make typecheck` — zero new errors on touched files
3. `make lint` — zero errors
4. `make test-unit` — passes (and the new coverage threshold is met)

Populate the `preflight` block of the result contract.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and confirm:
- All existing tests still pass.
- Coverage HTML/XML/JSON files exist under `tests/output/coverage/`.
- `--cov-fail-under=<floor>` is enforced (verified by reading the failing message format if you intentionally drop a covered line — not required, but verify the flag is wired).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "Makefile",
    ".gitignore",
    "dashboard/services/coverage_service.py",
    "dashboard/routers/coverage.py",
    "dashboard/app.py",
    "scripts/e2e_health_check.py",
    "ai-dev/active/F-00069/F-00069_Feature_Design.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "baseline_coverage": {
    "measured_on": "YYYY-MM-DD",
    "baseline_percent": 0.0,
    "floor_percent": 0
  },
  "blockers": [],
  "notes": "Templates intentionally not created — owned by S02. /system/coverage will 500 until S02 lands."
}
```
