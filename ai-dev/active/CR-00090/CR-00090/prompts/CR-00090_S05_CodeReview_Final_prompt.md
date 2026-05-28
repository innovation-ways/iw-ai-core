# CR-00090_S05_CodeReview_Final_prompt

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

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

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration is required for this CR.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00090 --json`
- `ai-dev/active/CR-00090/CR-00090_CR_Design.md` — Design document
- All implementation step reports: `ai-dev/active/CR-00090/reports/CR-00090_S0{1,2,3}_*_report.md`
- Per-agent code review report: `ai-dev/active/CR-00090/reports/CR-00090_S04_CodeReview_report.md`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/active/CR-00090/reports/CR-00090_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the final cross-agent review of ALL implementation work for CR-00090.

## Read the Design Document FIRST

Read `ai-dev/active/CR-00090/CR-00090_CR_Design.md` fully before touching any code.
Every AC is a mandatory check. The TDD Approach section names two test files:
- `tests/unit/test_config.py` (modified by S01)
- `tests/dashboard/test_e2e_mode.py` (created by S03)

Both MUST appear in the combined `files_changed` of S01–S03 reports. Missing either
is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violations in the changed files are **CRITICAL** findings.

## Scope Diff (Directional — NON-NEGOTIABLE)

```bash
git diff main...HEAD --name-only
git log --name-only --pretty='%h %s' main..HEAD
git status -s
```

The CR's `scope.allowed_paths`:
- `orch/config.py`
- `dashboard/app.py`
- `dashboard/templates/base.html`
- `dashboard/templates/fragments/staleness_dot.html`
- `dashboard/templates/pages/project_selector.html`
- `ai-dev/iw-config/worktree-compose.template.yml`
- `tests/unit/test_config.py`
- `tests/dashboard/test_e2e_mode.py`

Files under `ai-dev/active/CR-00090/**` are implicitly allowed. Use directional
(`git diff main...HEAD`, triple-dot) — never symmetric (`git diff main`).

## Review Checklist

### 1. Completeness vs Design Document

- `get_e2e_mode()` in `orch/config.py` returns True for `"true"`, `"1"`, `"TRUE"` and
  False for absent/other? (AC4)
- `_e2e_mode` global injected into `templates.env.globals` in `dashboard/app.py`? (AC5)
- All three templates updated with `_e2e_mode or ...` expression? (AC1, AC2, AC3)
- `IW_CORE_E2E_MODE: "true"` present in `ai-dev/iw-config/worktree-compose.template.yml`? (AC1)
- Both test files present and covering the required cases? (AC4, AC5)

### 2. Cross-Agent Consistency

- The global variable name `_e2e_mode` is consistent: `get_e2e_mode()` in config.py,
  `templates.env.globals["_e2e_mode"]` in app.py, `_e2e_mode` in template `{% set %}` expressions.
- The Jinja2 `_headless` variable name is PRESERVED in templates — only the right-hand
  expression is changed. Verify no template accidentally dropped `_headless` entirely.

### 3. Integration Points

- The `_e2e_mode` global is set at app startup in `dashboard/app.py`. Verify it is NOT
  set inside a request handler or a lifespan event that fires per-request. It must be
  set once and remain constant for the app's lifetime.
- The templates that use `_headless` must all see `_e2e_mode` from the global context
  without requiring the route handler to pass it — verify there are no route handlers
  that override `_e2e_mode` or `_headless` explicitly.

### 4. Test Coverage (Holistic)

- Unit tests cover all six `get_e2e_mode()` parametrized cases?
- Dashboard tests cover both the "suppressed" (E2E mode) and "active" (prod mode) paths?
- Tests use `monkeypatch` correctly — no `importlib.reload()` calls anywhere?
- Tests assert on observable HTML attributes (`hx-trigger`, `hx-get`), not on mocks?

### 5. Architecture Compliance

- Config function pattern in `orch/config.py` matches existing `get_*()` functions?
- Global injection site in `dashboard/app.py` matches how `is_db_stale` and `static_v`
  are injected (must be at the same startup phase)?
- No circular imports introduced?

### 6. AC6: No Regression

- Does the compose template change affect any service other than `app`? (It must not)
- Does the template change break the UA fallback (AC3)? The expression must be
  `_e2e_mode OR ('headlesschrome' in _ua) OR ('playwright' in _ua)` — verify
  the OR short-circuit preserves the UA check.

## Test Verification (NON-NEGOTIABLE)

Run the full unit and integration test suites:

```bash
make test-unit
make test-integration
```

Any failure is a **CRITICAL** finding.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "CR-00090",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
