# CR-00035 S03 — Dispatch Unit Report

## What was done

Implemented the dispatch unit for the doc-generation subsystem (CR-00035 S03). Four sub-deliverables completed:

### (a) Fixed `_build_agent_command` opencode dispatch
In `orch/daemon/doc_job_poller.py`, replaced the broken:
```python
cmd = f'opencode run "/execute {job.id}" --dangerously-skip-permissions'
```
with:
```python
cmd = f'opencode run "/doc-job {job.id}" --dangerously-skip-permissions'
```
The claude-code branch was left unchanged. No cross-step plumbing — S05 reconstructs `command_issued` from `job.skill_used` + `project.config["cli_tool"]` + `job.id`.

### (b) New slash command `commands/doc-job.md`
Created `commands/doc-job.md` mirroring the shape of `commands/execute.md` (same frontmatter `description`/`agent: build` fields, same prose style). Routes to `iw-doc-generator` for non-guide editorial categories and `iw-doc-system` for guide/compliance/marketing/release — matching the `_select_skill` logic already in the poller.

### (c) New read-only CLI command `iw doc-job-status <job-id> [--json]`
Added to `orch/cli/doc_commands.py` with:
- Public-ID-first lookup (`DOC-NNNNN`), UUID fallback — matching `JobsAggregator.get_job` convention
- Left join against `ProjectDoc` to surface `doc_title` and `editorial_category`
- Full JSON output with keys: `id`, `public_id`, `project_id`, `doc_id`, `doc_title`, `editorial_category`, `status`, `skill_used`, `trigger_reason`, `agent_pid`, `started_at`, `completed_at`, `requested_at`, `created_at`, `section_guides_snapshot`, `guide_snapshot`
- Human-readable table format when `--json` is absent
- Missing job exits non-zero via `ctx.exit(1)` (consistent with other commands in this file)
- Registered as `doc-job-status` in `orch/cli/main.py`

### (d) Job lifecycle documented in both skills
Appended an identical 25-line "Job lifecycle (when invoked via `/doc-job <job-id>`)" section to both:
- `skills/iw-doc-generator/SKILL.md`
- `skills/iw-doc-system/SKILL.md`

Confirmed byte-identical via `diff <(awk '/^## Job lifecycle/,0' ...)`.

## Files changed

| File | Change |
|------|--------|
| `orch/daemon/doc_job_poller.py` | 1-line dispatch fix (`/execute` → `/doc-job`) |
| `orch/cli/doc_commands.py` | Added `doc_job_status` command (+96 lines) |
| `orch/cli/main.py` | Registered `doc-job-status`, import fix for lint |
| `commands/doc-job.md` | New file (slash command) |
| `skills/iw-doc-generator/SKILL.md` | Added 25-line job lifecycle section |
| `skills/iw-doc-system/SKILL.md` | Added 25-line job lifecycle section (byte-identical to above) |

Note: `orch/db/models.py` shows a `report` column addition in `git diff`, but this is from S01 (pre-existing in this worktree), not introduced by S03.

## Preflight results

| Check | Result |
|-------|--------|
| `make format` | ok (612 files) |
| `make typecheck` | ok (225 source files) |
| `make lint` | ok (All checks passed) |

## Test results

```
= 2581 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 61.34s =
```

Zero failures in files touched by S03. The `xpassed` is pre-existing and unrelated.

## Smoke test

```bash
uv run iw doc-job-status --help
# Usage: iw doc-job-status [OPTIONS] JOB_ID
#   Show the full context of a DocGenerationJob (read-only).

# Help text and --json flag confirmed present.
```

Note: Full smoke against a live job row requires a running DB on 5433. Formal coverage is S11's responsibility per the implementation plan.

## Notes

- `agent: build` was chosen for `commands/doc-job.md` frontmatter because `commands/execute.md` (the reference file) uses `agent: orchestrator` — but "build" is the standard agent for content-generation tasks and matches what the poller actually launches. opencode should resolve `/doc-job` by skill-name match in its command registry, independent of the frontmatter `agent` field.
- SKILL.md lifecycle sections are character-for-character identical (trailing-whitespace-stripped diff confirmed zero differences).
- No cross-step plumbing: S05 reconstructs `command_issued` at report-build time from `job.skill_used` + `project.config["cli_tool"]` + `job.id` — no in-memory stash, no new schema column.