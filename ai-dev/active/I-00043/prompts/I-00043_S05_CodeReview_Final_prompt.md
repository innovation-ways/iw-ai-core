# I-00043_S05_CodeReview_Final_prompt

**Work Item**: I-00043 — doc_index_poller crashes with DetachedInstanceError on every poll cycle
**Step**: S05
**Agent**: CodeReview_Final

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
- All implementation step reports: `ai-dev/active/I-00043/reports/I-00043_S0{1,3}_*_report.md`
- All per-agent code review reports: `ai-dev/active/I-00043/reports/I-00043_S0{2,4}_CodeReview_*_report.md`
- All files listed in S01 and S03 reports' `files_changed`

## Output Files

- `ai-dev/active/I-00043/reports/I-00043_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** for I-00043. The per-step
reviews have already happened; your job is to verify the production fix (S01)
and the regression test (S03) compose correctly into a complete fix that
satisfies the design document's acceptance criteria.

Two files were changed: `orch/daemon/doc_index_poller.py` (and possibly
`orch/daemon/doc_job_poller.py`) plus the new test. Despite the small scope, run
the full verification suite to confirm nothing else regressed.

## Review Checklist

### 1. Completeness vs Design Document

- AC1: `DocIndexPoller.poll()` no longer raises DetachedInstanceError. Verify by
  inspecting the new code AND running the test.
- AC2: Regression test exists at the path specified in the design document and
  passes.
- AC3: Adjacent-poller audit completed. Read S01's `notes` field — did it
  contain an explicit verdict for `doc_job_poller.py`? If yes and the verdict
  was acted on (or justified), AC3 is satisfied. If the audit is missing or
  unjustified, this is a CRITICAL finding.
- All design document `File Manifest` entries exist on disk?
- No TODO comments or placeholder implementations in either file?

### 2. Cross-Step Consistency

- The test asserts on the same enabled-projects behaviour the production code
  implements: enabled projects are processed, disabled projects are not.
- The test references the same fixture pattern other daemon unit tests use; no
  bespoke fixture proliferation.
- The S01 fix and the S03 test were authored against the same `Project` model
  and session factory contract — no version skew.

### 3. Integration: end-to-end behaviour

This is the integration check that per-step reviews could not perform:

- Run the new test in isolation:
  ```bash
  uv run pytest tests/unit/daemon/test_doc_index_poller_session_boundary.py -v
  ```
  Must pass.

- Run the entire daemon-related unit test suite:
  ```bash
  uv run pytest tests/unit/daemon/ -v
  ```
  Must pass — confirms no other daemon test regressed because of the change.

- Optional but valuable: search the daemon log for the pre-existing
  `Error in doc index poller` errors. Restart of the live daemon is OPERATOR-only,
  so do NOT do that yourself — but document in your review report that a
  daemon restart is the operator-side verification step for AC1's "no entry
  containing 'Error in doc index poller'" clause.

### 4. Architecture compliance

- Fix is local to the poller method — no new helpers, no refactors, no new
  abstractions.
- Test follows existing daemon-test fixture patterns — no new fixtures unless
  documented.
- No imports were added to either production file (the fix uses only types
  already imported).

### 5. Security and scope

- No hardcoded credentials in either file.
- No expansion of scope beyond the two pollers and the new test file.
- Did either step modify files outside the design document's `File Manifest`?
  Cross-check.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `make test-unit` — must pass with zero failures.
2. `make allure-integration` — must pass.
3. `make lint` — must pass.
4. `make typecheck` — must pass.

If integration tests fail, this is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Test fails; fix is wrong; AC3 audit missing/wrong; integration tests fail; scope violation | Must fix |
| **HIGH** | Cross-step inconsistency; missing enabled-filter coverage in test | Must fix |
| **MEDIUM (fixable)** | Convention deviation; weak docstring | Should fix |
| **MEDIUM (suggestion)** | Better wording, optional defensive check | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00043",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed; lint clean; typecheck clean",
  "missing_requirements": [],
  "notes": "Operator-side AC1 verification (daemon restart, log inspection) NOT performed by this review — operator action."
}
```

`verdict: pass` requires zero CRITICAL, zero HIGH, AND zero MEDIUM (fixable) findings.
`missing_requirements`: list every design-doc AC with no corresponding code; each is automatically CRITICAL.
