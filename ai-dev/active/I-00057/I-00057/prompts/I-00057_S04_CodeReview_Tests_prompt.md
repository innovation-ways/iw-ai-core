# I-00057_S04_CodeReview_Tests_prompt

**Work Item**: I-00057 -- Chat panel collapse toggle is intrusive and panel starts open
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00057 --json`
- `ai-dev/active/I-00057/I-00057_Issue_Design.md`
- `ai-dev/active/I-00057/reports/I-00057_S03_Tests_report.md`
- The new test file added in S03 (`tests/dashboard/test_chat_panel_default_collapsed.py`)
- `dashboard/templates/chat/panel.html` (the implementation it covers)

## Output Files

- `ai-dev/active/I-00057/reports/I-00057_S04_CodeReview_report.md`

## Pre-Review Gate

```bash
make lint
make format
```

NEW violations on changed test files → CRITICAL.

## Review Checklist

### 1. Falsifiability

Each test must FAIL on pre-S01 code.

- `data-collapsed="true"` test: would fail on `main` (template ships `false`).
- No-floating-tab test: would fail on `main` (the literal `style="left: -48px;"` is in the template).
- Affordance-labels test: would fail on `main` (only `aria-label="Collapse chat panel"` exists; "Expand chat panel" appears only as a JS-set runtime label, not in static markup).

If any test would PASS on `main` as-is, flag CRITICAL.

### 2. Specific values, not just shape

- `'data-collapsed="true"' in html` AND `'data-collapsed="false"' not in html` — both halves required.
- `'style="left: -48px;"' not in html` AND `'id="chat-toggle-tab"' not in html` — both halves required.
- `'aria-label="Collapse chat panel'` AND `'aria-label="Expand chat panel'` — both must be present.

### 3. Real-DB integration discipline

Tests use the project's testcontainer pattern from `tests/dashboard/conftest.py`. No DB mocks. FTS triggers run after `create_all`.

### 4. Test isolation

- Each test seeds its own project (or reuses a function-scoped fixture).
- No reliance on localStorage state — these are server-rendered HTML tests; localStorage behavior is browser-tested in S11.

### 5. Convention conformance

- File location matches existing dashboard tests.
- Naming follows project pattern (`test_*.py`, `def test_*`).
- Imports follow project style.

## Test Verification

```bash
make test-unit
make test-integration   # if green on main
```

## Severity Levels

| CRITICAL | Test passes on pre-fix code; test asserts only shape | Must fix |
| HIGH | Coverage gap (only one of the three required assertions present) | Must fix |
| MEDIUM (fixable) | Convention drift | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00057",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
