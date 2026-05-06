# CR-00035_S06_CodeReview_Backend_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Being Reviewed**: S05 (backend-impl — observability unit)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Read-only `alembic history / current / show`. No `upgrade/downgrade/stamp` against port 5433.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. AC2..AC5, the Notes section).
- `ai-dev/active/CR-00035/reports/CR-00035_S03_Backend_report.md` — confirms the deterministic dispatch shape that S05 reconstructs locally (no plumbing).
- `ai-dev/active/CR-00035/reports/CR-00035_S05_Backend_report.md`.
- All files in S05's `files_changed` (poller, doc_service, doc_report, log_capture, execution_report, aggregator).

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```
Any new violation in S05's changed files = **CRITICAL**.

## Review Checklist (per S05 sub-deliverable)

### (1) PID liveness probe

- Runs **before** the wall-clock stall sweep — otherwise the new "process exited" error message is never emitted (the stall sweep would catch the same job 14 minutes later as `failed_timeout` instead).
- Skips jobs whose `started_at` is younger than ~10 seconds (race protection vs. fork lag). Verify the threshold.
- `os.kill(pid, 0)`: `ProcessLookupError` → dead, `PermissionError` → alive, success → alive. No other exceptions silently treated as dead.
- Calls `complete_doc_job(job.id, error="agent process exited without calling iw doc-job-done", worktree_path=...)` — error string MUST match AC2 / the heuristic match string used by `build_execution_report`. Verify the call site does NOT pass `command_issued` or `cli_tool` — those are reconstructed inside `complete_doc_job`.
- Commits before processing the next project (preserve existing transaction boundaries).

### (2) `orch/doc_report.py`

- All four functions are pure (no DB, no global state, no ambient IO except a passed-in path).
- `read_log_tail` returns `(text, original_size, line_count)`. Truncation marker exact format `"[truncated: N bytes elided]\n"`. Empty/missing path returns `("", 0, 0)` cleanly (no exception).
- `parse_tool_calls` heuristic is documented. Pin one canonical example in a docstring.
- `build_execution_report` accepts the keyword args declared in S05's prompt and returns the dict matching AC4. Diagnosis heuristics implemented in priority order.
- ANSI strip is **factored** into `orch/utils/log_capture.py` and re-imported, NOT duplicated. Search for `re.compile(r'\\x1b'` across orch — should appear once.

### (3) `complete_doc_job`

- Signature has exactly one new kwarg: `worktree_path` (keyword-only, after `*`). It does NOT accept `cli_tool` or `command_issued` kwargs — those are reconstructed internally. Flag any extra kwargs as **HIGH (design drift)**.
- Idempotent: existing `if job.status in (completed, failed): return job` short-circuit is preserved. Calling twice does NOT re-truncate or rewrite agent_output / report.
- `worktree_path` falls back to `Project.repo_root` when None.
- Outcome classification matches the prompt's mapping (timeout / process_exited / agent_error / completed).
- **`command_issued` reconstruction** matches the dispatch shape `_build_agent_command` actually emits. Read both functions side-by-side; the strings must align (opencode → `opencode run "/doc-job <id>" --dangerously-skip-permissions`). Any drift is **HIGH** — the report would lie about what command was issued.
- `agent_output` always assigned (empty string allowed when log file missing).
- `report` always assigned on terminal state (must include all keys from AC4 even when log is empty).

### (4) Aggregator surfaces `report`

- `orch/jobs/aggregator.py:_build_doc_generation_raw` includes `"report": job.report` in its returned dict.
- The list-view path AND detail-view path both go through `_build_doc_generation_raw` (verify by reading `_fetch_doc_generation` and `_get_doc_generation`) — this is the single fix point per the existing I-00064 docstring at line 414.

### Scope discipline

- S05 must NOT touch any of: `_build_agent_command` opencode dispatch path, `commands/doc-job.md`, `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md`, `orch/cli/doc_commands.py`, `orch/cli/main.py`. Those belong to S03. Any incursion is a **HIGH (scope)** finding.

### General code quality

- No mock-DB usage in any test stubs that may have been added.
- No new `importlib.reload(orch.config)` calls.
- No async / threading introduced into the daemon loop.
- No silent exception swallows around `os.kill`.
- Type hints on new helper functions.

## Test Verification

```bash
make test-unit
make test-integration
```

Verify no regression. Report results accurately.

## Severity Levels

Standard. CRITICAL/HIGH/MEDIUM_FIXABLE trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
