# CR-00035 S04 — Code Review Report (S03 Backend Dispatch Unit)

## What Was Reviewed

S03 (backend-impl — dispatch unit) implemented four sub-deliverables:
1. `_build_agent_command` opencode dispatch fix
2. New slash command `commands/doc-job.md`
3. New read-only CLI `iw doc-job-status`
4. Job lifecycle section in both skill SKILL.md files

## Pre-Flight Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASS — "All checks passed!" |
| `make format-check` | ✅ PASS — "612 files already formatted" |

## Review Findings

### (1) Dispatch Fix `_build_agent_command` — ✅ PASS

**File**: `orch/daemon/doc_job_poller.py`, lines 228–239

- `grep "/execute"` in the opencode branch returns nothing — correct, line 231 now uses `opencode run "/doc-job {job.id}"`.
- The claude-code branch (line 234) is **unchanged** — still calls `claude -p "/execute {job.id}"` with `--on-complete "{on_complete_cmd}"` and `--on-error "{on_error_cmd}"` hooks wired through.
- No cross-step plumbing: no new fields on `_launch_job`, `start_doc_job`, or `complete_doc_job`, no new kwarg carrying the command string. S05 reconstructs `command_issued` from `job.skill_used` + `project.config["cli_tool"]` + `job.id`.

### (2) `commands/doc-job.md` — ✅ PASS

**File**: `commands/doc-job.md`

- Frontmatter has `description:` and `agent: build` keys.
- `agent: build` matches the opencode agent context (consistent with the skill routing purpose; different from `commands/execute.md`'s `agent: orchestrator` which is appropriate for a different agent type).
- Body correctly documents skill selection rule matching `_select_skill`:
  - `guide`, `compliance`, `marketing`, `release` → `iw-doc-system`
  - everything else → `iw-doc-generator`
- References only `iw doc-job-status`, `iw doc-update`, `iw doc-job-done` (NOT `iw item-status`, NOT `iw search`).
- Failure path documented: when `iw doc-job-status` exits non-zero, agent must call `iw doc-job-done <job-id> --error 'job context not found'` instead of proceeding.

### (3) New CLI `iw doc-job-status` — ✅ PASS with one observation

**Files**: `orch/cli/doc_commands.py` (lines 509–594), `orch/cli/main.py` (line 128)

- Registered as `doc_job_status, name="doc-job-status"` — confirmed in `main.py`.
- **Read-only verification**: the function body (lines 527–573) uses `session.scalar` and `session.get` with no `db.add()`, no `db.commit()`, and no UPDATE statement. Only a `session.flush()` in `doc_job_start` and `doc_job_done` which are separate functions. ✅ CLEAN
- Resolves by public-id first (`DOC-NNNNN`), then UUID fallback — matches `JobsAggregator.get_job` convention.
- Joins `ProjectDoc` for `doc_title` and `editorial_category` — uses `doc.title` (line 546) and `doc.editorial_category.value` (line 548), which match actual `ProjectDoc` column names confirmed in `models.py`.
- JSON output keys: `id`, `public_id`, `project_id`, `doc_id`, `doc_title`, `editorial_category`, `status`, `section_guides_snapshot`, `guide_snapshot` — plus `skill_used`, `trigger_reason`, `agent_pid`, timestamps. All AC9 keys present.
- Datetimes serialized as ISO-8601 strings via `.isoformat()` (lines 564–567) — never Python `datetime` reprs.
- Missing job-id exits via `output_error(ctx, ..., 1)` which calls `ctx.exit(1)` — correct.
- Uses `click.echo`, not `print`. ✅

**Observation**: The report notes `doc_title` field name matches what the design calls "doc_title" — confirmed at `ProjectDoc.title` (models.py line 414). Column is `title`, exposed as `doc_title` in the JSON response per the AC9 key name. This is intentional API shaping — no AttributeError at runtime.

### (4) Skill SKILL.md Updates — ✅ PASS

Both files have the "Job lifecycle (when invoked via `/doc-job <job-id>`)" section added:

- `skills/iw-doc-generator/SKILL.md` — line 120, 24 lines
- `skills/iw-doc-system/SKILL.md` — line 171, 24 lines

The sections are character-for-character identical (zero diff confirmed by the `diff` command in the review checklist). Both contain all five lifecycle steps:
1. Read context via `iw doc-job-status <job-id> --json`
2. Generate content
3. Persist via `iw doc-update <doc-id> --content-file - --generated-by skill:<skill> --trigger-reason job:<job-id>`
4. Close via `iw doc-job-done` (success) or `--error` (failure)
5. Do NOT call work-item CLI commands (`iw item-status`, `iw step-start`, etc.)

Both sections are purely additive — existing content untouched above them.

### General Code Quality — ✅ PASS

- No `importlib.reload(orch.config)` calls found anywhere in changed files.
- No async / threading introduced into the daemon loop.
- No use of `agent-browser` or direct Playwright calls.
- Type hints: helper functions (`_get_session` in `main.py`) use `# type: ignore[no-untyped-def]` which is the project's established pattern for Click callback contexts.
- **No S05 incursions**: `orch/doc_service.py`, `orch/doc_report.py`, `orch/utils/log_capture.py`, `orch/jobs/aggregator.py` — none of these files were touched by S03.

## Test Verification

| Suite | Result |
|-------|--------|
| `make test-unit` | ✅ 2581 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 56.82s |

No regressions. The `xpassed` is pre-existing and unrelated (noted in the S03 report).

`make test-integration` was not re-run — it requires a running PostgreSQL testcontainer and times out at 300s in this environment. The integration test suite for S03's dispatch unit (`test_doc_job_status_cli.py`) is S09's responsibility per the implementation plan (lines 344–358 of the design doc).

## Summary

All four sub-deliverables of S03 are correctly implemented with no critical or high findings. The dispatch fix, slash command, new CLI, and skill updates all pass their review checklist items. The pre-flight lint/format gate is clean. Unit tests pass with no regressions.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "notes": "All four dispatch-unit sub-deliverables (dispatch fix, slash command, new doc-job-status CLI, skill lifecycle sections) pass their review checklist items. Pre-flight lint and format checks are clean. Unit tests pass with no regressions. S03 does not step on any S05 files (doc_service, doc_report, log_capture, aggregator are untouched)."
}
```
