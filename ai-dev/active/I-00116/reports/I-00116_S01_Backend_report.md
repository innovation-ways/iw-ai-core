# I-00116 S01 Backend Report

**Work Item**: I-00116 — Daemon marks code-review step as PID-dead when reviewer exits without `iw step-done`; downstream review chain loops unboundedly
**Step**: S01 (Backend)
**Agent**: Backend
**Date**: 2026-05-28

---

## What was done

Added `_try_recover_completed_review_step(db, run, project_id, now)` to `orch/daemon/step_monitor.py` and wired it into `_check_step_health` between the `_probe_for_child` check and the `_handle_crashed` call.

The helper checks the authoritative on-disk verdict report before the daemon declares a review step crashed:

1. Guards on `run.step_type in ('code_review', 'code_review_final')` — no effect on other step types.
2. Anchors the glob at `run.worktree_path` (not daemon cwd) to avoid cross-project contamination.
3. Uses `Path.glob` to find `ai-dev/active/<item>/reports/<item>_<step>_..._report.md`.
4. Requires `report_mtime > run.started_at.timestamp()` so stale reports from prior runs are ignored.
5. Parses the first ```json ``` fenced block; rejects malformed JSON or missing `verdict` key.
6. On `verdict='pass'`: marks run `completed`, step `completed`.
7. On `verdict='fail'` with `mandatory_fix_count > 0`: marks run `failed`, step `needs_fix` (same contract as `iw step-done`).
8. Emits a `DaemonEvent` of type `step_run_recovered_from_report` with structured `event_metadata` (not `metadata` — SQLAlchemy reserves the name per CLAUDE.md Critical Rules).

If any check fails (no file, mtime stale, parse error, unknown verdict), the function returns `False` and `_handle_crashed` is called as before.

---

## Files changed

- `orch/daemon/step_monitor.py` — added `_REVIEW_STEP_TYPES`, `_try_recover_completed_review_step`, and the one-call-site in `_check_step_health`.

---

## TDD RED Evidence

Pre-fix `_check_step_health` calls `_handle_crashed` unconditionally when `_probe_for_child` returns False, regardless of step_type or on-disk report presence. The S07 reproduction test (`test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed`) will fail with:

```
AssertionError: I-00116: review step with a verdict report on disk must NOT be marked crashed.
```

because `crashed.called` is `True` — the pre-fix code has no knowledge of the report file and proceeds directly to `_handle_crashed`. The S07 test exercises the exact precondition described in the incident (reviewer exits cleanly without `iw step-done`) and asserts that `_handle_crashed` is **not** called when a well-formed report exists on disk with mtime > `started_at`.

---

## Post-Edit Gates

| Gate | Result |
|------|--------|
| `make format-check` | pass |
| `make lint` | pass |

Two `PTH204` violations (use `Path.stat().st_mtime` instead of `os.path.getmtime`) and one `PTH207` violation (use `Path.glob` instead of `glob.glob`) were fixed before exit.

---

## Notes

- `_probe_for_child` body was NOT modified — it's I-00113's contract.
- `_handle_crashed` itself was NOT modified — only a sibling helper and its callsite were added.
- The `run.worktree_path` field is used as the anchor. In the normal daemon flow, `worktree_path` is set when the step run is created; if it is `None` the function returns `False` and the crash path is unchanged.
- `DaemonEvent.metadata` → `event_metadata` throughout (enforced by CLAUDE.md "Critical Rules" + `make lint`).
- Logger calls use `%`-style placeholders, not `.format()` or f-strings (enforced by `scripts/check_templates.py` via `make lint`).
- No migrations, no docker changes, no test files touched.