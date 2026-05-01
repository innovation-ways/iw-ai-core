# I-00057_S05_CodeReview_Final_prompt

**Work Item**: I-00057 -- Chat panel collapse toggle is intrusive and panel starts open
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00057 --json`
- `ai-dev/active/I-00057/I-00057_Issue_Design.md`
- All step reports under `ai-dev/active/I-00057/reports/`
- All files in those reports' `files_changed`

## Output Files

- `ai-dev/active/I-00057/reports/I-00057_S05_CodeReview_Final_report.md`

## Pre-Review Gate

```bash
make lint && make format && make typecheck
```

NEW violations on changed files → CRITICAL.

## Cross-Step Review Checklist

### 1. End-to-end fix coverage

Trace each acceptance criterion to a passing test or verifiable evidence:

- AC1 (panel defaults to collapsed) → S03 dashboard test.
- AC2 (no floating tab) → S03 dashboard test.
- AC3 (collapsed-state preference persists globally) → S11 browser verification (localStorage round-trip).
- AC4 (expand affordance visible when collapsed) → S03 affordance-label test.
- AC5 (collapse affordance visible when expanded) → S03 affordance-label test.
- AC6 (regression test exists) → all S03 tests.

If any AC has no covering test/verification, raise CRITICAL.

### 2. JS / template consistency

- The element IDs the template renders match the IDs `panel.js` queries: `#chat-collapse-btn`, `#chat-expand-rail`, `#chat-panel`, etc. No orphan listeners attaching to nonexistent elements.
- No leftover references to `#chat-toggle-tab` in either file.
- Cmd+\\ keyboard shortcut still works because it goes through `togglePanel()` which now also persists the state.

### 3. Mobile drawer untouched

- `#chat-drawer-open`, `#chat-drawer-backdrop`, `openDrawer`, `closeDrawer`, the mobile-only `#chat-close-btn` are unchanged.
- The mobile drawer-open behavior does NOT toggle `data-collapsed` — it uses `translate-x-full` instead.

### 4. No scope creep

Out-of-scope (must not appear):

- Diagram rendering changes (I-00055 territory).
- Chip strip / collapsible H2 changes (I-00056 territory).
- Chat width persistence changes — `iw_chat_width` semantics must be unchanged.
- Other chat sub-templates (`composer.html`, `message.html`, parts/*).

### 5. CLAUDE.md conformance

- No `docker compose up` calls.
- No alembic upgrade/downgrade/stamp.
- No live-DB connections from tests.
- Tailwind classes statically composable; `make css` ran if needed.
- `node --check` passes on `panel.js`.

## Test Verification

```bash
make test-unit
make test-integration   # if green on main
```

## Severity Levels

| CRITICAL | AC has no test; orphan listener; persistence broken | Must fix |
| HIGH | Mobile drawer regressed; scope creep | Must fix |
| MEDIUM (fixable) | Cross-cut convention drift | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00057",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
