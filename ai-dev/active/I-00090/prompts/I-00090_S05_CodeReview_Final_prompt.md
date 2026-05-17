# I-00090_S05_CodeReview_Final_prompt

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. Testcontainers spun by
pytest fixtures are exempt; read-only introspection is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Alembic upgrade/downgrade/stamp commands against live DBs are prohibited
from agent context. This item does not generate any migration; if you
see one in any report's `files_changed`, that is a CRITICAL finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00090 --json`
- `ai-dev/active/I-00090/I-00090_Issue_Design.md` -- Design document
- `ai-dev/active/I-00090/I-00090_Functional.md` -- Functional summary
- `ai-dev/active/I-00090/reports/I-00090_S01_Backend_report.md`
- `ai-dev/active/I-00090/reports/I-00090_S02_CodeReview_Backend_report.md`
- `ai-dev/active/I-00090/reports/I-00090_S03_Tests_report.md`
- `ai-dev/active/I-00090/reports/I-00090_S04_CodeReview_Tests_report.md`
- All files in any implementation report's `files_changed` — expected total: `dashboard/routers/running.py` + `tests/dashboard/test_running_router_active_filter.py`

## Output Files

- `ai-dev/active/I-00090/reports/I-00090_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for I-00090. Per-agent reviews (S02, S04) have already been done; your job is to catch cross-cutting issues they could not — completeness vs the design document, consistency between the production fix and its tests, AC traceability, scope adherence at the package level.

## Read the Design Document FIRST

Read `ai-dev/active/I-00090/I-00090_Issue_Design.md` BEFORE running any gates and BEFORE opening any changed files.

- Read the `## Acceptance Criteria` section in full — AC1, AC2, AC3, AC4, AC5 are all in scope.
- Read the `## TDD Approach` section — write down each of the 16 mandatory test names. Cross-check every name against `tests/dashboard/test_running_router_active_filter.py`. Any missing one is a CRITICAL finding.
- Read the `## File Manifest` and `## Impacted Paths` sections — the only files that should appear across all implementation reports' `files_changed` are `dashboard/routers/running.py` and `tests/dashboard/test_running_router_active_filter.py`. Any other file (especially the templates, the running-now helpers, or any migration) is a HIGH "scope violation" finding.
- Read the `## Notes` section — note that the running-now helpers (`_query_running_now`, `get_running_count`) are intentionally OUT OF SCOPE.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in the changed files is a CRITICAL finding.

## Review Checklist

### 1. Completeness vs Design Document (CRITICAL)

- AC1 satisfied: failed steps from completed/cancelled/archived items are filtered out of `_query_failed_steps`.
- AC2 satisfied: failed steps from active items (draft/approved/in_progress/paused/failed, archived_at=None) DO surface.
- AC3 satisfied: same filter on `_query_recent_completions`.
- AC4 satisfied: 16 tests in `tests/dashboard/test_running_router_active_filter.py` and they pass.
- AC5 is owned by the qv-browser step (S13) and is not assessable here — note this in your report.
- ALL 16 test names from the design's TDD Approach section appear in the test file.

### 2. Cross-Agent Consistency (HIGH)

- The active-item predicate in `dashboard/routers/running.py` MUST match what the tests assert against. Specifically:
  - Predicate excludes: `archived_at IS NOT NULL` OR `status IN (completed, cancelled)`.
  - Tests excludes: same items.
  - Predicate includes: `status IN (draft, approved, in_progress, paused, failed)` AND `archived_at IS NULL`.
  - Tests confirm: status=in_progress, status=failed, status=paused all surface.
- If the production predicate uses a different enum set than the tests assume, that is a HIGH cross-cutting "consistency" finding.

### 3. Integration Points (HIGH)

- `_query_failed_steps` and `_query_recent_completions` are still called from the correct route handlers (`running_tasks`, `project_running_tasks`).
- The template `dashboard/templates/pages/system/running.html` still receives the same kwargs (`failed_rows`, `completed_rows`) — render path is intact.
- `get_running_count` (sidebar badge) is UNCHANGED.
- `_query_running_now` is UNCHANGED.

### 4. Test Coverage (Holistic) (HIGH)

- Helper-level tests AND route-level tests both exist (per the design — neither alone is sufficient).
- Route-level tests use the dashboard `client` fixture (registered in `tests/dashboard/conftest.py`) — not the integration `db_session` fixture directly. This is correct because they need the FastAPI stack.
- Test 8 (project filter regression on `_query_failed_steps`) AND Test 16 (project filter on the project route) are BOTH present — the project-filter logic predates this fix and must not be regressed.

### 5. Architecture Compliance (MEDIUM_FIXABLE if violated)

- Per `dashboard/CLAUDE.md`: "Routers are thin — business logic belongs in the orch/ layer." The query helpers in `running.py` are EXISTING private functions in the router file; the fix follows the existing pattern. This is acceptable. Do NOT raise an architecture finding suggesting these should move to `orch/` — that's a separate refactor.
- SQLAlchemy 2.0 style: `is_(None)` (not `== None`), `WorkItemStatus.completed` (not `"completed"` string).

### 6. Security (Cross-Cutting)

- No hardcoded secrets, credentials, or API keys.
- New predicates use enum literals, not user input — no injection surface.
- Authorization unchanged (routes were already public; this fix doesn't change that).

### 7. Scope Verification (HIGH)

Run:
```bash
git diff --name-only main...HEAD
```

The output MUST be a subset of:
- `dashboard/routers/running.py`
- `tests/dashboard/test_running_router_active_filter.py`
- `ai-dev/active/I-00090/**` (design docs, prompts, manifest, reports, evidences)

Any other file (template, migration, model, executor, etc.) is a HIGH "scope violation" finding.

### 8. TDD RED Evidence Audit (HIGH)

- S01's report (Backend) MUST have `tdd_red_evidence` either as an inline-reproduction snippet OR the explicit `"n/a — query-only filter; behavioural tests added in S03 …"` form. Empty/missing is HIGH.
- S03's report (Tests) MUST have `tdd_red_evidence` as a textual reasoning sentence (per the S03 prompt; runtime source-revert is prohibited). Empty/missing is HIGH.
- The designated reproduction test (`test_query_failed_steps_excludes_completed_item`) MUST exist in the file.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run **`make test-unit`** — must report zero failures.
2. Run the **new** test file in isolation:

   ```bash
   uv run pytest tests/dashboard/test_running_router_active_filter.py -v
   ```

   All 16 tests MUST pass.

Do **NOT** run `make allure-integration` or `make test-integration` here — full-suite integration is owned by the dedicated S12 qv-gate (`integration-tests`) and duplicating it in a review step caused multi-thousand-second timeouts in I-00073/S03. If the targeted run above passes and per-step lint/format/typecheck are clean, the integration gate will catch any wider regression on its own.

If the targeted run fails, this is a CRITICAL finding. Report the failing test names in your `findings` array.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing AC, missing required test, lint/format/typecheck violation, targeted test failure, migration generated |
| **HIGH** | Scope violation, predicate ↔ test enum mismatch, missing TDD RED evidence, broken integration |
| **MEDIUM_FIXABLE** | Convention violation (`== None`, brittle assertion) |
| **MEDIUM_SUGGESTION** | Cleanup, documentation |
| **LOW** | Nit |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00090",
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
  "test_summary": "X unit passed, 16 targeted passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: list any AC or test name from the design that has no implementation. Each is automatically CRITICAL.
- `cross_cutting`: true for findings that span multiple agents' work (e.g. predicate↔test mismatch).
