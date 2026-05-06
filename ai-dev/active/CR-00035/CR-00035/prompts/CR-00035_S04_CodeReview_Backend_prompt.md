# CR-00035_S04_CodeReview_Backend_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Being Reviewed**: S03 (backend-impl — dispatch unit)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Read-only `alembic history / current / show`. No `upgrade/downgrade/stamp` against port 5433.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. AC6, AC7, AC9, the Notes section on `iw doc-job-status`).
- `ai-dev/active/CR-00035/reports/CR-00035_S03_Backend_report.md`.
- All files in S03's `files_changed` (poller, doc_commands.py, main.py, slash command, two skill files).

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S04_CodeReview_report.md`

## Context

S03 made four sub-deliverables in the dispatch unit. Review every one — a miss on any one will produce a CR that ships partially fixed.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```
Any new violation in S03's changed files = **CRITICAL**.

## Review Checklist (per S03 sub-deliverable)

### (1) Dispatch fix `_build_agent_command`

- opencode branch issues `/doc-job {job.id}` — verify by greppping for `/execute` in `_build_agent_command` (should not appear in the opencode branch anymore).
- Claude-code branch (`cli_tool == "claude"`) is **unchanged** — the `--on-complete "iw doc-job-done {job.id}"` and `--on-error` hooks still wire through.
- **No cross-step plumbing** of the rendered command string. `_build_agent_command` is changed in-place; no new fields on `_launch_job`, `start_doc_job`, or `complete_doc_job` were added by S03 to carry the command string to S05. Per the design, S05 reconstructs `command_issued` at report-build time from `job.skill_used` + `project.config["cli_tool"]` + `job.id`. Flag any in-memory stash, new column, or kwarg added in S03 for this purpose as **HIGH (scope)**.

### (2) `commands/doc-job.md`

- Frontmatter has `description:` and `agent:` keys.
- The `agent:` value is consistent with `commands/execute.md` (so opencode's loader recognises it).
- Body documents skill selection rule (matches `_select_skill` exactly: `guide`/`compliance`/`marketing`/`release` → `iw-doc-system`; otherwise `iw-doc-generator`).
- References `iw doc-job-status`, `iw doc-update`, `iw doc-job-done` — and ONLY these (NOT `iw item-status`, NOT `iw search`).
- Failure path: when `iw doc-job-status` exits non-zero, the agent must call `iw doc-job-done <job-id> --error '...'` instead of proceeding. Verify this branch is documented.

### (3) New CLI `iw doc-job-status`

- File: added to `orch/cli/doc_commands.py` next to `doc_job_start` / `doc_job_done`.
- Registration: added to `orch/cli/main.py` (`cli.add_command(doc_job_status, name="doc-job-status")`).
- **Read-only**: no `db.add(...)`, no `db.commit()` after a mutation, no UPDATE statement. Verify by reading the function body.
- Resolves by either UUID or `DOC-NNNNN` public_id.
- Joins `ProjectDoc` for `doc_title` and `editorial_category` — the actual column names in `ProjectDoc` may differ; confirm the query uses real columns (no AttributeError at runtime).
- JSON output (`--json` flag) emits ALL keys listed in AC9 (`id`, `public_id`, `project_id`, `doc_id`, `doc_title`, `editorial_category`, `status`, `section_guides_snapshot`, `guide_snapshot` — plus `skill_used`, `trigger_reason`, `agent_pid`, timestamps).
- Datetimes serialised as ISO-8601 strings (or null) — never as Python `datetime` reprs.
- Missing job-id exits non-zero with a clear `Error:` message to stderr.
- Uses `click.echo`, not `print`. Uses `ctx.exit(1)` (not `sys.exit`) for failure paths.

### (4) Both skill SKILL.md updates

- Same lifecycle section appended to both `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md`.
- Section is additive; existing content untouched. Diff cleanly.
- Contains all five lifecycle steps from the design (read context via `iw doc-job-status`, generate, doc-update, doc-job-done, do-not-call-item-CLI).
- The two files' lifecycle sections are character-for-character identical. Verify with:

```bash
diff <(awk '/^## Job lifecycle/,0' skills/iw-doc-generator/SKILL.md) \
     <(awk '/^## Job lifecycle/,0' skills/iw-doc-system/SKILL.md)
```

Zero output = pass. Any diff = HIGH finding.

### General code quality

- No new `importlib.reload(orch.config)` calls.
- No async / threading introduced into the daemon loop.
- No use of `agent-browser` or direct Playwright calls.
- Type hints on the new CLI command's helper functions.
- No work touching `orch/doc_service.py`, `orch/doc_report.py`, `orch/utils/log_capture.py`, or `orch/jobs/aggregator.py` — those belong to S05 and editing them here would step on S05's diff. Flag any incursion as **HIGH (scope)**.

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
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
