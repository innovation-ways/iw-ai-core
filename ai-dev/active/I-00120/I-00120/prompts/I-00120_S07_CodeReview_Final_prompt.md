# I-00120_S07_CodeReview_Final_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Do not run any command that changes Docker state. Testcontainer fixtures, read-only introspection, and
`./ai-core.sh` / `make` targets are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json`.
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design doc.
- All step reports: `ai-dev/work/I-00120/reports/I-00120_S*_report.md`.
- All files changed across S01/S03/S05 (`orch/llm_usage.py`, `dashboard/routers/usage.py`,
  `dashboard/templates/fragments/llm_usage_footer.html`, `tests/unit/test_llm_usage.py`,
  `tests/dashboard/test_usage_fragment.py`).

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S07_CodeReview_Final_report.md` — final review report.

## Context

Final cross-agent review of all I-00120 work. Per-step reviews are done; catch cross-cutting issues
they could not: does the backend `status` contract line up end-to-end with what the router maps and the
template renders, and what the tests assert?

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```
New violations in changed files → CRITICAL.

## Scope Diff — Directional (MANDATORY)

```bash
git diff main...HEAD --name-only -- 'orch/**' 'dashboard/**' 'tests/**'
git status -s -- 'orch/**' 'dashboard/**' 'tests/**'
```
Confirm only the five allow-listed paths (plus `ai-dev/**`) changed. Anything else is a scope finding;
classify direction (Feature-added vs main-ahead) before flagging.

## Review Checklist (item-specific)

1. **End-to-end contract consistency** — the exact `status` string values emitted by
   `orch/llm_usage.py` (`ok`/`expired`/`unauthenticated`/`error`) are precisely the keys the router's
   mapping consumes, and the warning phrases the router emits are precisely what the template renders
   and the tests assert. No drift in any of the four spellings.
2. **Completeness vs design** — every Acceptance Criterion (AC1 bug fixed, AC2 regression test exists)
   is satisfied. The four failure modes from the design's tables are all implemented and tested.
3. **No token refresh anywhere** — confirm the whole diff contains no OAuth refresh / `auth.json`
   write / token-endpoint call (explicitly out of scope). Any such code is CRITICAL.
4. **`text-amber-600` is pre-compiled** in `dashboard/static/styles.css` (no `make css` dependency).
5. **Never-raises guarantee** preserved in `_codex_usage()`; Claude/MiniMax/60s-cache paths untouched.
6. **Tests are semantic, not shape-only** (re-confirm the S06 conclusion holds across the full picture).

## Test Verification (NON-NEGOTIABLE)

Run the full unit AND integration suites; report results. Integration failures are CRITICAL.
```bash
make test-unit
make test-integration
```

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW. `verdict: pass` only when zero
CRITICAL + HIGH + MEDIUM_FIXABLE.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00120",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
