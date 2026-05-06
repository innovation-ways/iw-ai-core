# CR-00035 S06 — Code Review Report (Observability Unit)

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Reviewed**: S05 (backend-impl — observability unit)
**Review Step**: S06
**Agent**: code-review-impl
**Date**: 2026-05-06

---

## Summary

S05 implements four sub-deliverables for the observability unit:
1. **PID liveness probe** in `DocJobPoller.poll`
2. **New module `orch/doc_report.py`** with four pure functions
3. **Rewritten `DocService.complete_doc_job`** writing `agent_output` and `report`
4. **Aggregator surfaces `report`** in `_build_doc_generation_raw`

**Verdict**: PASS — zero mandatory fixes. Two low-severity observations noted for follow-up in S11 (tests).

---

## Pre-Flight Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 614 files already formatted |
| `make test-unit` | ✅ 2600 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 61.29s |

---

## Review Checklist

### (1) PID Liveness Probe ✅

**File**: `orch/daemon/doc_job_poller.py`

- ✅ `_PID_RACE_PROTECTION_SECONDS = 10` constant defined at line 39
- ✅ `_is_pid_alive(pid)` at lines 42–55: `ProcessLookupError` → dead, `PermissionError` → alive, success → alive
- ✅ `_detect_dead_subprocess_jobs(db)` at lines 125–157: queries `status=running AND agent_pid IS NOT NULL`, skips jobs whose `started_at > cutoff` (10-second race protection)
- ✅ `poll()` calls `_detect_dead_subprocess_jobs` **before** the wall-clock stall sweep (lines 79–99)
- ✅ Dead job calls `complete_doc_job(job.id, error="agent process exited without calling iw doc-job-done", worktree_path=...)` — error string matches AC2
- ✅ `db.commit()` at line 117 preserves existing transaction boundaries

### (2) `orch/doc_report.py` ✅

**File**: `orch/doc_report.py`

- ✅ All four functions are pure — no DB, no global state, no ambient IO except the passed-in log path
- ✅ `read_log_tail` returns `(text, original_size, line_count)`; empty/missing path returns `("", 0, 0)` cleanly
- ✅ Truncation marker exact format `"[truncated: N bytes elided]\n"` at line 62
- ✅ `parse_tool_calls` heuristic documented with multi-line docstring (lines 74–106) and pinned canonical example
- ✅ `build_execution_report` accepts all keyword args declared in the AC4 schema; returns `dict` with all required keys
- ✅ ANSI strip re-exported from `orch/utils/log_capture.py` — no duplication across the codebase

### (3) `complete_doc_job` ✅

**File**: `orch/doc_service.py`

- ✅ Signature has exactly one new kwarg: `worktree_path: str | Path | None` (keyword-only after `*` at line 509) — no `cli_tool` or `command_issued` kwargs
- ✅ Idempotency preserved: early return at lines 514–515 (`if job.status in (JobStatus.completed, JobStatus.failed): return job`) guards both original logic and new observability block
- ✅ `worktree_path` falls back to `project_for_worktree.repo_root` at line 539
- ✅ Outcome classification at lines 556–563: `completed | failed_timeout | failed_process_exited | failed_agent_error`
- ✅ **`command_issued` reconstruction** matches `_build_agent_command` exactly:
  - opencode (line 571): `f'opencode run "/doc-job {job.id}" --dangerously-skip-permissions'`
  - claude (line 573): `f'claude -p "/doc-job {job.id}" --permission-mode bypassPermissions'`
- ✅ `agent_output` always assigned at line 553 (empty string when log missing)
- ✅ `report` always assigned on terminal state at line 577 (all AC4 keys present)

### (4) Aggregator Surfaces `report` ✅

**File**: `orch/jobs/aggregator.py`

- ✅ `_build_doc_generation_raw` (line 440): `"report": job.report` included in returned dict
- ✅ Both `_fetch_doc_generation` (list view, line 384) and `_get_doc_generation` (detail view, line 654) go through `_build_doc_generation_raw` — single fix point per I-00064

### Scope Discipline ✅

S05's changed files (per git diff):
- `orch/daemon/doc_job_poller.py` — within S05 scope ✅
- `orch/doc_service.py` — within S05 scope ✅
- `orch/doc_report.py` — new file, S05 scope ✅
- `orch/jobs/aggregator.py` — within S05 scope ✅
- `tests/unit/test_doc_report.py` — new file, S05 scope ✅
- `tests/unit/test_doc_job_poller.py` — updated tests, S05 scope ✅

**S05 did NOT touch** (correctly scoped): `commands/doc-job.md`, `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md`, `orch/cli/doc_commands.py`, `orch/cli/main.py` — those belong to S03.

### General Code Quality ✅

- ✅ No `importlib.reload(orch.config)` calls introduced
- ✅ No async / threading introduced into the daemon loop
- ✅ No silent exception swallows around `os.kill` — all exceptions from `_detect_dead_subprocess_jobs` are caught and logged at lines 82–99
- ✅ Type hints on all new helper functions (`_is_pid_alive`, `_detect_dead_subprocess_jobs`)
- ✅ `JobOutcome` type alias placed after all imports to avoid ruff E402

---

## Observations (No Fix Cycle Required)

### Obs-1: `test_complete_doc_job_with_error` stub missing `worktree_path` kwarg (MEDIUM-INFO)

**File**: `tests/unit/test_doc_job_poller.py`, line 412

The test stub `complete_doc_job(job_id, error=None)` does not include the `worktree_path` keyword-only parameter. The real signature is `complete_doc_job(job_id, error=None, *, worktree_path=None)`. This works in Python because `worktree_path` has a default, but the stub doesn't reflect the full interface. S11 should update the stub to include `*, worktree_path=None` to keep it in sync.

### Obs-2: ANSI strip grep confirmed clean

Search for `re.compile(r'\\x1b'` across the entire `orch/` tree returns **zero matches** — confirmed by the review agent's own grep. `strip_ansi` lives in exactly one place (`orch/utils/log_capture.py:15`) and is re-exported by `orch/doc_report.py:12`.

---

## Test Coverage

| Suite | Result |
|-------|--------|
| Unit (`make test-unit`) | ✅ 2600 passed, 4 skipped, 5 xfailed, 1 xpassed |
| `test_doc_report.py` (isolated) | ✅ 34 passed |
| `test_doc_job_poller.py` (isolated) | ✅ All relevant tests passed |

The coverage report from the isolated run shows ~5.6% because it only ran the two target files (others skipped). The full suite shows 52.78% total coverage, well above the 46.0% threshold.

---

## Findings Summary

| Severity | File | Issue | Suggested Fix |
|----------|------|-------|--------------|
| MEDIUM-INFO (S11) | `tests/unit/test_doc_job_poller.py:412` | Test stub missing `worktree_path` kwarg | Add `*, worktree_path=None` to stub signature |

**Mandatory fix count**: 0  
**Verdict**: PASS

---

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S05",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "2600 passed (make test-unit). 34 unit tests for doc_report + doc_job_poller pass in isolation. Full suite coverage 52.78% > 46.0% threshold.",
  "notes": "One MEDIUM-INFO observation for S11: test_complete_doc_job_with_error stub should mirror the full worktree_path kwarg signature. No mandatory fixes. All AC2-AC5 criteria met."
}
```