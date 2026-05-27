# I-00115 S05 Final Code Review Report

## Verdict
**FAIL**

## What was reviewed
- Design doc: `ai-dev/active/I-00115/I-00115_Issue_Design.md` (AC1/AC2/AC3, TDD section)
- Prior reports: `S01`, `S02`, `S03`, `S04`
- Changed files:
  - `dashboard/templates/components/scope_amend_modal.html`
  - `tests/dashboard/test_scope_amend_modal_i00115.py`

## Scope checks
- `git status -s -- 'dashboard/**' 'tests/**' 'orch/**'` shows only expected changes:
  - `M dashboard/templates/components/scope_amend_modal.html`
  - `?? tests/dashboard/test_scope_amend_modal_i00115.py`
- No `orch/**`, no `dashboard/routers/actions.py`, no `docs/**` edits detected.

## Acceptance criteria review
- **AC1 (all dismissal paths teardown both modal+overlay):** PASS
  - Submit success: form has `hx-on::after-request` gated by `event.detail.successful`, removing both IDs.
  - × / Cancel: both call shared dismiss helper.
  - ESC + backdrop click: listeners present; backdrop guarded with `event.target === overlay`.
- **AC2 (regression tests exist):** PASS
  - `tests/dashboard/test_scope_amend_modal_i00115.py` exists with 5 tests.
- **AC3 (submit success still queues restart + toast path intact):** PASS by code inspection/scope discipline
  - `dashboard/routers/actions.py` unchanged.
  - No `stopPropagation()` introduced in modal code; page-level toast handler remains reachable.

## Cross-agent consistency
- S03 assertions match S01 implementation choice:
  - form-level `hx-on::after-request`
  - script/helper-based ESC/backdrop/X/Cancel handling.

## Listener-leak hygiene
- PASS: `cleanupListeners()` removes both `keydown` and overlay `click` listeners; called on dismiss and exposed for submit-success cleanup.

## Required gates run
- `make lint` ✅ PASS
- `make format-check` ✅ PASS

## Required test verification
- `make test-unit` ❌ **FAIL** (CRITICAL)
  - Error during collection: `ModuleNotFoundError: No module named 'anthropic'`
  - Failing module: `tests/unit/test_llm_judge_script.py`
- `uv run pytest tests/dashboard/ tests/integration/test_scope_amend_endpoints.py -v` ✅ PASS
  - **1232 passed, 15 skipped, 27 deselected, 1 xfailed, 0 failed**

## Findings
1. **CRITICAL** — Mandatory final-review test gate failed.
   - `make test-unit` is red due to missing `anthropic` dependency in unit test collection.
   - Per step contract, S05 cannot pass while required test gate is failing.

## Review result contract
```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00115",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "title": "Required final-review test gate failed",
      "detail": "make test-unit failed during collection: ModuleNotFoundError: No module named 'anthropic' in tests/unit/test_llm_judge_script.py"
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": false,
  "test_summary": "make test-unit failed (collection error); dashboard+integration targeted suite: 1232 passed, 0 failed",
  "missing_requirements": [
    "Non-negotiable final-review requirement unmet: make test-unit must pass"
  ],
  "notes": "Implementation scope and acceptance criteria checks pass; step fails solely due to required test gate failure."
}
```
