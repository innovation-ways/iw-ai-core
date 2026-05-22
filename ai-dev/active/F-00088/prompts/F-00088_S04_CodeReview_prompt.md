# F-00088_S04_CodeReview_prompt

**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

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
- `ai-dev/work/F-00088/reports/F-00088_S03_Backend_report.md` — S03 report.
- All files listed in the S03 report's `files_changed`.
- S01 and S02 reports for context.

## Output Files

- `ai-dev/work/F-00088/reports/F-00088_S04_CodeReview_report.md` — review report.

## Context

You are reviewing the S03 implementation of F-00088 — the remaining five journey
modules, the `e2e_smoke` subset designation, the GitHub Actions workflow, and the
documentation/skill/plan updates.

Read the design document first (especially AC1–AC7, Boundary Behavior, Invariants,
and TDD Approach), then the S03 report, then every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC7), `## Boundary Behavior`, `## Invariants`,
and `## TDD Approach` in full. Note the five journey modules S03 must deliver —
all MUST appear in S03's `files_changed`; any missing one is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation is a **CRITICAL** finding. Also run `make test-assertions`.
If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched** beyond `scripts/e2e_seed.py`. Any edit to
  `orch/`, `dashboard/`, `executor/` is a **CRITICAL** scope violation —
  including a fix for any 5xx a journey found (those must be xfailed with a
  filed Incident ID; see the TDD Approach section).
- **No production-code edit for the RED demonstration.** The S03 RED proof is
  the extended `tests/e2e/test_harness_selfcheck.py` unit tests against
  synthetic input — not a "temporary" break of a route or template. Run
  `git diff origin/main -- dashboard/ orch/ executor/` — it MUST be empty; any
  output is a **CRITICAL** scope violation.

### 2. AC2 — all six journeys exist and assert a11y + no console errors

- Verify all five journey modules are in S03's `files_changed`:
  - `tests/e2e/test_journey_queue_to_merge.py`
  - `tests/e2e/test_journey_code_qa_sse.py`
  - `tests/e2e/test_journey_docs_export.py`
  - `tests/e2e/test_journey_jobs_filters.py`
  - `tests/e2e/test_journey_htmx_fragments.py`
- Each journey must contain at least one `accessibility_check` assertion and
  at least one `assert_no_console_errors()` (or equivalent) assertion — grep
  for these in each file. Absence in any journey is **HIGH**.
- Assertions are behavioural and strong — apply `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist.

### 3. AC4 — e2e_smoke subset is exactly two journeys

- Verify: `uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q` collects
  exactly `test_journey_home_navigation` and `test_journey_queue_to_merge` — no
  more, no fewer. If a third journey is also marked `e2e_smoke`, that is **HIGH**
  (the spec names exactly two journeys in the smoke subset).

### 4. AC5 — e2e.yml workflow correctness

- `e2e-smoke` job triggers on `pull_request` + `push`; **no** `continue-on-error`.
- `e2e-full` job triggers on `schedule` + `workflow_dispatch`; `continue-on-error: true`.
- Neither job triggers on the wrong events — verify the `on:` block carefully:
  - `e2e-smoke` appearing in `schedule:` is **HIGH** (would run slow nightly suite on every scheduled run).
  - `e2e-full` appearing in `push:` is **HIGH** (would run slow full suite on every commit).
- Both jobs bring up and tear down the E2E stack cleanly. The env vars
  `scripts/e2e_up.sh` expects (`COMPOSE_PROJECT_NAME`, `E2E_FRONTEND_PORT`,
  `E2E_DB_PORT`, `IW_BROWSER_BASE_URL`) are documented in the workflow file.
- No hardcoded ports in the workflow YAML.
- The teardown step runs in an `always:` condition so the stack is torn down
  even when tests fail.

### 5. Journey 6 — htmx-fragments relationship to CR-00072

- `test_journey_htmx_fragments.py` must have a module docstring (or a prominent
  comment) explaining that this journey is the **browser-level complement** to
  CR-00072's TestClient route sweep — CR-00072 has no JS/HTMX runtime; this
  journey does. Absence of this note is **MEDIUM (fixable)** — it will confuse
  the next engineer who reads both files.
- The journey checks for dangling `hx-target` references via `curl` + HTML
  inspection — verify this logic is present and not just a stub.

### 6. AC7 — docs / skill / plan

- `docs/IW_AI_Core_Testing_Strategy.md` describes the E2E layer (§3/§5/§9);
  the ad-hoc `-m browser` description is updated.
- `skills/iw-ai-core-testing/SKILL.md` notes the E2E layer + how to extend it.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is **byte-identical** to the
  master (`diff` them — a mismatch means `iw sync-skills --force` was not run
  → **HIGH**).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.1 → DONE (F-00088); a §11
  changelog entry exists with the journey names and any Incident IDs for xfailed
  journeys.

### 7. Invariant checks

- Invariant 6: grep `tests/e2e/` for `chromium.launch`, `agent-browser`,
  `npx playwright` — any match is **CRITICAL**.
- Invariant 7: any journey that encountered a genuine dashboard 5xx must be
  xfailed with a filed Incident ID (not silently passing). A journey that
  swallows a 5xx without an xfail or Incident is **HIGH**.
- Invariant 8: exactly two journeys carry `@pytest.mark.e2e_smoke`.

### 8. TDD RED Evidence

Confirm `tdd_red_evidence` records the **extended harness self-check** —
`tests/e2e/test_harness_selfcheck.py` gaining RED-first unit tests for the
dangling-`hx-target` detector and the SSE-timeout detector (synthetic input,
no stack), each shown RED then GREEN. Also confirm each of the 5 new journey
modules carries the one-line assertion-inversion comment. A missing self-check
test for either detector is **HIGH**; a `tdd_red_evidence` that describes a
production-code injection is **HIGH** and also a scope violation (see §1).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, security issue |
| **HIGH** | Significant bug, missing AC, chromium.launch present, marker mismatch, smoke count wrong, doc not synced |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion, missing docstring note |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00088",
  "step_reviewed": "S03",
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
  "test_summary": "collection verified: 6 journeys under -m e2e; exactly 2 under -m e2e_smoke; 0 e2e-marked journey tests under default addopts",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
