# F-00088_S02_CodeReview_prompt

**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`,
`docker volume rm|prune`, `docker system prune`, …). Allowed: testcontainers via
pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make`
targets. If your task seems to require a prohibited command, STOP and raise a
blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

F-00088 adds no migration. If you find a migration file in the changeset, that
is a **CRITICAL** scope violation. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status F-00088 --json`.
- `ai-dev/active/F-00088/F-00088_Feature_Design.md` — design document.
- `ai-dev/work/F-00088/reports/F-00088_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed`.

## Output Files

- `ai-dev/work/F-00088/reports/F-00088_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the S01 implementation of F-00088 — a test-infrastructure
Feature that adds the E2E harness foundation: the `tests/e2e/` directory, the
playwright-cli Python wrapper, the `e2e`/`e2e_smoke` markers, Makefile targets,
and the first journey (`test_journey_home_navigation.py`).

Read the design document first (especially the Acceptance Criteria, Boundary
Behavior, Invariants, and TDD Approach sections), then the S01 report, then
every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC7), `## Boundary Behavior`, `## Invariants`,
and `## TDD Approach` in full. Every AC is a mandatory check. Note the files
the design names — all MUST appear in S01's `files_changed`; a missing one is
**CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation (not on `main` before S01) is a **CRITICAL** finding
with `category: conventions`, the file/line, and the exact code+message. Also run
`make test-assertions` — a new assertion-scanner violation in any new test file
is **CRITICAL**. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched.** The only files changed must be within
  `scope.allowed_paths`: `tests/e2e/**`, `pyproject.toml`, `uv.lock`, `Makefile`,
  `scripts/e2e_seed.py` (if extended). Any edit to `orch/`, `dashboard/`,
  `executor/` is a **CRITICAL** scope violation — including a "temporary fix"
  for a 5xx the journey found (those must be xfailed with a `TODO(file-incident)`
  placeholder and listed as operator follow-up, not fixed; see the TDD Approach
  section).
- **No production-code edit for the RED demonstration.** F-00088's TDD approach
  proves the harness can fail entirely within `tests/e2e/**` (the
  `test_harness_selfcheck.py` unit tests against synthetic input). Production
  handlers and templates must NOT be edited even "temporarily". Run
  `git diff origin/main -- dashboard/ orch/ executor/` — it MUST be empty; any
  output is a **CRITICAL** scope violation.

### 2. AC1 — playwright-cli wrapper correctness

- `tests/e2e/playwright_wrapper.py` exists and is in S01's `files_changed`.
- ALL browser interactions are subprocess calls to `playwright-cli`. Grep for
  `chromium.launch`, `agent-browser`, `npx playwright`, `from playwright` —
  any of these in `tests/e2e/` is **CRITICAL**.
- The wrapper raises a clear `RuntimeError` (not a cryptic `FileNotFoundError`)
  at init time if the binary is absent — check the binary-check logic.
- The wrapper exposes at minimum: `open_url`, `goto`, `snapshot`, `click`,
  `fill`, `screenshot`, `read_console_errors`, `accessibility_check`.
- `screenshot` copies the latest `.playwright-cli/page-*.png` to the dest —
  it does NOT pass a path argument to `playwright-cli screenshot`.
- `open_url` is called only once per session; `goto` is used for subsequent
  navigations — verify there is no second `open_url` in the journey module.

### 3. AC3 — marker exclusion verified

- `e2e` and `e2e_smoke` markers are registered in `pyproject.toml`
  `[tool.pytest.ini_options].markers` with prose descriptions.
- The `addopts` `-m` filter now excludes `e2e`; `--strict-markers` and all
  other flags are intact.
- Verify the exclusion actually works:
  `uv run pytest tests/e2e/ --collect-only -q`
  must collect **zero `e2e`-marked journey tests** under the default selection
  (the unmarked `test_harness_selfcheck.py` unit tests ARE collected — that is
  intended; they need no stack). If any journey is collected by the default
  selection, E2E journeys would run in `make test-integration` → **CRITICAL**.
- Verify the smoke target:
  `uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q`
  must collect `test_journey_home_navigation`.

### 4. AC4 (partial) — Makefile targets

- `test-e2e` target exists: `uv run pytest tests/e2e/ -m e2e -v --no-cov`.
- `test-e2e-smoke` target exists: `uv run pytest tests/e2e/ -m e2e_smoke -v --no-cov`.
- Both are in the `.PHONY` line.

### 5. AC6 (partial) — E2E stack isolation

- The `base_url` conftest fixture reads `$IW_BROWSER_BASE_URL`.
- If `IW_BROWSER_BASE_URL` is not set, the `base_url` / `pw` fixtures skip with
  a message starting `E2E_STACK_MISSING:` — a fixture-scoped skip, not a hard
  `RuntimeError` and not a directory-wide collection hook (the harness
  self-check unit tests must still run without the stack).
- No hardcoded ports (no `localhost:5173`, `localhost:9900`, or any numeric
  port literal) appear in the wrapper or conftest.

### 6. Journey 1 quality

- `test_journey_home_navigation.py` is marked `@pytest.mark.e2e` AND
  `@pytest.mark.e2e_smoke`.
- The journey asserts at least: the home page lists projects, a project page
  renders with the project name visible, each main project tab renders
  (HTTP 200), zero console errors, and the accessibility check passes.
- The dashboard has **no authentication** — there is no login. Any login /
  logout / credential (`IW_BROWSER_E2E_*`) assertion in this journey is a
  **MEDIUM (fixable)** finding: the journey was deliberately refocused away
  from the auth premise to home → project → cross-tab navigation.
- Assertions are behavioural and strong — apply `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist. An assertion of `assert page_text is not None` with no
  content check is **MEDIUM (fixable)**.
- The journey is order-independent (`pytest-randomly` is on by default): no
  test-level state bleeds to other tests.

### 7. TDD RED Evidence

S01 is a test-infrastructure step. Confirm `tdd_red_evidence` records the
**harness self-check** demonstration: `tests/e2e/test_harness_selfcheck.py`
(unmarked unit tests, in scope) exercising the console-error detector and the
accessibility check with synthetic bad input, each shown RED-first then GREEN.
The RED snippet must be a real `AssertionError`, not a collection/import
error. If `tdd_red_evidence` is missing, says `n/a`, or describes a
production-code injection (a `raise`/`console.error` added to `dashboard/`),
raise a **HIGH** finding: a harness that cannot be shown to fail is worthless,
and a production-code injection is itself a scope violation (see §1).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, security issue |
| **HIGH** | Significant bug, missing AC, chromium.launch / agent-browser present, marker exclusion broken |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00088",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "collection verified: 0 tests under default addopts; test_journey_home_navigation collected under -m e2e_smoke",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
