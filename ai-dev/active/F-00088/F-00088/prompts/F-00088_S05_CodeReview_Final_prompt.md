# F-00088_S05_CodeReview_Final_prompt

**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` and `make` targets. If your task seems to require a prohibited
command, STOP and raise a blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

F-00088 adds no migration. A migration file in the changeset is a **CRITICAL**
finding. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status F-00088 --json`.
- `ai-dev/active/F-00088/F-00088_Feature_Design.md` — design document.
- All step reports: `ai-dev/work/F-00088/reports/F-00088_S*_*_report.md`.
- All files listed in S01's and S03's `files_changed`.

## Output Files

- `ai-dev/work/F-00088/reports/F-00088_S05_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of F-00088 — a
test-infrastructure Feature adding a structured E2E test layer with six journey
modules, a playwright-cli wrapper, Makefile targets, and a two-job CI workflow.
The per-agent reviews (S02, S04) are done; your job is to verify the whole
package is coherent, complete against the design, and safe to merge.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC7), `## Boundary Behavior`, `## Invariants`,
and `## TDD Approach` in full. Cross-check all named files against S01's and S03's
`files_changed` — a missing file is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation
is a **CRITICAL** finding (`category: conventions`). If a command is unavailable,
STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design — every AC

Verify each acceptance criterion end-to-end:

- **AC1** — `playwright_wrapper.py` exists; all browser interactions are
  subprocess calls to `playwright-cli`; no `chromium.launch` / `agent-browser` /
  `npx playwright` anywhere in `tests/e2e/` (grep independently).
- **AC2** — all six journey modules exist; each contains `accessibility_check`
  and `assert_no_console_errors` (or equivalent) assertions.
- **AC3** — `e2e` marker in `addopts` exclusion; independently verify
  `uv run pytest tests/e2e/ --collect-only -q` collects **zero `e2e`-marked
  journey tests** (the unmarked `test_harness_selfcheck.py` unit tests ARE
  collected — intended); also verify
  `uv run pytest tests/dashboard/ tests/integration/ --collect-only -q`
  collects no `e2e`-marked tests.
- **AC4** — `make test-e2e` and `make test-e2e-smoke` exist and are in `.PHONY`;
  `uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q` collects **exactly**
  `test_journey_home_navigation` and `test_journey_queue_to_merge`.
- **AC5** — `e2e.yml` exists; `e2e-smoke` triggers on `push`+`pull_request`
  without `continue-on-error`; `e2e-full` triggers on `schedule`+`workflow_dispatch`
  with `continue-on-error: true`; neither job fires on the wrong trigger.
- **AC6** — `base_url` fixture reads `$IW_BROWSER_BASE_URL`; no hardcoded ports
  anywhere in `tests/e2e/`; missing env var causes a skip, not a crash.
- **AC7** — strategy doc, skill, and plan updated; `.claude/skills/iw-ai-core-testing/SKILL.md`
  byte-identical to its master (run `diff`).

### 2. Scope integrity (CRITICAL)

- Every changed file is within `scope.allowed_paths`. No `orch/` / `dashboard/` /
  `executor/` production code edited (except `scripts/e2e_seed.py` as approved).
- **No production-code edit anywhere** — the RED demonstration is the
  `tests/e2e/test_harness_selfcheck.py` unit tests, not a route/template break.
  Run `git diff origin/main -- dashboard/ orch/ executor/` and confirm it is
  empty. Any output is a **CRITICAL** scope violation.

### 3. Cross-cutting coherence

- The `pyproject.toml` marker descriptions, Makefile targets, workflow file,
  and docs all describe the `e2e` / `e2e_smoke` markers and the two jobs
  consistently — no contradictory claims (e.g. docs saying `e2e-smoke` is
  nightly while the workflow has it on push/PR).
- The htmx-fragments journey (test 6) has a module docstring stating it is the
  **browser-level complement** to CR-00072 — not a redundant check.
- `skills/iw-workflow/SKILL.md`'s canonical QV-gate list was **not** modified
  (S14 is a qv-browser step, not a qv-gate step — adding it to the canonical
  gate list would be scope creep → **HIGH**).
- `TESTS_ENHANCEMENT.md` §11 changelog counts (journey names, xfailed count,
  operator follow-up items with `TODO(file-incident)` placeholders) match the S03
  report exactly. No real Incident IDs are expected — the operator files Incidents
  on `main` post-merge; a real `I-NNNNN` ID here means a package was created in
  the worktree, which is a **CRITICAL** scope violation.

### 4. Test effectiveness (holistic)

- The harness **can detect failures** — `tdd_red_evidence` across S01 and S03
  covers the `test_harness_selfcheck.py` self-check tests (console-error,
  accessibility, dangling-reference, SSE-timeout detectors). Run
  `uv run pytest tests/e2e/test_harness_selfcheck.py -v` yourself and confirm
  it passes. As an independent spot-check you MAY temporarily invert one
  behavioural assertion in a single journey file (`tests/e2e/**` — in scope),
  re-collect, then revert — state whether you did this. Do NOT edit any
  production file for this check.
- Assertions are behavioural and strong across all six journeys (apply
  `skills/iw-ai-core-testing/SKILL.md`'s red-flag checklist).
- All journeys are order-independent under `pytest-randomly`.

### 5. Invariant verification

For each invariant in the design doc, verify it holds in the implementation:

1. No port-5433 connection in any journey file — grep for `5433`.
2. Every journey has a `assert_no_console_errors` call.
3. Every journey has an `accessibility_check` call.
4. `--collect-only` default shows zero `e2e` tests.
5. `make test-integration` does not collect `e2e` tests.
6. No direct Playwright API anywhere in `tests/e2e/`.
7. Any genuine 5xx encountered has an `xfail` with a `TODO(file-incident)` placeholder and a one-line rationale, and is listed as operator follow-up in the step report; no `ai-dev/active/I-NNNNN/` package was created inside the worktree.
8. Exactly two journeys carry `e2e_smoke`.

### 6. Architecture & security

- Read `CLAUDE.md`. The playwright-cli rules are followed throughout:
  `kill-all` before open; `goto` after first `open_url`; no hardcoded ports;
  `$IW_BROWSER_BASE_URL` exclusively.
- No hardcoded secrets, credentials, or URLs in the workflow file or tests.
- `scripts/e2e_seed.py` extensions (if any) are idempotent.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + integration suites**:

```bash
make test-unit
make test-integration
```

`make test-integration` must NOT collect any `e2e`-marked test — if it does,
that is a **CRITICAL** finding (the `addopts` exclusion is broken). Report
results accurately. (You need not run `make test-e2e` — that requires the live
E2E stack and is the S14 qv-browser step's job.)

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, missing requirement, integration suite fails, chromium.launch present |
| **HIGH** | Significant bug, missing AC, scope creep (QV gate list modified), e2e-full fires on push, doc not synced |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion, missing docstring |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00088",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed (0 e2e collected), 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `missing_requirements`: any AC with no corresponding implementation — each is automatically CRITICAL.
