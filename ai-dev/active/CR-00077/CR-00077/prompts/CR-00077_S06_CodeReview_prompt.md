# CR-00077_S06_CodeReview_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S06
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This CR adds no migrations.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- `ai-dev/active/CR-00077/reports/CR-00077_S05_Tests_report.md`
- `skills/iw-ai-core-testing/SKILL.md` — testing red-flag checklist.

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S06_CodeReview_report.md` — findings with severities.

## Scope of Review

Per-agent review of the new test files from S05. Apply the iw-ai-core-testing red-flag checklist:

1. **Assertion strength**
   - Every test asserts an *exact* value, list, or substring — no `assert response`, `assert result`, `assert len(...) > 0`, no `pytest.raises(Exception)` (must be a specific exception class).
   - The happy-path dashboard test asserts EACH glob string individually (loop or explicit), not just `assert "globs" in body` (vacuous).

2. **Isolation**
   - The dashboard test uses the `db_session` testcontainer fixture from `tests/conftest.py`. **NEVER** connects to port 5433. Flag any `postgresql://...5433` URL as CRITICAL.
   - No test relies on data outside its own seed.
   - The unit test for `group_overlap_events` is pure — no DB, no `datetime.now()`.

3. **TDD RED evidence**
   - The report's `tdd_red_evidence` field is populated for each new test module with a plausible failure (AssertionError / 404-vs-200 mismatch / ImportError), not a collection error or fixture error.

4. **Coverage of AC**
   - AC1 (clickable trigger): not directly testable from server-side; AC1 is covered by S14 browser_verification — note this in the review report.
   - AC2 (grouping by item): covered by happy-path test.
   - AC3 (no truncation): covered by asserting every glob appears.
   - AC4 (dismissal): covered by S14 browser_verification.
   - AC5 (404 when no event): covered by 404 test.
   - AC6 (read-only): assert response body does NOT contain `<form` or `hx-post`.

5. **No vacuous assertions** — `make test-assertions` (the QV scanner in S13) must accept these tests. If any assertion is structurally weak, flag and require a tightening edit.

6. **Naming / convention** — file names use snake_case starting with `test_`; functions named `test_*`; pytest collected without warnings.

## Severity Guide

- CRITICAL: live-DB connection, fixture pollution, missing 404 test.
- HIGH: vacuous assertions, missing AC coverage that S14 cannot legitimately fulfil.
- MEDIUM: weak edge-case coverage (e.g. the 300s window cutoff not exercised).
- LOW: docstring polish, test naming.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00077",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
