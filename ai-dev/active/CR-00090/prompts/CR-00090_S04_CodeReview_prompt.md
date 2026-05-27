# CR-00090_S04_CodeReview_prompt

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Steps Being Reviewed**: S01 (backend-impl), S02 (frontend-impl), S03 (tests-impl)
**Review Step**: S04

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
- `ai-dev/active/CR-00090/CR-00090_CR_Design.md` — Design document (authoritative spec)
- `ai-dev/active/CR-00090/reports/CR-00090_S01_Backend_report.md` — S01 report
- `ai-dev/active/CR-00090/reports/CR-00090_S02_Frontend_report.md` — S02 report
- `ai-dev/active/CR-00090/reports/CR-00090_S03_Tests_report.md` — S03 report
- All files listed in each report's `files_changed`

## Output Files

- `ai-dev/active/CR-00090/reports/CR-00090_S04_CodeReview_report.md` — Review report

## Context

You are reviewing the implementation work from S01 (backend), S02 (frontend), and S03
(tests) for CR-00090.

## Read the Design Document FIRST

Read `ai-dev/active/CR-00090/CR-00090_CR_Design.md` in full before opening any code.
Pay particular attention to:
- `## Acceptance Criteria` — all six ACs are mandatory checks
- `## TDD Approach` — confirms `tests/unit/test_config.py` and `tests/dashboard/test_e2e_mode.py`
  must both be present in some step's `files_changed`. Missing either is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code:

```bash
make lint
make format-check
```

Any NEW violations in the changed files are **CRITICAL** findings.

## Scope Discipline

Use directional diff to verify no out-of-scope changes:

```bash
git diff main...HEAD --name-only
git status -s
```

The CR's `scope.allowed_paths` covers:
- `orch/config.py`
- `dashboard/app.py`
- `dashboard/templates/base.html`
- `dashboard/templates/fragments/staleness_dot.html`
- `dashboard/templates/pages/project_selector.html`
- `ai-dev/iw-config/worktree-compose.template.yml`
- `tests/unit/test_config.py`
- `tests/dashboard/test_e2e_mode.py`

Files under `ai-dev/active/CR-00090/**` are implicitly allowed.

## Review Checklist

### 1. S01 Backend Review

- `orch/config.py`: Is `get_e2e_mode()` present? Does it return `True` for `"true"`, `"1"`,
  `"TRUE"` and `False` for everything else? Is it function-scoped (reads env at call time)?
- `dashboard/app.py`: Is `_e2e_mode` injected into `templates.env.globals`? Is it set once at
  startup (not per-request)? Is `get_e2e_mode` imported from `orch.config`?
- `tests/unit/test_config.py`: Are all six parametrized cases present? Does it use
  `monkeypatch.setenv` / `monkeypatch.delenv` (NOT `importlib.reload`)?

### 2. S02 Frontend Review

- `dashboard/templates/base.html`: Is `_headless` now `_e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua)`?
- `dashboard/templates/fragments/staleness_dot.html`: Same change?
- `dashboard/templates/pages/project_selector.html`: Same change?
- `ai-dev/iw-config/worktree-compose.template.yml`: Is `IW_CORE_E2E_MODE: "true"` present in the `app` service's `environment:` block?
- Jinja2 format filters: are ALL `format` calls still `%`-style? (enforced by `make lint`)

### 3. S03 Tests Review

- `tests/dashboard/test_e2e_mode.py`: Are tests B and C present (polling suppressed vs. present)?
  Do they actually assert on `hx-trigger="never"` and `hx-get` attributes?
- Are tests isolated? (use `monkeypatch`, not `importlib.reload`)
- Does each test assert on **behaviour** (the HTML attribute), not just on their own mocks?
  A test that passes even if `_e2e_mode` is never injected is not a valid test (mutation test criterion).

### 4. AC Completeness

Verify each AC against the code:
- **AC1**: Does `IW_CORE_E2E_MODE=true` → `hx-trigger="never"` + no `hx-get`? (test B + S02)
- **AC2**: Does unset env var → polling attributes present? (test C + S02)
- **AC3**: Does UA fallback still apply when env var is absent? (template OR expression)
- **AC4**: Does `get_e2e_mode()` handle all six value cases? (unit tests)
- **AC5**: Is `_e2e_mode` global always available without route handler passing it? (S01 injection)
- **AC6**: Are no other pages or flows broken? (regression coverage in tests)

### 5. Security

- No hardcoded secrets or credentials in any file
- The env var is read-only; no security surface is introduced

## Test Verification

```bash
uv run pytest tests/unit/test_config.py -v -k "e2e" --no-cov
uv run pytest tests/dashboard/test_e2e_mode.py -v --no-cov
```

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00090",
  "step_reviewed": "S01-S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
