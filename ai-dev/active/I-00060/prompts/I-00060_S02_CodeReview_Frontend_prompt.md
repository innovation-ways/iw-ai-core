# I-00060_S02_CodeReview_Frontend_prompt

**Work Item**: I-00060 -- Code chat — pin user message on Enter and tighten empty Assistant bubble
**Step Being Reviewed**: S01 (Frontend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Same restrictions as the implementation step. See
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No DB changes are in scope. Any alembic activity is a CRITICAL finding.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00060 --json`.
- `ai-dev/active/I-00060/I-00060_Issue_Design.md`
- `ai-dev/active/I-00060/reports/I-00060_S01_Frontend_report.md`
- All files listed in S01's `files_changed` (expected: `dashboard/static/chat/composer.js`, `dashboard/static/chat.css`; optionally `dashboard/static/chat/render.js` if a renderer-side contributor was confirmed)

## Output Files

- `ai-dev/active/I-00060/reports/I-00060_S02_CodeReview_report.md`

## Context

You are reviewing the S01 fix for I-00060. The two acceptance criteria
are:

- **AC1**: submit scrolls so the user's just-typed bubble is in view.
- **AC2**: empty Assistant bubble is ≤ 48px tall before any tokens.
- **AC3**: stream follow-scroll only when user is already at the bottom.

Read the design doc first to understand intent, then read the S01 report
and all changed files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the files in S01's `files_changed`:

```bash
make lint
make format
```

If either reports NEW violations not present on `main`, classify each as
a **CRITICAL** finding with `"category": "conventions"`.

If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. AC coverage

- AC1: confirm `scrollToBottom()` is called on submit after both
  `appendUserBubble` and `appendAssistantBubble`. A single call placed
  after both is acceptable.
- AC2: confirm the empty Assistant bubble actually shrinks. The expected
  change is a deletion of the rule
  `#chat-messages > article[data-role="assistant"]:last-child { min-height: 50dvh; }`
  at `dashboard/static/chat.css:3`. Run the browser smoke yourself if
  practical (`playwright-cli` against the isolated stack), or at
  minimum trace the change to confirm the offending rule is gone.
  Reject if the change adds a fixed height instead of letting the
  bubble size to its content, or if it edits `dashboard/static/styles.css`
  (Tailwind output) instead of `dashboard/static/chat.css`.
- AC3: confirm the stream follow-scroll is **conditional** on the user
  being at the bottom. The simplest correct approach reuses the existing
  `IntersectionObserver` for `#chat-scroll-anchor`. Reject any
  implementation that yanks scroll regardless of user position — that's
  worse than the original bug.

### 2. Scope discipline

- The diff MUST be limited to `dashboard/static/chat/composer.js`,
  `dashboard/static/chat.css`, and optionally `dashboard/static/chat/render.js`.
  Anything else (routers, templates outside `chat/`, Python,
  `dashboard/static/styles.css`) is OUT OF SCOPE — flag as CRITICAL.
- Reject refactors of unrelated code (citation popovers, mermaid
  rendering, sources panel rebuilds).

### 3. Code quality

- The new comment(s) explain WHY, not WHAT. A single short comment near
  the new `scrollToBottom()` call is appropriate; longer comments or
  comments on every line are findings.
- The `IntersectionObserver` is not duplicated. The closure variable
  approach (read once, update via observer callback) is preferred over
  spawning a new observer.
- No new globals leak onto `window` unless they were already there.

### 4. Project conventions

- The fix edits `dashboard/static/chat.css` (hand-written) NOT
  `dashboard/static/styles.css` (Tailwind output). If S01 edited
  `styles.css`, that's a HIGH finding — Tailwind output is regenerated
  and the edit will not survive a future build.
- `playwright-cli` only — no `agent-browser`, no `npx playwright install`.

### 5. No regressions

- The "↓ Latest" floating button still appears when the user scrolls up.
- Sources panel, citations, mermaid: structurally untouched.
- The existing `scrollToBottom()` smooth-scroll on the floating-button
  click handler still works.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make lint
```

Both must pass. Report results in the contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks AC1/AC2/AC3, scope violation, security issue | Must fix before merge |
| **HIGH** | Significant bug, missing requirement | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00060",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.js",
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

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
