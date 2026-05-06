# CR-00035_S13_CodeReview_Final_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Review Step**: S13 (Final Review)
**Implementation Steps Reviewed**: S01..S11

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt; `docker ps/inspect/logs` read-only allowed. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Read-only `alembic history / current / show`. No `upgrade/downgrade/stamp` against port 5433.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` — the contract.
- All step reports `S01..S12`.
- Every file changed across S01..S11 (read them in full):
  - `orch/db/models.py` (new field)
  - `orch/db/migrations/versions/<rev>_add_report_to_doc_generation_jobs.py`
  - `orch/daemon/doc_job_poller.py` (S03 dispatch fix + S05 PID liveness)
  - `orch/cli/doc_commands.py` (S03 new `doc-job-status` command)
  - `orch/cli/main.py` (registers `doc-job-status`)
  - `orch/doc_service.py` (S05 complete_doc_job)
  - `orch/doc_report.py` (S05)
  - `orch/utils/log_capture.py` (S05 strip_ansi)
  - `orch/daemon/execution_report.py` (S05 refactor to import strip_ansi)
  - `orch/jobs/aggregator.py` (S05 raw includes report)
  - `dashboard/routers/<chosen>.py` (S07 — 3 new endpoints)
  - `dashboard/routers/jobs_ui.py` (S07 — log_file_exists into context)
  - `dashboard/templates/pages/project/job_detail.html` (S09 — Live Log + Execution Report cards)
  - `commands/doc-job.md` (S03)
  - `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md` (S03)
  - All `tests/unit/` and `tests/integration/` new files (S11)
  - `tests/fixtures/doc_jobs/**` (S11)

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S13_CodeReview_Final_report.md`

## Context

This is the **cross-step final review**. Per-agent reviews already covered each step in isolation. Your job is to verify the steps integrate end-to-end and that the design doc's `## Acceptance Criteria` AC1..AC9 are all satisfied by the combined work.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
make typecheck
```

Any new violation across any S01..S11 changed file = **CRITICAL**.

## End-to-End Integration Trace (the critical review)

Walk the data flow and verify each handoff:

### Trace 1: a successful run

1. Daemon launches a doc job → `_build_agent_command` produces `opencode run "/doc-job <UUID>" ...`. **Verify**: NOT `/execute`.
2. opencode loads `commands/doc-job.md` and dispatches to `iw-doc-generator` (or `iw-doc-system`). **Verify**: file exists, frontmatter valid.
3. Skill instructs the agent to read context via `iw doc-job-status <job-id> --json`. **Verify**: the command exists in `orch/cli/doc_commands.py`, is registered in `orch/cli/main.py`, returns the AC9 keys, and is read-only.
4. Skill SKILL.md tells the agent to call `iw doc-update` then `iw doc-job-done`. **Verify**: both files contain identical lifecycle section.
5. `iw doc-job-done` (CLI) → `DocService.complete_doc_job(job_id)` → reads on-disk log → writes `agent_output` and `report`. **Verify**: kwargs path works without explicit `worktree_path`.
6. `_build_doc_generation_raw` exposes `report` to the dashboard. **Verify**: grep aggregator for `"report":`.
7. `job_detail.html` renders the Execution Report card when `raw.report` is truthy. **Verify**: condition matches.

### Trace 2: a process-exited-early run

1. Daemon launches the job; the agent crashes after 5 seconds.
2. Next poll cycle: PID liveness probe detects dead pid → `complete_doc_job(job.id, error="agent process exited without calling iw doc-job-done")`.
3. `complete_doc_job` reads the log → builds report with `outcome="failed_process_exited"`, runs the wrong-dispatch heuristic if applicable.
4. Dashboard renders the Execution Report card with the diagnosis line.

**Verify**: error string matches between probe call site and `build_execution_report`'s outcome-classification logic. Drift here silently demotes the outcome to `failed_agent_error`.

### Trace 3: live-log streaming

1. UI opens `/project/<pid>/jobs/doc_generation/<id>` while job is `running`.
2. Page renders Live Log card with `sse-connect` to `.../log/stream`.
3. SSE generator opens log file, emits last 50 lines, then tails. ANSI stripped per line.
4. Job reaches terminal status; SSE generator emits `event:status data:terminal` and closes.

**Verify**: the terminal-detection re-checks job status via a fresh short-lived session; verify by reading the SSE generator code; flag any `Depends(get_db)` injected into the SSE handler that holds a session for the stream's lifetime.

### Trace 4: AC8 endpoint shapes

GET `/log/tail` → JSON.
GET `/log/stream` → text/event-stream.
GET `/log/raw` → text/plain attachment.

**Verify**: response media types. Any mismatch is HIGH.

### Trace 5: AC9 — `iw doc-job-status` round-trip

1. Run `uv run iw doc-job-status DOC-00004 --json` against a seeded DB.
2. **Verify**: exit code 0, single-object JSON, all AC9 keys present, datetimes ISO-8601.
3. **Verify**: row hash before/after invocation is unchanged (read-only).
4. Run with a bogus id → **Verify**: exit code != 0, stderr "not found".

## Acceptance Criteria coverage

For each AC1..AC9, identify the test(s) that verify it. If any AC has no corresponding test, flag as **HIGH (testing)**.

## Cross-cutting checks

- No `agent-browser` references anywhere added.
- No `chromium.launch()` anywhere added.
- No `npx playwright install` anywhere added.
- No `localhost:5173` / `localhost:5174` hardcoded URLs in QV browser prompt.
- No `docker compose up/down/restart` invocations from any code path you can see, even in comments.
- No `importlib.reload(orch.config)` in any new test.
- ANSI strip exists in **one** location (`orch/utils/log_capture.py`); not duplicated.
- `event_metadata` Python attribute (not `metadata`) on any new `DaemonEvent` insert.

## Test verification

```bash
make test-unit
make allure-integration
make typecheck
make lint
```

ALL must pass. Report exact pass/fail counts.

## Severity Levels

Standard. CRITICAL/HIGH/MEDIUM_FIXABLE trigger fix cycles.

## Review Result Contract

```json
{
  "step": "S13",
  "agent": "CodeReview_Final",
  "work_item": "CR-00035",
  "verdict": "pass|fail",
  "ac_coverage": {
    "AC1": "covered_by: tests/...",
    "AC2": "covered_by: tests/...",
    "AC3": "covered_by: tests/...",
    "AC4": "covered_by: tests/...",
    "AC5": "covered_by: tests/...",
    "AC6": "covered_by: tests/...",
    "AC7": "covered_by: tests/...",
    "AC8": "covered_by: tests/...",
    "AC9": "covered_by: tests/..."
  },
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
