# I-00056_S07_CodeReview_Final_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00056 --json`
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- All step reports under `ai-dev/active/I-00056/reports/`
- All files in those reports' `files_changed`

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S07_CodeReview_Final_report.md`

## Context

Cross-step review for I-00056. Per-agent reviews already covered each piece in isolation — your job is the integration view.

## Pre-Review Gate

```bash
make lint && make format && make typecheck
```

NEW violations on changed files → CRITICAL.

## Cross-Step Review Checklist

### 1. End-to-end fix coverage

Trace each acceptance criterion to a passing test:

- AC1 (chip slot precedes prose) → page-level dashboard test (S05).
- AC2 (chip click loads detail) → htmx attribute parity verified by test + S04 review note.
- AC3 (Purpose-open, others-closed) → wrap helper unit tests (S05).
- AC4 (mapgen prompt asks for 1–3) → mapgen prompt-text assertion (S05).
- AC5 (regression) → all of the above pass on next CI.

If any AC has no test, raise CRITICAL.

### 2. Two-surface consistency

The chip strip and the components cards both end at `#code-detail-panel` via the same `/code/modules/{slug}` endpoint. Confirm they pass the SAME `hx-target`, `hx-swap`, and URL — no divergence. Diff the htmx attributes in `code_module_chips.html` and `code_module_cards.html`.

### 3. Render pipeline integrity

`_render_architecture_html` must call helpers in the correct order:

```
strip_trailing_arch_diagram_section (I-00055)
   → _preprocess_mermaid
   → render_markdown
   → wrap_h2_sections_collapsible
```

A wrong ordering (e.g. wrap before render) would corrupt output.

### 4. No scope creep

Out-of-scope (must not appear):

- Changes to `code_module_cards.html` (parity check only — no edits).
- Chat panel changes (I-00057's territory).
- Diagram-architecture rendering changes (I-00055's territory).
- Any DB schema or migration.

### 5. CLAUDE.md conformance across diff

- No new `docker compose up` commands.
- No alembic upgrade/downgrade/stamp calls.
- No live-DB connections from tests.
- Tailwind classes statically composable; `make css` ran.

### 6. Operational readiness

The mapgen prompt edit takes effect on the next code-map run per project. Confirm the design doc's notes mention this; no urgent regen needed because the chip strip + collapsible H2 already address the UX symptom for existing content.

## Test Verification

```bash
make test-unit
make test-integration   # if green on main
```

Both must pass.

## Severity Levels

| CRITICAL | AC has no passing test; surfaces diverge | Must fix |
| HIGH | Render pipeline order wrong; scope creep | Must fix |
| MEDIUM (fixable) | Cross-cut convention drift | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00056",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
