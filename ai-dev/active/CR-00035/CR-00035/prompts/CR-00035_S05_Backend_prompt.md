# CR-00035_S05_Backend_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S05 — Observability unit
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt; `docker ps/inspect/logs` allowed. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT generate migrations — S01 already did. Do NOT add migration files. Do NOT run alembic against port 5433.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` — design (required reading: `## Desired Behavior` "Live" + "After job terminates", AC2/AC3/AC4, `## Notes`).
- `ai-dev/active/CR-00035/reports/CR-00035_S01_Database_report.md` — `report` JSONB column is in place.
- `ai-dev/active/CR-00035/reports/CR-00035_S03_Backend_report.md` — confirms the dispatch shape is now `opencode run "/doc-job <id>" --dangerously-skip-permissions`. You do NOT consume any plumbed string from S03 — `command_issued` is reconstructed locally (see Requirement 3 below).
- `orch/daemon/doc_job_poller.py` — current poller (key functions: `poll`, `_process_project`, `_launch_job`, `_select_skill`).
- `orch/doc_service.py` — current `complete_doc_job` (lines ~500–531) and surrounding methods.
- `orch/utils/log_capture.py` — existing log helpers; the `strip_ansi` factoring target.
- `orch/jobs/aggregator.py` — `_build_doc_generation_raw` at line ~406.
- `orch/daemon/execution_report.py` — pattern reference for ANSI handling (likely the inline `re.compile(r'\x1b...')` to factor out).
- The actual broken-run log: `ai-dev/logs/doc_job_727a12bd-cae3-443b-b033-924ea767b0e8.log` — useful to eyeball while writing the report builder.

## Output Files

- `orch/daemon/doc_job_poller.py` — adds PID liveness probe (no other changes; do not touch `_build_agent_command` or `_launch_job` — those were edited in S03)
- `orch/doc_service.py` — `complete_doc_job` rewrite
- `orch/doc_report.py` — **new module** (helpers + report builder)
- `orch/utils/log_capture.py` — exposes `strip_ansi(text: str) -> str`
- `orch/daemon/execution_report.py` — refactored to import `strip_ansi` from `orch/utils/log_capture.py` (if it currently inlines the regex)
- `orch/jobs/aggregator.py` — adds `report` to `_build_doc_generation_raw`
- `ai-dev/active/CR-00035/reports/CR-00035_S05_Backend_report.md`

## Context

You are implementing the **observability unit**: PID liveness, log capture, structured execution report, and the aggregator hook that surfaces it. Four sub-deliverables, all in this step. The dispatch fix and skill updates were handled in S03 — do NOT touch those files (`commands/doc-job.md`, `skills/**`, `_build_agent_command`, `orch/cli/**`) here. Stepping on S03's diff is a HIGH scope finding.

Read the design doc end-to-end before starting. Pay close attention to:
- `## Desired Behavior` — "Live" and "After job terminates" subsections
- `## Acceptance Criteria` AC2..AC5
- `## Notes` — `complete_doc_job` signature, ANSI strip helper location, aggregator parity, missing files, step splitting (commit boundary discipline with S03)

## Requirements

### 1. PID liveness probe in `DocJobPoller.poll`

In `orch/daemon/doc_job_poller.py`, add a private method:

```python
def _detect_dead_subprocess_jobs(self, db: Session) -> list[DocGenerationJob]:
    """Return running jobs whose agent_pid no longer points at a live process."""
    ...
```

Use `os.kill(pid, 0)`:
- `ProcessLookupError` → dead
- `PermissionError` → alive (kernel knows the PID, just not ours to signal)
- success → alive

