# I-00060_S05_CodeReview_Final_prompt

**Work Item**: I-00060 -- Code chat — pin user message on Enter and tighten empty Assistant bubble
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Same restrictions as previous steps. See
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No DB changes in scope.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00060 --json`.
- `ai-dev/active/I-00060/I-00060_Issue_Design.md`
- All implementation step reports: `ai-dev/active/I-00060/reports/I-00060_S0[1-4]_*_report.md`
- All per-agent code review reports: same directory
- All files listed in `files_changed` across S01 and S03

## Output Files

- `ai-dev/active/I-00060/reports/I-00060_S05_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of all I-00060 work.
Per-agent reviews (S02 and S04) covered S01 and S03 individually. Your
job is to catch cross-cutting issues they could not — chiefly:

- The S01 fix and the S03 tests actually correspond. The tests measure
  what S01 changed, not adjacent behaviour. If S01 changed the empty
  bubble's structure but S03 only tests scroll behaviour, AC2 has no
  test coverage and that's a CRITICAL finding.
- The whole package satisfies every acceptance criterion in the design
  doc (AC1..AC5). Walk each AC and find the corresponding test +
  implementation evidence.

Read the design document first to understand the full intended scope.
Read all reports. Then review all changed files holistically.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on changed files → CRITICAL findings.

## Review Checklist

### 1. AC coverage matrix

Build a small mental matrix:

| AC | Implementation evidence | Test evidence |
|----|-------------------------|---------------|
| AC1 (scroll on submit) | line(s) in composer.js | test name |
| AC2 (compact empty bubble) | deletion of `min-height: 50dvh` rule in `dashboard/static/chat.css` | test name |
| AC3 (conditional follow-scroll) | line(s) in composer.js | test name |
| AC4 (reproduction test exists) | n/a | the AC1+AC2 repro tests |
| AC5 (no regressions) | unchanged files | citation + mermaid + ↓Latest tests |

Each row must have BOTH columns populated. A blank cell is a finding:
CRITICAL if it's an AC1/AC2/AC3 gap, HIGH for AC5.

### 2. Cross-cutting consistency

- Tests target the SAME selectors / DOM shape that S01 produces. If S01
  removed a class that S03's test expects, that's CRITICAL.
- The `IntersectionObserver` is used coherently — not duplicated, not
  fighting itself.
- The fix touches `dashboard/static/chat.css` (hand-written), NOT
  `dashboard/static/styles.css` (Tailwind output). Any edit to
  `styles.css` is a HIGH finding — it gets overwritten on rebuild.
- `make css` is a no-op in this project; do not require its output.

### 3. Scope discipline (cross-agent)

The combined diff should be:

- `dashboard/static/chat/composer.js` (S01)
- `dashboard/static/chat.css` (S01, hand-written stylesheet)
- Optional: `dashboard/static/chat/render.js` (S01, only if the live
  browser check exposed an additional contributor)
- `tests/dashboard/browser/test_chat_scroll_i00060.py` (S03)
- Optional: tiny addition to `tests/dashboard/browser/conftest.py` (S03)

Anything outside this list is a scope violation and a CRITICAL finding.
In particular, any edit to `dashboard/static/styles.css` (Tailwind
output) is a HIGH finding — that file is regenerated and the edit will
not survive.

### 4. Architecture compliance

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Confirm:

- No backend / router / template changes outside `dashboard/templates/chat/`.
- No use of `agent-browser` or hardcoded ports anywhere in tests.

### 5. Security (cross-cutting)

- No new `innerHTML =` injections from untrusted input. The renderer
  already runs DOMPurify; verify nothing new bypasses it.
- No new credentials / URLs hardcoded.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
uv run pytest tests/dashboard/browser/ -m browser -v
make lint
```

If unit or browser-lane tests fail → CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Missing AC coverage, scope violation, broken integration | Must fix before merge |
| **HIGH** | Edit to `dashboard/static/styles.css` instead of `chat.css`; failing test in adjacent lane | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00060",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "",
      "suggestion": "",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y browser passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `missing_requirements`: list any AC with no implementation OR no test
  coverage. Each one is automatically CRITICAL.
