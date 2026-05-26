# I-00115_S05_CodeReview_Final_prompt

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This item touches NO migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00115 --json`
- `ai-dev/active/I-00115/I-00115_Issue_Design.md` — design document (READ FIRST)
- All implementation step reports: `ai-dev/active/I-00115/reports/I-00115_S01_Frontend_report.md`, `..._S03_Tests_report.md`
- All per-agent code review reports: `..._S02_CodeReview_report.md`, `..._S04_CodeReview_report.md`
- All files in `files_changed`: `dashboard/templates/components/scope_amend_modal.html`, `tests/dashboard/test_scope_amend_modal_i00115.py`

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_S05_CodeReview_Final_report.md` — final review report

## Context

You are performing the **final cross-step review** of all work for I-00115. Two implementation steps (S01 template fix, S03 tests) and two per-agent reviews have run. Your job is to catch what they couldn't.

## Read the Design Document FIRST

Read the design document **before** running the lint gate. Specifically:

- `## Acceptance Criteria` — three ACs (AC1, AC2, AC3). Each is a mandatory check.
- `## TDD Approach` — names `tests/dashboard/test_scope_amend_modal_i00115.py` as the regression test file. Cross-check it appears in S03's `files_changed`. If missing, CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Both must report zero violations on the changed files. CRITICAL if either fails.

## Scope Diff — Directional (MANDATORY)

```bash
git diff main...HEAD --name-only -- 'dashboard/**' 'tests/**' 'orch/**'
git status -s -- 'dashboard/**' 'tests/**' 'orch/**'
```

Expected names: only `dashboard/templates/components/scope_amend_modal.html` and `tests/dashboard/test_scope_amend_modal_i00115.py` (plus implicit `ai-dev/active/I-00115/**`).

Anything else is scope creep — CRITICAL. Especially watch for:
- `dashboard/routers/actions.py` — must NOT change (the 204 + toast response is correct as-is).
- Any alembic file.
- `orch/**` — pure frontend fix, no orch changes.

Use the **directional** form (`main...HEAD`), not symmetric `git diff main`. See the rule in `ai-dev/templates/CodeReview_Final_Prompt_Template.md`.

## Review Checklist

### 1. Completeness vs Design Document

**AC1 — All dismissal paths fully tear down the modal**: read the post-S01 template and verify all five paths (submit, ×, Cancel, ESC, backdrop) remove BOTH `#scope-amend-modal` and `#scope-amend-overlay`. The submit path's cleanup must fire only on 2xx (not on 4xx/5xx). If any path is missing, CRITICAL.

**AC2 — Regression test exists**: `tests/dashboard/test_scope_amend_modal_i00115.py` must exist with 5 tests, all green. Verify by reading and running.

**AC3 — Submit success still queues the step for restart**: existing `tests/integration/test_scope_amend_endpoints.py` must still pass. Confirm S01 did NOT touch `dashboard/routers/actions.py`.

### 2. Cross-Agent Consistency

- S03's tests must be testing the actual idiom S01 chose (whether `hx-on::after-request` or `<script>` block). If S03's assertions are looking for one idiom and S01 implemented the other, the tests will pass but won't actually exercise the intent — HIGH.

### 3. Listener-leak hygiene

If S01 added a document-level ESC listener, verify it is detached on dismissal. Open the template and trace: does the cleanup function `removeEventListener` the same handler it `addEventListener`'d? If not, HIGH (listener leak across reopens).

### 4. Toast still surfaces on submit success

The page-level `htmx:afterRequest` handler at `dashboard/templates/pages/project/item_detail.html:159-172` reads `HX-Trigger: showToast`. Confirm S01's modal-level cleanup does NOT call `event.stopPropagation()` in a way that prevents the page-level handler from running. If it does, HIGH (silent toast loss).

### 5. CLAUDE.md conventions

- Dashboard CSS prebuilt — no new Tailwind classes without a plain-CSS fallback append (per I-00067 rule).
- No `navigator.clipboard.writeText` calls.
- No `str.format`-style Jinja2 `format` filter calls (per I-00075).
- htmx + Jinja2 + plain JS, no framework.

### 6. Security (cross-cutting)

- No hardcoded URLs/ports/credentials.
- No new XSS surface: the modal renders user-controlled `step.step_id` and `item.id` via Jinja2 (auto-escapes); confirm S01 did NOT introduce `{{ ... | safe }}` anywhere new.
- No new sub-resource includes (no new `<script src="">`).

### 7. Documentation drift

The item's prose-level docs are inside the design doc and functional doc — no `docs/` updates expected. Confirm no stray edits to `docs/**`.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + dashboard + integration suite** (this is the final review's job, unlike per-agent reviews):

```bash
make test-unit
uv run pytest tests/dashboard/ tests/integration/test_scope_amend_endpoints.py -v
```

If either fails, CRITICAL. The QV gates S11/S12 will re-run as well but you should not pass `verdict: pass` while these are red.

## Severity Levels

| Severity | Action Required |
|----------|-----------------|
| CRITICAL | Must fix before merge |
| HIGH | Must fix before merge |
| MEDIUM (fixable) | Should fix in fix cycle |
| MEDIUM (suggestion) | Optional |
| LOW | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00115",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "N unit passed, M integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