Iterate jobs with `status=running AND agent_pid IS NOT NULL`. Skip jobs whose `started_at` was less than 10 seconds ago (avoid racing the daemon's own launch — `subprocess.Popen` returns the PID before the child is fully forked in some kernels).

In `poll()`, run this **before** the wall-clock stall sweep. For each dead-subprocess job, call `complete_doc_job(job.id, error="agent process exited without calling iw doc-job-done", worktree_path=<resolved>)`. The error message text is part of AC2 — keep it stable. Do NOT pass `command_issued` or `cli_tool` from the poller — `complete_doc_job` reconstructs them internally (see Requirement 3).

### 2. New module `orch/doc_report.py`

Pure functions (no DB, no IO except reading the log file the caller passes a path to):

```python
def read_log_tail(path: pathlib.Path, max_bytes: int = 65536) -> tuple[str, int, int]:
    """Return (text, original_size_bytes, line_count). Truncates to last max_bytes.
    Prepends "[truncated: N bytes elided]\n" when the file was larger.
    Empty/missing file → ("", 0, 0)."""

def parse_tool_calls(log_text: str) -> list[dict]:
    """Extract `iw <subcommand>` invocations and their exit signal.
    Return [{"tool": "iw item-status", "exit_code": 1}, ...]
    Use the literal pattern `$ uv run iw <cmd>` followed by zero or more output
    lines and detect `Error:` / non-zero exit signals (the captured logs use
    plain shell prompts — no real exit code is recorded, so exit_code is 0
    by default and 1 when a subsequent line starts with `Error:` or the
    output contains a known failure phrase). Document the heuristic in
    a docstring; tests pin it."""

def count_doc_update_invocations(log_text: str) -> int:
    """Count `iw doc-update ` occurrences (preceded by a $ shell prompt)."""

def build_execution_report(
    *,
    job: DocGenerationJob,
    project: Project,
    log_text: str,
    log_size_bytes: int,
    log_line_count: int,
    outcome: Literal["completed", "failed_timeout", "failed_process_exited", "failed_agent_error"],
    command_issued: str | None,
    cli_tool: str,
) -> dict[str, Any]:
    """Assemble the AC4 report dict. Includes a one-line `diagnosis`
    derived from heuristic rules:
      - outcome=failed_process_exited AND doc_update_invocations==0
        AND tool_calls contains 'iw item-status' → wrong-dispatch diagnosis
      - outcome=failed_process_exited AND doc_update_invocations==0 → "agent
        ran but produced no document content"
      - outcome=failed_timeout → "agent ran for the full timeout without
        completing"
      - outcome=completed AND lint_warning_count>0 → "completed with lint warnings"
      - outcome=completed AND doc_update_invocations==0 → suspicious; flag
      - default → ""
    """
```

Re-export `strip_ansi` from `orch/utils/log_capture.py` (factor it out of `orch/daemon/execution_report.py` if it lives there inline today — search for `\x1b` and `re.compile` to find it). Apply `strip_ansi` inside `read_log_tail` so callers always get clean text.

### 3. `DocService.complete_doc_job` writes `agent_output` and `report`

Modify the method signature (only one new kwarg — `worktree_path`):

```python
def complete_doc_job(
    self,
    job_id: str,
    error: str | None = None,
    *,
    worktree_path: str | pathlib.Path | None = None,
) -> DocGenerationJob:
```

Inside, after the existing status/timestamp/lint logic:

1. Resolve `worktree_path`: prefer the kwarg; fall back to `self._session.get(Project, job.project_id).repo_root` when None.
2. Compute `log_path = pathlib.Path(worktree_path) / "ai-dev" / "logs" / f"doc_job_{job.id}.log"`.
3. Call `read_log_tail(log_path)` → `(text, size, lines)`.
4. `job.agent_output = text` (may be empty string if file missing).
5. Determine `outcome`:
   - `error is None` → `"completed"`
   - error contains `"timeout"` → `"failed_timeout"`
   - error contains `"agent process exited"` → `"failed_process_exited"`
   - else → `"failed_agent_error"`
6. **Reconstruct `cli_tool` and `command_issued` locally — do NOT accept them as kwargs.** Look up the project (you already have it from step 1) and read `cli_tool = project.config.get("cli_tool", "opencode") if project.config else "opencode"`. Then build:
   - opencode → `command_issued = f'opencode run "/doc-job {job.id}" --dangerously-skip-permissions'`
   - claude → `command_issued = f'claude -p "/doc-job {job.id}" --permission-mode bypassPermissions'` (or whatever `_build_agent_command` actually emits — keep the strings in sync; cite `doc_job_poller.py` line numbers in your step report).
   - unknown → `command_issued = None`
7. `job.report = build_execution_report(job=job, project=project, log_text=text, log_size_bytes=size, log_line_count=lines, outcome=outcome, command_issued=command_issued, cli_tool=cli_tool)`.

Rationale (from the design's Notes section): the dispatch shape is now deterministic, so reconstructing `command_issued` here is exact and avoids cross-step plumbing between S03 and S05. If the dispatch shape ever changes again, the reconstruction here and `_build_agent_command` must change in lockstep — call this out in your step report so reviewers can verify drift.

The method MUST remain idempotent: a second call after terminal state still returns the row unchanged (the existing early-return at lines 508–509 handles this; do not regress it). Verify by reading the original method top-to-bottom and confirming the new logic is added AFTER the early-return guard.

### 4. Aggregator surfaces `report`

In `orch/jobs/aggregator.py:_build_doc_generation_raw`, add `"report": job.report` to the returned dict (alongside the existing fields). This is what makes the dashboard's job-detail template see it. Forgetting this is the single most likely silent miss — the field will exist in the DB but never reach the page.

Verify both the list-view path AND detail-view path go through `_build_doc_generation_raw`. The single fix-point is documented in the existing docstring near line 414 (per I-00064).

## Project Conventions

Read `orch/CLAUDE.md` for daemon patterns, `tests/CLAUDE.md` for test rules. Critical rules:

- The daemon is a single-threaded sync polling loop. Don't introduce async or threads.
- Sessions: `with self._session_factory() as db:` per logical work-unit. `db.commit()` explicitly. Never share a session across worktree boundaries.
- ORM driver is psycopg v3 (`psycopg[binary]`).
- For tests: testcontainers only, never live DB on 5433.
- For ANSI handling: factor a single `strip_ansi` helper rather than inlining `re.compile(r'\x1b\[[0-9;]*m')` in three places.

## TDD Requirement

S11 writes the formal tests, but you SHOULD write at least the unit-test stubs for the helpers you create (`read_log_tail`, `parse_tool_calls`, `build_execution_report`) and confirm they pass before declaring `complete`. Don't over-invest — S11 has the formal coverage.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

All three must be clean for files you touched before you report `complete`.

## Test Verification

```bash
make test-unit
```

If integration tests cover the doc job flow, run them too. Report PASS only when zero failures involve files you touched.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "CR-00035",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/doc_job_poller.py",
    "orch/doc_service.py",
    "orch/doc_report.py",
    "orch/utils/log_capture.py",
    "orch/daemon/execution_report.py",
    "orch/jobs/aggregator.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "command_issued is reconstructed locally from job.skill_used + project.config[cli_tool] + job.id (no S03 plumbing consumed); ANSI helper now lives at orch/utils/log_capture.py; idempotency early-return preserved."
}
```
