# I-00043_S02_CodeReview_Backend_prompt

**Work Item**: I-00043 — doc_index_poller crashes with DetachedInstanceError on every poll cycle
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

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
- `ai-dev/active/I-00043/reports/I-00043_S01_Backend_report.md` — S01 step report (must include doc_job_poller audit notes)
- `orch/daemon/doc_index_poller.py` — Modified file
- `orch/daemon/doc_job_poller.py` — Either modified or proven correct
- `orch/CLAUDE.md` — Project conventions
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00043/reports/I-00043_S02_CodeReview_Backend_report.md` — Review report

## Context

S01 fixed the session-boundary bug in `DocIndexPoller.poll()` and audited
`doc_job_poller.py` for the same pattern. Your job is to verify both halves of the
work are correct.

## Review Checklist

### 1. Correctness of the `doc_index_poller.py` fix

- Is `project.id` (or any other ORM attribute) accessed only **inside** the
  `with self._session_factory() as db:` block?
- Does the new code produce a list of plain Python strings (not ORM instances)
  before exiting the `with` block?
- Is the for-loop now iterating plain `project_id` strings, not ORM instances?
- Is the SQLAlchemy comparison `Project.enabled == True` retained with its `# noqa: E712` comment?

If any of these is wrong, this is a CRITICAL finding (the fix doesn't actually
fix the bug).

### 2. Adjacent-poller audit (`doc_job_poller.py`)

S01's report MUST contain an explicit audit note. Two cases:

- **`doc_job_poller.py` is in S01's `files_changed`**: read the diff. Verify the
  same fix pattern was applied. Verify no other unrelated changes leaked in.
- **`doc_job_poller.py` is NOT in S01's `files_changed`**: read the file
  yourself and confirm S01's claim that it's already correct. Specifically: any
  `with self._session_factory() as db:` block must have all subsequent
  attribute access **inside** the block, OR must extract plain Python values
  before the block closes.

If S01's report is missing the audit, this is a HIGH finding (incomplete
deliverable).

If S01's audit conclusion is wrong (claims correct when buggy, or vice versa),
this is a CRITICAL finding.

### 3. Scope discipline

- Did S01 modify ONLY the two poller files? Anything outside is a HIGH finding
  (scope drift).
- Were any new helpers, methods, or imports added that aren't strictly necessary?
  This is a MEDIUM (suggestion) finding — the design doc explicitly forbids
  refactoring beyond the local fix.

### 4. Code quality

- Is the new code clear without comments? (The fix is so small that it should be
  self-evident from the structure. A comment is acceptable but not required.)
- Are imports unchanged? (The fix should not need any new imports.)
- Type annotations match PEP 604?

### 5. Lifecycle correctness review

Mentally trace through the new code:

```
1. Enter with-block, open session.
2. Query for project IDs.
3. Materialise list of plain strings.
4. Exit with-block, session closes, instances expire.
5. Loop iterates plain strings — no expired-attribute access possible.
6. Each iteration calls _process_project(project_id), which opens its own session.
```

If any step in this trace can fail with a session-related error in the new code,
this is a CRITICAL finding.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `make lint` — must pass.
2. `make typecheck` — must pass.
3. `make test-unit` — must pass with zero failures.

If any fail, this is a finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Fix is wrong (bug still triggers); audit conclusion is wrong; tests fail | Must fix |
| **HIGH** | Audit missing from S01 report; scope drift; unrelated changes | Must fix |
| **MEDIUM (fixable)** | Unnecessary refactor; convention deviation | Should fix |
| **MEDIUM (suggestion)** | Better naming, minor style improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00043",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "code_quality|architecture|conventions|testing",
      "file": "orch/daemon/doc_index_poller.py",
      "line": 50,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint clean; typecheck clean; X unit passed, 0 failed",
  "notes": "doc_job_poller.py audit verdict: <agree | disagree>; <details>"
}
```

`verdict: pass` requires zero CRITICAL, zero HIGH, AND zero MEDIUM (fixable) findings.
