# I-00116_S08_CodeReview_Tests_prompt

**Work Item**: I-00116
**Step**: S08
**Agent**: CodeReview (reviewing S07 — Tests)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Scope of review

ONLY the three test files created by S07:

- `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py`
- `tests/integration/test_fix_cycle_review_relaunch_cap.py`
- `tests/unit/test_review_prompt_scope.py`

Flag any production-code change as a CRITICAL scope violation — S07 is tests-only.

## Input Files

- **Runtime state**: `uv run iw item-status I-00116 --json`
- **Design**: `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- **S07 report**: `ai-dev/active/I-00116/reports/I-00116_S07_Tests_report.md`
- **The new test files**
- **Test conventions** (mandatory): `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- Review report: `ai-dev/active/I-00116/reports/I-00116_S08_CodeReview_report.md`

## Review Checklist

| # | Check |
|---|-------|
| 1 | All four tests from the design's reproduction set are present and named exactly: `test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed`, `..._without_report_still_marked_crashed`, `..._non_review_step_type_is_unchanged`, `..._recovered_run_emits_daemon_event_with_verdict` |
| 2 | File (a) mocks at `_is_pid_alive` and `_probe_for_child` (the boundaries) — NOT at `_try_recover_completed_review_step` (would defeat the bug-class test boundary) |
| 3 | File (b) uses the real testcontainer-backed `db_session` (NOT a `MagicMock`) — `FOR UPDATE` locking must be exercised per CLAUDE.md rule 3 |
| 4 | File (b) tests both under-cap (no effect) AND at-cap (item→failed + exactly one DaemonEvent) paths |
| 5 | File (b) at-cap test verifies idempotency (second call doesn't emit a second event) |
| 6 | File (b) uses `monkeypatch.setenv` for `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` (small value like 3 for speed). NO `importlib.reload(orch.config)` |
| 7 | File (c) reads the actual master prompts on disk — no filesystem mocking |
| 8 | File (c) asserts BOTH agents/code-review-impl.md AND commands/code-review-impl.md contain `allowed_paths` |
| 9 | All assertions are SEMANTIC: specific verdict values, specific DaemonEvent types, specific cap counts. No `assert ... in data` shape-only checks |
| 10 | pytest-randomly compatibility — each test is self-contained and order-independent |
| 11 | No production code touched (grep `git diff` for any non-test path) |
| 12 | Targeted pytest command runs the three new files and reports PASS for each |

## Required Pre-flight Gates

```bash
make lint
make format-check
uv run pytest tests/unit/daemon/test_step_monitor_i00116_review_recovery.py \
              tests/integration/test_fix_cycle_review_relaunch_cap.py \
              tests/unit/test_review_prompt_scope.py -v --no-cov
```

The pytest command MUST report all tests passing. If any test fails, that is a HIGH finding — re-review S01/S03/S05 alignment with the test expectations and flag the discrepancy.

## Verdict Contract

Same JSON contract block as S02. Verdict `pass` or `fail`. Findings array empty if pass.

## Step Done Contract

Call `iw step-done S08 --report ai-dev/active/I-00116/reports/I-00116_S08_CodeReview_report.md` before exit. Never exit without calling `iw step-done` or `iw step-fail`.
