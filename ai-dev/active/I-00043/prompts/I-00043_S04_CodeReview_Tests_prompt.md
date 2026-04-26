# I-00043_S04_CodeReview_Tests_prompt

**Work Item**: I-00043 — doc_index_poller crashes with DetachedInstanceError on every poll cycle
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp`. Read-only inspection is fine.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00043/I-00043_Issue_Design.md` — Design document
- `ai-dev/active/I-00043/reports/I-00043_S03_Tests_report.md` — S03 step report
- `tests/unit/daemon/test_doc_index_poller_session_boundary.py` — The new test file
- `tests/CLAUDE.md` — Test conventions
- `tests/integration/conftest.py` — Testcontainer fixture
- `orch/daemon/doc_index_poller.py` — Source under test (post-fix)

## Output Files

- `ai-dev/active/I-00043/reports/I-00043_S04_CodeReview_Tests_report.md` — Review report

## Context

S03 wrote the regression test. Your job is to verify the test:

1. Uses a **real** session, not a mock — without this, the test would have
   passed against the bug.
2. Asserts **specific values**, not shape — without this, it would pass against
   wrong-but-non-empty results.
3. Is **falsifiable** — reverting the S01 fix must make the test fail with
   DetachedInstanceError.

## Review Checklist

### 1. Real session, not mocked (CRITICAL)

The most important check. Read the test and confirm:

- The `session_factory` passed to `DocIndexPoller` is backed by a real
  testcontainer-driven engine, NOT a `MagicMock(spec=Session)` or any other mock.
- `Project` rows are seeded via real INSERTs (or via the existing testcontainer
  seed helpers), NOT via mocked query results.
- `_process_project` is the only method replaced with a recorder; the session
  itself is real.

If the test uses a mocked session, it would have passed against the pre-fix bug
(since mocked attribute access does not raise DetachedInstanceError). This is a
CRITICAL finding — the test fails its primary purpose.

### 2. Semantic correctness (CRITICAL)

The recorder list must be checked for **specific project IDs**:

- ✓ `assert sorted(seen) == sorted(["project_a", "project_b"])`
- ✓ `assert "project_disabled" not in seen` (or equivalent — verifies the enabled filter)
- ✗ `assert seen` (just non-empty — CRITICAL)
- ✗ `assert len(seen) == 2` (count only — CRITICAL; would pass with wrong IDs)

If the test does not check the specific seeded project IDs, this is a CRITICAL
finding.

### 3. Falsifiability (HIGH)

Without actually reverting the fix, mentally trace whether the test would fail
on pre-fix code:

- Pre-fix `poll()` accesses `project.id` outside the session.
- The test calls `poller.poll()`.
- Reading `project.id` on a detached instance raises DetachedInstanceError.
- The exception propagates out of `poll()`.
- pytest reports the test as ERRORED (or FAILED) with that exception.

If you cannot follow this trace through the test as written, the test is
not falsifiable and this is a HIGH finding.

If the test wraps `poller.poll()` in a try/except that swallows
DetachedInstanceError, this is a CRITICAL finding — it defeats the test.

### 4. Enabled-filter coverage

The design doc requires the test to seed at least one disabled project and
verify it is NOT processed. If the test seeds only enabled projects, the
enabled-filter assertion is missing — this is a HIGH finding.

### 5. Placement and naming

- File location: `tests/unit/daemon/test_doc_index_poller_session_boundary.py`?
  (Per the design doc and project convention.)
- Test function name follows `test_<scenario>_<outcome>` style?
- Single test function per scenario, no class-based grouping unless the
  surrounding directory uses that style?

### 6. Code quality

- Imports at top of file?
- PEP 604 type hints?
- No leftover scaffolding (commented-out code, debug prints, TODO comments)?
- Test docstring explains what the test proves and why a mocked session would
  not suffice?

### 7. Scope

- Test file contains only the session-boundary regression for `DocIndexPoller`?
- No tests for unrelated functionality (e.g., `_mark_stalled_jobs`, the doc
  generation poller, etc.) — those are out-of-scope drift.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `uv run pytest tests/unit/daemon/test_doc_index_poller_session_boundary.py -v` —
   must pass.
2. `make test-unit` — must pass with zero failures.
3. `make lint` — must pass.
4. `make typecheck` — must pass.

If any fail, this is a finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Mocked session; shape-only assertions; try/except swallows the error; tests fail | Must fix |
| **HIGH** | Test isn't falsifiable; enabled-filter coverage missing; misplaced; unrelated tests added | Must fix |
| **MEDIUM (fixable)** | Convention deviation; weak docstring | Should fix |
| **MEDIUM (suggestion)** | Better naming, additional defensive check | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00043",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|conventions|architecture|code_quality",
      "file": "tests/unit/daemon/test_doc_index_poller_session_boundary.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1 unit test passed; X unit passed; lint clean; typecheck clean",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL, zero HIGH, AND zero MEDIUM (fixable) findings.
