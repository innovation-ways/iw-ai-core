# I00106_S07_CodeReview_Final_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed exceptions: testcontainer fixtures, read-only `docker ps`/`docker logs`/`docker inspect`,
and `./ai-core.sh` / `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This work item adds NO migration. Any alembic file in the diff is a CRITICAL scope violation.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00106 --json` for the current step list.
- `ai-dev/active/I-00106/I-00106_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00106/I-00106_Functional.md` -- Human-facing summary.
- All implementation reports: `ai-dev/active/I-00106/reports/I-00106_S0{1,3,5}_*_report.md`.
- All per-agent review reports: `ai-dev/active/I-00106/reports/I-00106_S0{2,4,6}_CodeReview_report.md`.
- All changed files: `orch/daemon/session_reader.py`, `dashboard/routers/items.py`,
  `dashboard/templates/fragments/session_log_popup_content.html`,
  `tests/unit/test_session_reader.py`, `tests/dashboard/test_session_log_modal_ordering.py`.

## Output Files

- `ai-dev/active/I-00106/reports/I-00106_S07_CodeReview_Final_report.md` -- Final review report.

## Context

You are performing the **final cross-agent review** of ALL implementation work for I-00106:
a new turn-grouping helper in `orch/daemon/session_reader.py` (S01), the router + template wiring
that makes the Agent Session Log modal render newest-turn-first (S03), and the reproduction +
regression tests (S05). Per-agent reviews (S02/S04/S06) are done; your job is the cross-cutting
picture they could not see.

Read the design document fully, then all reports, then review the changed files holistically.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading code, run on all changed files. Report only — fix nothing.

```bash
make lint
make format-check
```

`make lint` includes the Jinja2 template check. Any NEW violation in a changed file is a
**CRITICAL** finding. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. End-to-end correctness — the three pieces fit together

Trace the whole path with the actual code in front of you:

- `read_session_content` produces chronological segments (unchanged).
- The S01 helper groups them into turns and reverses turn order, preserving within-turn order.
- `item_session_log` calls the helper and passes `turns` to the template.
- `session_log_popup_content.html` iterates `turns` (outer) then segments (inner) and renders
  each segment with the unchanged per-type markup, a divider between turns.

Confirm the helper NAME and SIGNATURE used by the router exactly match what S01 defined — a
mismatch (wrong name, wrong return shape) is a CRITICAL integration finding even if each step
passed its own review.

### 2. Acceptance criteria — verify every one end-to-end

- **AC1** — newest turn renders first; verify via the reproduction test and by reading the code.
- **AC2** — the named reproduction + regression tests exist and pass.
- **AC3** — within-turn segment order is never reversed.
- **AC4** — in-progress trailing turn surfaces first; `compaction` is a standalone turn; a lone
  `log` segment has its lines reversed.
- **AC5** — empty-state branch still renders; the `is_live` 3-second poll still works.

Any AC with no corresponding code/test is a CRITICAL `missing_requirements` entry.

### 3. Cross-agent consistency

- The router imports the helper from `orch.daemon.session_reader` — no duplicated reversal logic
  in the router or template.
- `orch/` does not import from `dashboard/` (the `log`-segment line reverse is local to
  `session_reader.py`).
- The template's context contract (`turns`) matches what the router passes on **every** path,
  including the error-fallback branch.

### 4. Scope integrity

Run `git diff --stat origin/main...HEAD` (or the worktree base). The diff must touch ONLY:
`orch/daemon/session_reader.py`, `dashboard/routers/items.py`,
`dashboard/templates/fragments/session_log_popup_content.html`,
`tests/unit/test_session_reader.py`, `tests/dashboard/test_session_log_modal_ordering.py`
(plus `ai-dev/active/I-00106/**`). Any file outside `scope.allowed_paths` is a CRITICAL finding.
No migration file may appear.

### 5. Test quality (holistic)

- The reproduction test genuinely fails against pre-fix (chronological) behaviour — reason about
  whether its ordering assertion would pass if the helper were removed. If it would, that is HIGH.
- Tests assert concrete ordering, not shape (the I003 lesson). No regression of existing
  `test_session_reader.py` tests.

### 6. No residual debt

- No `TODO`, no placeholder, no commented-out code, no dead `segments` context key left behind.
- No scroll-preservation JS was added (out of scope per design).

## Test Verification (NON-NEGOTIABLE)

Run **targeted** tests only. The full `make test-unit` / `make test-frontend` /
`make allure-integration` suites are owned by the S13 / S14 / S15 QV gates that run immediately
after this step — re-running them here duplicates that work and risks a step timeout (the
integration gate alone is budgeted at 1800 s for S15, and this step has no extended timeout).
Run the new test files plus the existing regression coverage of the route:

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -30
uv run pytest tests/dashboard/test_session_log_modal_ordering.py -v 2>&1 | tail -30
uv run pytest tests/dashboard/test_items_session_log.py -v 2>&1 | tail -30
```

Any failure in these targeted files is a CRITICAL finding. Report results accurately.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, missing requirement, scope violation, security issue |
| **HIGH** | Significant bug, integration failure, architectural violation |
| **MEDIUM (fixable)** | Code-quality issue, missed edge case, convention violation |
| **MEDIUM (suggestion)** | Optional improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00106",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL, zero HIGH, and zero MEDIUM (fixable) findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
- `missing_requirements`: every design requirement with no implementation — each is CRITICAL.
