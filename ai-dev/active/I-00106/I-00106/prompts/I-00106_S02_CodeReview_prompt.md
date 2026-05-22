# I00106_S02_CodeReview_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

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
- `ai-dev/active/I-00106/reports/I-00106_S01_Backend_report.md` -- S01 implementation report.
- `orch/daemon/session_reader.py` -- The file changed by S01.

## Output Files

- `ai-dev/active/I-00106/reports/I-00106_S02_CodeReview_report.md` -- Review report.

## Context

You are reviewing the S01 backend work for **I-00106**: a new pure helper added to
`orch/daemon/session_reader.py` that groups the flat chronological agent-session segment list
into *turns* and returns them newest-first.

Read the design document first — especially the section **"The turn-grouping helper (S01 contract)"**
and Acceptance Criteria **AC3** (within-turn order preserved) and **AC4** (in-progress trailing
turn, compaction, log segment). Read the S01 report to see what was done, then review the code.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading code, run these on `orch/daemon/session_reader.py`. Report only — fix nothing.

```bash
make lint
make format-check
```

Any NEW violation in the changed file is a **CRITICAL** finding (`"category": "conventions"`,
with `file`, `line`, and the exact rule code/message). If a command is unavailable, STOP and
raise a blocker.

## Review Checklist

### 1. Contract correctness — the turn-grouping helper

Verify the new helper against the S01 contract in the design doc:

- **Turn boundary.** A turn terminates at an `assistant` segment **not** immediately followed by
  another `assistant`, or at an `error` segment. Confirm consecutive `assistant` segments stay in
  ONE turn (not split). Confirm an `error` always terminates its turn.
- **Newest-first.** The list of turns is reversed so the newest turn is at index 0; verify the
  reversal is on the list of turns, NOT on the segments within a turn.
- **Within-turn order preserved.** Segments inside a turn keep their chronological order
  (thinking → tool call → tool result → assistant reply). This is AC3 — a violation is CRITICAL.
- **In-progress trailing turn.** Segments accumulated with no terminating `assistant`/`error`
  must form a final turn that ends up FIRST after reversal.
- **`compaction`.** Emitted as its own single-segment turn, with the in-progress turn flushed
  before it so its chronological position is correct.
- **`log` segment.** Emitted as its own turn with its `text` **lines reversed**. Confirm the
  line-reverse helper is local to `session_reader.py` and does NOT import from `dashboard/`.
- **Purity.** The function must not mutate the input list or its dicts; the rewritten `log`
  segment must be a new dict. A mutation of the input is a HIGH finding.
- **Empty input.** `[]` → `[]`.

Reason through at least the multi-turn case and the consecutive-`assistant` case by hand against
the actual code — do not just trust the docstring.

### 2. Scope discipline

- The ONLY file changed must be `orch/daemon/session_reader.py`. Any other file (router, template,
  tests, migration) is a scope violation — CRITICAL. Note: S01 must NOT have edited
  `tests/unit/test_session_reader.py` (that is S05's deliverable).
- `read_session_content` and the `_render_*` / `_process_*` parsing functions must be **unchanged** —
  they must still return chronological segments. Any change there is a HIGH finding unless trivially
  justified.
- No router wiring in this step — `item_session_log` is S03's job.

### 3. Architecture & conventions

- `orch/` must not import from `dashboard/` (`orch/CLAUDE.md`).
- Naming, type hints (`list[dict[str, Any]]`), and docstring style match the rest of the module.
- The helper is pure and side-effect free.

### 4. TDD RED evidence

This is a Backend step, but the design doc delegates the reproduction/regression tests to S05.
Confirm the S01 report's `tdd_red_evidence` uses the `"n/a — …"` form with that justification.
S01 adding committed test code to `tests/unit/test_session_reader.py` would be a scope violation.

## Test Verification (NON-NEGOTIABLE)

Run the module's existing tests to confirm no regression:

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -30
```

Report the result accurately in the contract.

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
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00106",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "orch/daemon/session_reader.py",
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
