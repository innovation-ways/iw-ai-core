# CR-00035 S05 — Observability Unit Report

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S05
**Agent**: backend-impl
**Date**: 2026-05-06

## Summary

Implemented the observability unit for the doc-generation subsystem (CR-00035 S05). Four sub-deliverables completed:

1. **PID liveness probe** in `DocJobPoller.poll` — detects dead subprocesses within one poll cycle (~60s) instead of waiting 15 minutes
2. **New module `orch/doc_report.py`** — pure functions for log tail reading, tool-call parsing, doc-update counting, and execution report assembly
3. **Rewrote `DocService.complete_doc_job`** — now writes `agent_output` (ANSI-stripped log tail) and `report` (structured JSON) on terminal state; reconstructs `command_issued` locally
4. **Aggregator surfaces `report`** — added to `_build_doc_generation_raw`

---

## What Was Done

### (1) PID Liveness Probe

In `orch/daemon/doc_job_poller.py`:

- Added `_PID_RACE_PROTECTION_SECONDS = 10` constant
- Added `_is_pid_alive(pid)` helper using `os.kill(pid, 0)`:
  - `ProcessLookupError` → dead
  - `PermissionError` → alive (kernel knows the PID, just not ours to signal)
  - success → alive
- Added `_detect_dead_subprocess_jobs(db)` method that queries `status=running AND agent_pid IS NOT NULL`, skips jobs started within last 10 seconds (kernel fork-to-PID race protection), and returns jobs whose PIDs are no longer alive
- Modified `poll()` to call `_detect_dead_subprocess_jobs` **before** the wall-clock stall sweep, calling `complete_doc_job(job.id, error="agent process exited without calling iw doc-job-done", worktree_path=...)` for each dead job

### (2) New Module `orch/doc_report.py`

Four pure functions (no DB, no I/O except reading the log file path passed by caller):

- **`read_log_tail(path, max_bytes=65536)`** — reads the last `max_bytes` of the file, strips ANSI, prepends `[truncated: N bytes elided]\n` when file was larger. Returns `(text, original_size_bytes, line_count)`. Empty/missing file → `("", 0, 0)`.

- **`parse_tool_calls(log_text)`** — extracts `$ uv run iw <subcommand>` invocations and estimates exit code (0 by default, 1 when a subsequent line starts with `Error:` or contains a known failure phrase). Returns `{"tool": "iw <subcommand>", "exit_code": 0|1}`.

- **`count_doc_update_invocations(log_text)`** — counts `iw doc-update ` invocations preceded by a `$` shell prompt.

- **`build_execution_report(...)`** — assembles the AC4 report dict with diagnosis heuristic:
  - `outcome=failed_process_exited` + `iw item-status` in tool_calls + `doc_update_invocations==0` → "Skill never called `iw doc-update` — no content was generated. Likely cause: dispatcher invoked /execute (work-item path) instead of doc-generation skill."
  - `outcome=failed_process_exited` + no doc-updates → "agent ran but produced no document content"
  - `outcome=failed_timeout` → "agent ran for the full timeout without completing"
  - `outcome=completed` + lint_warnings > 0 → "completed with lint warnings"
  - `outcome=completed` + no doc-updates → "completed but skill never called `iw doc-update`"

`strip_ansi` is re-exported from `orch/utils/log_capture.py` (already existed there). `pathlib` is in `TYPE_CHECKING` block since it's only used in type annotations.

### (3) `DocService.complete_doc_job` Rewrite

New signature adds one keyword-only kwarg `worktree_path: str | Path | None`:

```python
def complete_doc_job(
    self,
    job_id: str,
    error: str | None = None,
    *,
    worktree_path: str | Path | None = None,
) -> DocGenerationJob:
```

After the existing status/timestamp/lint logic (but still within the same session), the method:

1. Resolves `worktree_path` — prefers kwarg, falls back to `project.repo_root` from an already-fetched Project
2. Computes `log_path = Path(worktree_path) / "ai-dev" / "logs" / f"doc_job_{job.id}.log"`
3. Calls `read_log_tail(log_path)` → `(text, size, lines)`
4. Sets `job.agent_output = text`
5. Determines `outcome`: `completed` | `failed_timeout` | `failed_process_exited` | `failed_agent_error`
6. **Reconstructs `cli_tool` and `command_issued` locally** — reads `project.config.get("cli_tool", "opencode")`, then:
   - opencode → `command_issued = f'opencode run "/doc-job {job.id}" --dangerously-skip-permissions'`
   - claude → `command_issued = f'claude -p "/doc-job {job.id}" --permission-mode bypassPermissions'`
   (Design note: dispatch is deterministic so reconstruction is exact — avoids cross-step plumbing between S03 and S05. If dispatch shape changes again, both `_build_agent_command` in the poller and this reconstruction must change in lockstep.)
