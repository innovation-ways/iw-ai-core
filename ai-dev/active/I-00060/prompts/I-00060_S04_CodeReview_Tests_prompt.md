# I-00060_S04_CodeReview_Tests_prompt

**Work Item**: I-00060 -- Code chat — pin user message on Enter and tighten empty Assistant bubble
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Same restrictions as previous steps. See
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No DB changes in scope.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00060 --json`.
- `ai-dev/active/I-00060/I-00060_Issue_Design.md`
- `ai-dev/active/I-00060/reports/I-00060_S03_Tests_report.md`
- All files listed in S03's `files_changed`
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00060/reports/I-00060_S04_CodeReview_report.md`

## Context

You are reviewing the new tests written in S03. The bar is HIGH because
I002 shipped tests that passed without the bug being fixed (see the
"Semantic Correctness" lesson in `tests/CLAUDE.md` and the S03 prompt).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on changed test files → CRITICAL findings.

## Review Checklist

### 1. Semantic Correctness (PRIMARY)

This is the single biggest reason to fail S03 if it's wrong. Every test
must verify a specific, observable consequence of the fix — not just
that "something happened".

For AC1 reproduction:
- ✅ Test asserts the user bubble's bounding rect is INSIDE the messages
  container's viewport after submit.
- ❌ Test only asserts `chat-send` was clicked, or that the bubble
  exists in the DOM. (DOM existence is independent of scroll position.)

For AC2 reproduction:
- ✅ Test measures `getBoundingClientRect().height` of the empty
  assistant article BEFORE the first token streams in, asserts ≤ 48.
- ❌ Test only asserts the article exists, or that some CSS class is
  present.

If the assertions could pass against pre-S01 code, that's a CRITICAL
finding.

### 2. RED→GREEN evidence

The S03 report must include explicit evidence that the new reproduction
tests FAIL when S01 is reverted. Read the report. If the evidence is
missing, hand-wavy, or the failing output doesn't actually match the bug
— CRITICAL finding.

To verify yourself if needed: stash S01's diff, re-run the new tests,
confirm RED on AC1 and AC2 reproduction tests; restore S01, confirm
GREEN.

### 3. Regression coverage

- AC3 (conditional follow-scroll): a test exists and asserts the
  container does NOT auto-scroll when the user has scrolled away.
- Citations / mermaid (AC5): basic regression check exists. A skipped /
  empty test is NOT acceptable.
- Phase-strip growing the bubble is allowed: a positive test confirms
  the bubble grows once phase text appears.

### 4. Test isolation / harness hygiene

- No `agent-browser`, no `chromium.launch()`, no `npx playwright install`
  — `playwright-cli` only.
- No hardcoded ports / credentials. Reads `$IW_BROWSER_BASE_URL`,
  `$IW_BROWSER_E2E_USER`, `$IW_BROWSER_E2E_PASSWORD` from env.
- Cleanup: each test calls `playwright-cli kill-all` (or uses a fixture
  that does so) to avoid session leaks.
- Tests are deterministic — no `time.sleep()` longer than necessary, no
  flaky text-match heuristics. Layout assertions use bounding rects and
  numeric tolerances, not pixel-perfect equality.

### 5. Scope discipline

The diff should be limited to test files under
`tests/dashboard/browser/` and possibly a tiny addition to
`tests/dashboard/browser/conftest.py`. No production code changes —
flag any as CRITICAL scope violation.

## Test Verification (NON-NEGOTIABLE)

1. Run the browser-test lane:
   `uv run pytest tests/dashboard/browser/ -m browser -v`. The new
   I-00060 tests must pass, and the rest of the browser lane must
   remain green.
2. Run `make test-unit` to confirm no regressions in the broader suite.
3. Report results.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Tests would pass on broken code; missing RED→GREEN evidence; scope violation | Must fix before merge |
| **HIGH** | Missing AC coverage; flaky / non-deterministic test | Must fix before merge |
| **MEDIUM (fixable)** | Convention drift, weak assertion that could be tightened | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00060",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|conventions|architecture",
      "file": "tests/dashboard/browser/test_chat_scroll_i00060.py",
      "line": 42,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
