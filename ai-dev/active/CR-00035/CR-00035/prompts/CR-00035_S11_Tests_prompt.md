# CR-00035_S11_Tests_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by `tests/conftest.py` are the **ONLY** Docker container interaction allowed in tests. No `docker compose`, no `docker kill/stop/rm`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Tests run migrations **inside testcontainers only** via the conftest fixture path. Do NOT run alembic against port 5433. Do NOT add migration files (S01 already did).

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. `## TDD Approach`, all AC).
- All implementation reports: `S01_Database_report.md`, `S03_Backend_report.md` (dispatch unit), `S05_Backend_report.md` (observability unit), `S07_Api_report.md`, `S09_Frontend_report.md`.
- `tests/conftest.py` — fixtures (`test_db_engine`, `db_session`, etc.). Read in full.
- `tests/CLAUDE.md` — testing conventions and HARD RULES.
- `tests/integration/` — pattern reference for testcontainer-backed tests.
- `tests/unit/` — pattern reference for fast unit tests.
- `ai-dev/logs/doc_job_727a12bd-cae3-443b-b033-924ea767b0e8.log` — the canonical broken-run trace; you'll capture this as a fixture.

## Output Files

- `tests/unit/test_doc_job_poller_pid_liveness.py` — new
- `tests/unit/test_doc_report.py` — new
- `tests/unit/test_doc_service_complete_writes_output.py` — new
- `tests/unit/test_doc_job_status_cli.py` — new (covers the new `iw doc-job-status` command from S03)
- `tests/integration/test_doc_job_log_endpoints.py` — new
- `tests/fixtures/doc_jobs/doc_00004_replay.log` — copy of the canonical broken-run log
- `tests/fixtures/doc_jobs/successful_run.log` — synthetic
- `tests/fixtures/doc_jobs/process_exited_early.log` — synthetic
- Possible updates: any existing `tests/**/test_doc_service*` or `tests/**/test_doc_job_*` whose assertions about `complete_doc_job` need updating to match the new behaviour.
- `ai-dev/active/CR-00035/reports/CR-00035_S11_Tests_report.md`

## Context