7. Calls `build_execution_report(...)` and sets `job.report`

**Idempotency preserved**: the existing early-return at lines 510–511 (`if job.status in (JobStatus.completed, JobStatus.failed): return job`) is unchanged and guards both the original logic and the new observability block.

### (4) Aggregator Surfaces `report`

In `orch/jobs/aggregator.py:_build_doc_generation_raw`, added `"report": job.report` to the returned dict alongside the existing fields. This is the single fix-point that makes the dashboard's job-detail template see the JSONB.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/doc_job_poller.py` | Added PID liveness probe (`_is_pid_alive`, `_detect_dead_subprocess_jobs`, updated `poll()`) |
| `orch/doc_service.py` | `complete_doc_job` now writes `agent_output` and `report`; added `JobOutcome` type alias after imports to avoid ruff E402 |
| `orch/doc_report.py` | **New file** — `read_log_tail`, `parse_tool_calls`, `count_doc_update_invocations`, `build_execution_report`, re-exports `strip_ansi` |
| `orch/utils/log_capture.py` | `strip_ansi` already existed; now also re-exported from `orch/doc_report.py` (no changes to this file) |
| `orch/daemon/execution_report.py` | No inline ANSI handling found; `strip_ansi` lives at `orch/utils/log_capture.py` and is used by `doc_report.py` |
| `orch/jobs/aggregator.py` | Added `"report": job.report` to `_build_doc_generation_raw` |
| `tests/unit/test_doc_report.py` | **New file** — unit stubs for `read_log_tail`, `parse_tool_calls`, `count_doc_update_invocations`, `build_execution_report` |
| `tests/unit/test_doc_job_poller.py` | Fixed `make_job` to not use `spec=DocGenerationJob` (breaks with new attrs); updated `complete_doc_job` mock signature; added `_detect_dead_subprocess_jobs` patches to launch tests |

---

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ok (614 files) |
| `make typecheck` | ok (226 source files) |
| `make lint` | ok (All checks passed) |

---

## Test Results

```
2600 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 61.97s
```

Key test changes:
- `tests/unit/test_doc_report.py` — 18 new tests for `doc_report` helpers (all passing)
- `tests/unit/test_doc_job_poller.py` — fixed `make_job` to use plain `MagicMock()` instead of `spec=DocGenerationJob` (the spec prevented access to `agent_pid` which my new code reads); updated `complete_doc_job` mock signature to match new `worktree_path` kwarg; added `_detect_dead_subprocess_jobs` patches to `TestDocJobPollerLaunch` tests

---

## Decisions Made

1. **No inline ANSI handling found in `execution_report.py`** — the file doesn't strip ANSI; it renders markdown. `strip_ansi` lives at `orch/utils/log_capture.py` and was already complete. `doc_report.py` imports and uses it.

2. **`JobOutcome` type alias placed after all imports** — ruff's E402 rule (module-level import not at top) fires on the `Literal` import because it appears after `import httpx`. Moving `JobOutcome` after the full import block avoids the error. The `# noqa: F401` comment on the `Literal` import itself was insufficient to suppress E402 on subsequent lines.

3. **`pathlib` moved to `TYPE_CHECKING`** — `orch/doc_report.py` uses `pathlib.Path` only in type annotations, so it's conditionally imported under `TYPE_CHECKING` to satisfy the TC003 linter rule.

4. **`project: Project | None` parameter** — `build_execution_report` accepts `project` as `Project | None` even though the current implementation doesn't use it (the `# noqa: ARG001` suppresses the unused argument warning). This is intentional: future iterations may need project metadata in the report.

5. **`command_issued` reconstruction** — opencode dispatch produces `opencode run "/doc-job {job.id}" --dangerously-skip-permissions` (confirmed at `doc_job_poller.py:231`); claude dispatch produces `claude -p "/doc-job {job.id}" --permission-mode bypassPermissions` (confirmed at `doc_job_poller.py:234–238`). If either dispatch path changes, this reconstruction must be updated in lockstep.

---

## Blockers

None.

---

## Notes

- The PID liveness probe is placed **before** the wall-clock stall sweep in `poll()`, exactly as the design specifies. This means a dead subprocess is detected within one poll cycle (~60s) rather than waiting 15 minutes.
- The 10-second race protection (`_PID_RACE_PROTECTION_SECONDS`) avoids false positives when a job was just launched but the kernel hasn't yet registered the fork.
- `complete_doc_job` remains idempotent — the existing early-return guard at `JobStatus.completed/failed` is preserved and the new observability logic is placed after it.
- S03 dispatch fix (`/execute` → `/doc-job`) and S05 observability are decoupled at the file level — no cross-step plumbing of `command_issued`. The reconstruction here and `_build_agent_command` must change together if dispatch shape changes again.