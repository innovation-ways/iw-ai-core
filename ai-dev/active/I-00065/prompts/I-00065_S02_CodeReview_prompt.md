# I-00065_S02_CodeReview_prompt

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. Allowed exceptions:
testcontainers from pytest fixtures, read-only `docker ps/inspect/logs`,
and `./ai-core.sh` / `make` invocations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does not involve migrations. Do not run any state-changing
alembic command. Read-only `alembic history / current / show` is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00065 --json` (canonical).
- `ai-dev/active/I-00065/I-00065_Issue_Design.md` -- Design document
- `ai-dev/active/I-00065/reports/I-00065_S01_Frontend_report.md` -- S01 implementation report
- All files listed in S01's `files_changed`:
  - `dashboard/templates/chat/panel.html`
  - `dashboard/static/chat/panel.js`

## Output Files

- `ai-dev/active/I-00065/reports/I-00065_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S01 by frontend-impl for **I-00065**.

Read the design document to understand both bugs and the agreed fix shape, then the S01 report to understand what was actually changed, then review the diffs.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format
```

If either reports NEW violations in the changed files, classify each one as a **CRITICAL** finding with `category: "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Architecture Compliance

- The fix touches only the dashboard frontend layer (template + plain JS). No backend, no API, no DB.
- The CSS edit only adds one selector clause to the existing `[data-collapsed="true"]` rule — no new Tailwind utility classes (so `make css` is not needed).
- The JS edit only adds a guard at the top of `showEmptyState`. No new function, no new module.

### 2. Code Quality — bug-specific checks

**Bug 1 (panel.html)**:
- Confirm the new clause is `#chat-panel[data-collapsed="true"] #chat-new-btn` (exact ID, exact data-attribute selector).
- Confirm it is grouped logically with the other header-button hide rules (next to `#chat-collapse-btn`).
- Confirm no unrelated markup changed.

**Bug 2 (panel.js)**:
- Confirm `showEmptyState` removes any pre-existing `#chat-empty-state` BEFORE inserting the new one.
- Confirm the lookup uses `document.getElementById('chat-empty-state')` (or an equivalent `querySelector('#chat-empty-state')`) — NOT `messages.getElementById` (which doesn't exist).
- Confirm the function still uses `var` (not `let`/`const`), no arrow functions in `function`-named slots, and trailing semicolons — matching the rest of `panel.js`.
- Confirm the empty-state copy and class names are unchanged.
- Confirm no duplicate `id="chat-empty-state"` can exist after any number of "+ New" clicks.

### 3. Project Conventions

- Read `CLAUDE.md` and `dashboard/CLAUDE.md` for project-specific architecture rules.
- `dashboard/static/**/*.js` is plain JS — `make lint` runs `node --check` on it, so a syntax error MUST surface there. Confirm `make lint` passes locally.
- No file outside the manifest's `scope.allowed_paths` should have been touched.

### 4. Security

No security surface here (markup + DOM manipulation in user's own browser). Confirm no inline `innerHTML` is built from user input — the existing `innerHTML` only contains hard-coded literals.

### 5. Testing

- S01 is not the test step; the test step is S03. Do NOT mark S01 as failing solely because tests are missing — that is S03's responsibility.
- Confirm the existing dashboard tests (`make test-frontend`) still pass.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-frontend`.
2. Run `make test-unit`.
3. Report results in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00065",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