You are writing the test coverage for CR-00035. Follow TDD: a useful test FAILS on `main` (before this CR's implementation) and PASSES against the implementation S01–S09 produced. **Falsifiability is the bar.** Before writing each test, mentally check: "would this assertion fail if I reverted S03 or S05?". If no, the test is useless.

Read the design doc's `## TDD Approach` section in full. Implement every test enumerated there.

## Requirements

### 1. Capture fixtures

```bash
cp ai-dev/logs/doc_job_727a12bd-cae3-443b-b033-924ea767b0e8.log \
   tests/fixtures/doc_jobs/doc_00004_replay.log
```

Write `successful_run.log` synthetically — minimum content that exercises the report builder's success path:

```
[0m> build · MiniMax-M2.7
[0m→ Skill "iw-doc-generator"
$ uv run iw doc-update iw-ai-core code-index --content-file - --generated-by skill:iw-doc-generator --trigger-reason job:abc-123
ok
$ uv run iw doc-job-done abc-123
ok
[0m
```

Write `process_exited_early.log` — short, no `iw doc-update`, no `iw doc-job-done`:

```
[0m> build · MiniMax-M2.7
[0m→ Skill "iw-doc-generator"
$ uv run iw doc-update missing-project nonexistent-doc --content-file -
Error: project 'missing-project' not found
[0m
```

### 2. `tests/unit/test_doc_job_poller_pid_liveness.py`

Mock `os.kill` to inject `ProcessLookupError` / `PermissionError` / no-op success.

Tests:

- `test_dead_pid_marks_job_failed_within_one_cycle` — running job with dead PID, run one `poll()`, assert status=`failed`, error matches `"agent process exited"`, and `complete_doc_job` was called with `worktree_path`.
- `test_alive_pid_no_change` — `os.kill` returns cleanly, assert status stays `running`.
- `test_permission_error_treated_as_alive` — `os.kill` raises `PermissionError`, assert status stays `running`.
- `test_recently_started_job_skipped` — `started_at` 2 seconds ago, dead PID, assert status stays `running` (race protection).
- `test_agent_pid_none_skipped` — `agent_pid IS NULL`, assert no probe call.

Use the existing test session factory pattern. **Real DB rows in a testcontainer**, not mocks of the DB.

### 3. `tests/unit/test_doc_report.py`

Tests for `read_log_tail`, `parse_tool_calls`, `count_doc_update_invocations`, `build_execution_report`. No DB needed for these — they're pure.

- `test_read_log_tail_full_file` — small log → returns full text, no truncation marker.
- `test_read_log_tail_truncates` — log >64 KB → returns last 64 KB prefixed with `[truncated: N bytes elided]`. Verify the marker N matches.
- `test_read_log_tail_missing_path` — non-existent path → returns `("", 0, 0)`, no exception.
- `test_read_log_tail_strips_ansi` — fixture `doc_00004_replay.log` → returned text contains no `\x1b[`.
- `test_parse_tool_calls_doc_00004_fixture` — replay log → list contains `iw item-status`, `iw search`, `iw batch-status` with appropriate exit_codes.
- `test_count_doc_update_invocations_zero` — replay log → 0.
- `test_count_doc_update_invocations_one` — `successful_run.log` → 1.
- `test_build_report_wrong_dispatch_diagnosis` — pass replay log + `outcome="failed_process_exited"` → diagnosis mentions wrong dispatch / no doc content.
- `test_build_report_completed_success` — `successful_run.log` + `outcome="completed"` → `doc_update_invocations=1`, diagnosis is empty or "completed cleanly".
- `test_build_report_timeout_outcome` — replay log + `outcome="failed_timeout"` → diagnosis mentions timeout.
- `test_build_report_includes_all_ac4_fields` — assert every key from AC4 is present in the returned dict.

### 4. `tests/unit/test_doc_service_complete_writes_output.py`

Use a testcontainer-backed `db_session` fixture. Insert a `Project`, `ProjectDoc`, `DocGenerationJob` (status=running, agent_pid=12345). Write a fixture log file under a `tmp_path`-rooted fake repo_root.

- `test_complete_writes_full_log_when_small` — small log file → `agent_output` equals full file contents.
- `test_complete_truncates_when_large` — log >64 KB → `agent_output` starts with `[truncated:` and length ≤ 65536 + marker.
- `test_complete_writes_report_on_success` — `error=None` → `report.outcome == "completed"`, all AC4 keys present.
- `test_complete_writes_report_on_timeout_error` — `error="generation timeout after 15 minutes"` → `report.outcome == "failed_timeout"`.
- `test_complete_writes_report_on_process_exited_error` — `error="agent process exited without calling iw doc-job-done"` → `report.outcome == "failed_process_exited"`.
- `test_complete_idempotent` — call twice, assert second call is a no-op (does not re-truncate or re-overwrite).
- `test_complete_handles_missing_log_file` — log file doesn't exist → `agent_output == ""`, `report.log_size_bytes == 0`, no exception.
- `test_complete_falls_back_to_repo_root_when_no_kwarg` — pass `worktree_path=None` → method looks up `Project.repo_root`.

### 4b. `tests/unit/test_doc_job_status_cli.py`

Use `click.testing.CliRunner` against the new `iw doc-job-status` command (added in S03). Use a testcontainer-backed `db_session`; insert a `Project`, a `ProjectDoc` (with `title`, `editorial_category`), a `DocGenerationJob` referencing both.

- `test_doc_job_status_json_returns_all_keys` — `--json` output decodes; assert keys: `id`, `public_id`, `project_id`, `doc_id`, `doc_title`, `editorial_category`, `status`, `skill_used`, `trigger_reason`, `agent_pid`, `section_guides_snapshot`, `guide_snapshot`, plus the timestamps.
- `test_doc_job_status_resolves_by_public_id` — call with `DOC-NNNNN` returns the same row as the UUID.
- `test_doc_job_status_resolves_by_uuid` — call with the UUID resolves correctly.
- `test_doc_job_status_join_returns_doc_title` — when `doc_id` is set, `doc_title` and `editorial_category` come from the joined `ProjectDoc`.
- `test_doc_job_status_doc_id_null_returns_null_join_fields` — when `doc_id` is None, both `doc_title` and `editorial_category` are null (not raised).
- `test_doc_job_status_missing_job_exits_nonzero` — invoke with bogus id → exit code != 0, stderr contains "not found".
- `test_doc_job_status_is_read_only` — capture row hash before/after invocation; assert no DB mutation.
- `test_doc_job_status_human_output_renders` — without `--json`, output contains key labels (smoke test, not a strict format pin).
- `test_doc_job_status_datetimes_serialised_iso8601` — `started_at`, `requested_at` etc. are strings parseable by `datetime.fromisoformat` (not Python `datetime` repr).

### 5. `tests/integration/test_doc_job_log_endpoints.py`

Use `TestClient` against the FastAPI app. testcontainer-backed DB per `tests/CLAUDE.md` rules:
- `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- No `importlib.reload(orch.config)` — use `monkeypatch.delenv` instead.

Tests:

- `test_log_tail_returns_last_n_lines` — fixture log written to tmp_path, GET `/log/tail?n=10` → 200, JSON shape, last 10 lines, ANSI stripped.
- `test_log_tail_default_n_is_200` — large fixture → returns 200 lines.
- `test_log_tail_n_capped_at_1000` — `?n=10000` → returns at most 1000.
- `test_log_tail_missing_file_404` — no log file → 404 with `detail` body.
- `test_log_tail_empty_file_returns_empty_lines` — 0-byte file → 200 with `lines: []`.
- `test_log_raw_returns_unmodified_content` — fixture with ANSI → response body still contains `\x1b` (raw, not stripped).
- `test_log_raw_content_disposition_attachment` — `Content-Disposition` header present.
- `test_log_raw_missing_file_404`.
- `test_log_stream_emits_lines_then_terminal` — running job, write a few lines to the file mid-stream, mark job `failed`, assert SSE messages include those lines and a final `event:status data:terminal`.
- `test_log_stream_heartbeat` — idle file, after 16s assert at least one `event:ping` was emitted (this test is slow — mark it `@pytest.mark.slow` or use a shorter heartbeat injectable for tests).
- `test_log_stream_uses_uuid_not_public_id` — request via both `DOC-NNNNN` and the UUID, both resolve to the same job's log.
- `test_path_traversal_rejected` — even though job IDs are UUIDs, attempt `../../etc/passwd` style → 404.

### 6. Update existing tests

```bash
grep -rn "complete_doc_job" tests/
```

Any test that asserts `complete_doc_job` produces *only* `lint_warnings` or empty `agent_output` must be updated. Do NOT delete tests; update assertions to match the new behaviour. If you find tests asserting "agent_output is None" — those become "agent_output is the captured log" or "is empty when no log file existed".

## Project Conventions

Read `tests/CLAUDE.md` HARD RULES:

- testcontainers ONLY (never live DB on port 5433)
- No `importlib.reload(orch.config)` — `monkeypatch.delenv` instead
- Replace `psycopg2` URL with `psycopg` in testcontainer URL
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`
- `DaemonEvent.metadata` Python attr is `event_metadata`
- Never mock the database in integration tests

Tests live under `tests/unit/`, `tests/integration/`, or `tests/dashboard/`. The unit tests above don't need a DB except `test_doc_service_complete_writes_output` (which uses real testcontainer DB).

## TDD Requirement

Write the test, run it, watch it FAIL on a stash of the impl branch (or against `main` directly via `git stash` of S01–S09's changes — but easier: just delete the assertion target and confirm the test fails for the right reason). Then run with the impl in place; confirm PASS. Document any test that doesn't trivially fail on `main`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

## Test Verification

```bash
make test-unit
make test-integration
make allure-integration   # if integration tests are wrapped behind allure target
```

Report PASS only when ALL pass.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "tests-impl",
  "work_item": "CR-00035",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_doc_job_poller_pid_liveness.py",
    "tests/unit/test_doc_report.py",
    "tests/unit/test_doc_service_complete_writes_output.py",
    "tests/unit/test_doc_job_status_cli.py",
    "tests/integration/test_doc_job_log_endpoints.py",
    "tests/fixtures/doc_jobs/doc_00004_replay.log",
    "tests/fixtures/doc_jobs/successful_run.log",
    "tests/fixtures/doc_jobs/process_exited_early.log"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Falsifiability spot-check: which tests would fail on main; any tests that needed updating in pre-existing files."
}
```
