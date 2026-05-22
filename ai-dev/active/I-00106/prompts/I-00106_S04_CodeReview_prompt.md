# I00106_S04_CodeReview_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed exceptions: testcontainer fixtures, read-only `docker ps`/`docker logs`/`docker inspect`,
and `./ai-core.sh` / `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This work item adds NO migration. Flag any alembic file as a scope violation.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00106 --json` for the current step list.
- `ai-dev/active/I-00106/I-00106_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00106/reports/I-00106_S03_Frontend_report.md` -- S03 implementation report.
- `ai-dev/active/I-00106/reports/I-00106_S01_Backend_report.md` -- S01 report (helper name).
- `dashboard/routers/items.py` -- Router file changed by S03.
- `dashboard/templates/fragments/session_log_popup_content.html` -- Template changed by S03.

## Output Files

- `ai-dev/active/I-00106/reports/I-00106_S04_CodeReview_report.md` -- Review report.

## Context

You are reviewing the S03 frontend work for **I-00106**: the `item_session_log` router handler
and the `session_log_popup_content.html` fragment were changed so the Agent Session Log modal
renders the newest agent turn at the top.

Read the design document first — especially **"The router + template change (S03 contract)"** and
Acceptance Criteria **AC1** (newest turn renders first) and **AC5** (empty-state and live-poll not
regressed). Read the S03 report, then review both changed files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading code, run these on the changed files. Report only — fix nothing.

```bash
make lint
make format-check
```

`make lint` includes the Jinja2 template check (`scripts/check_templates.py`). Any NEW violation
in a changed file is a **CRITICAL** finding (`"category": "conventions"`, with `file`, `line`, and
the exact rule code/message). If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Router correctness (`dashboard/routers/items.py`)

- `item_session_log` applies the S01 helper to the segment list and passes the result to the
  template under the context key **`turns`** (the `segments` key should be gone).
- The **error-fallback** branch (the `except` building a single "Failed to read session log."
  segment) also produces a `turns`-shaped value — the template must never receive a bare
  `segments` list or a missing `turns`. A path that still passes `segments` is a HIGH finding.
- The empty case yields `turns == []` so the template empty-state branch still fires.
- The helper is imported from `orch.daemon.session_reader`. The router does NOT re-implement the
  reversal inline (routers are thin — `dashboard/CLAUDE.md`).
- `read_session_content` and `session_reader.py` are NOT modified by S03.

### 2. Template correctness (`session_log_popup_content.html`)

- Guard is `{% if turns %}` with the original `{% else %}` empty-state branch intact.
- Two-level iteration: outer `{% for turn in turns %}`, inner `{% for seg in turn %}`.
- The per-segment markup for every type (`compaction`, `assistant`, `thinking`, `tool_call`,
  `tool_result`, `error`, `log`) is reused **verbatim** — the bug fix must not silently restyle
  segments.
- A divider renders **between** turns (every turn except the first) using only Tailwind utility
  classes already present in the file. No new CSS class, no dependency on a `make css` rebuild.
- The header block and the `is_live` htmx polling wrapper (`hx-trigger="every 3s"`) are preserved.
- The fragment does NOT extend `base.html`.

### 3. Behaviour preserved (AC5)

- Confirm the empty-state copy still renders when there is no content.
- Confirm the live poll still targets the modal body and refreshes every 3 s.
- No scroll-preservation JS was added (out of scope per the design doc).
- `item_steps_table.html` (the trigger button + modal shell) is unchanged.

### 4. Scope discipline

- The ONLY files changed must be `dashboard/routers/items.py` and
  `dashboard/templates/fragments/session_log_popup_content.html`. Any other file — including
  test files (S05's job) — is a scope violation (CRITICAL).

### 5. Architecture & conventions

- Routers stay thin; reordering logic lives in the `orch/` helper.
- `dashboard/CLAUDE.md` rules respected (fragments, htmx, clipboard helper if relevant — not
  relevant here).

## Test Verification (NON-NEGOTIABLE)

Run the project unit suite for the touched module plus the relevant dashboard tests:

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -20
uv run pytest tests/dashboard/ -k "session_log or item" -v 2>&1 | tail -30
```

Report results accurately. Note that S05's dedicated tests do not exist yet at this point.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, security issue |
| **HIGH** | Significant bug, missing requirement, architectural violation |
| **MEDIUM (fixable)** | Code-quality issue, missed edge case, convention violation |
| **MEDIUM (suggestion)** | Optional improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00106",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 0,
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

- `verdict`: `pass` only if zero CRITICAL, zero HIGH, and zero MEDIUM (fixable) findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
