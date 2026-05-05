# CR-00035_S03_Backend_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S03 — Dispatch unit
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt; `docker ps/inspect/logs` allowed. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT generate migrations — S01 already did. Do NOT add migration files. Do NOT run alembic against port 5433.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` — design (required reading: especially `## Desired Behavior` → "Dispatch fix", `## Implementation Plan` rows S03/S05, AC6/AC7/AC9, `## Notes`).
- `ai-dev/active/CR-00035/reports/CR-00035_S01_Database_report.md` — schema is in place.
- `orch/daemon/doc_job_poller.py` — current poller (read in full; key functions: `poll`, `_process_project`, `_launch_job`, `_select_skill`, `_build_agent_command`).
- `orch/cli/doc_commands.py` — pattern reference for `doc-update`, `doc-job-start`, `doc-job-done`. You will add a sibling `doc-job-status` command.
- `orch/cli/main.py` — CLI registration. Add `doc-job-status` here.
- `orch/cli/item_commands.py` `item_status` — pattern reference for an `--json` read-only status command.
- `orch/db/models.py` `DocGenerationJob`, `ProjectDoc`, `DocTypeGuide`, `DocInstanceGuide` — for the join.
- `commands/execute.md` — slash command file format reference.
- `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md` — files to update.

## Output Files

- `orch/daemon/doc_job_poller.py` — updated (`_build_agent_command` opencode branch only; no other changes)
- `orch/cli/doc_commands.py` — adds `doc_job_status` command
- `orch/cli/main.py` — registers `doc-job-status`
- `commands/doc-job.md` — **new file**
- `skills/iw-doc-generator/SKILL.md` — additive lifecycle section
- `skills/iw-doc-system/SKILL.md` — additive lifecycle section (identical to the above)
- `ai-dev/active/CR-00035/reports/CR-00035_S03_Backend_report.md`

## Context

You are implementing the **dispatch unit**: making doc-generation jobs actually invoke a doc-generation skill (instead of the broken `/execute` work-item path), and giving that skill a way to read the job's context. Four sub-deliverables:

(a) Replace the broken `_build_agent_command` opencode dispatch (one-line change to the slash command name).
(b) Add a `commands/doc-job.md` slash command.
(c) Add a new read-only CLI command `iw doc-job-status <job-id> [--json]` that returns the job + ProjectDoc context.
(d) Document the lifecycle in both doc-generation skills.

S05 (a separate step) handles the observability side (PID liveness, log capture, `complete_doc_job` rewrite, report module, aggregator). Do NOT touch those files in this step. There is **no cross-step plumbing** between S03 and S05 — S05 reconstructs `command_issued` from existing job/project fields rather than reading anything S03 writes.

Read the design doc end-to-end before starting. Pay close attention to:
- `## Current Behavior` — the actual failure trace
- `## Desired Behavior` → "Dispatch fix" subsection
- `## Acceptance Criteria` AC6, AC7, AC9
- `## Notes` — `iw doc-job-status` is the chosen context channel; SKILL.md updates are character-for-character identical between the two files

## Requirements

### 1. Fix `_build_agent_command` opencode dispatch

In `orch/daemon/doc_job_poller.py:_build_agent_command`, replace:

```python
cmd = f'opencode run "/execute {job.id}" --dangerously-skip-permissions'
```

with:

```python
cmd = f'opencode run "/doc-job {job.id}" --dangerously-skip-permissions'
```

Leave the claude-code branch unchanged. **Do NOT plumb the rendered command string back through `_launch_job` or `complete_doc_job`.** S05 reconstructs the `command_issued` field at report-build time from `job.skill_used` + `project.config["cli_tool"]` + `job.id` — the dispatch shape is now deterministic, so reconstruction is exact and avoids both an in-memory poller stash and a new schema column. This keeps S03 and S05 file-disjoint.

### 2. New slash command `commands/doc-job.md`

Mirror the shape of `commands/execute.md`:

```markdown
---
description: Execute a documentation generation job (e.g., /doc-job 727a12bd-...). Reads job context via `iw doc-job-status`, selects the doc-generation skill by editorial category, generates content via `iw doc-update`, closes via `iw doc-job-done`.
agent: build
---

Execute the documentation generation job specified by `<job-id>`.

1. Read job context: `uv run iw doc-job-status <job-id> --json`. The output includes `editorial_category`, `doc_id`, `project_id`, `doc_title`, `section_guides_snapshot`, and `guide_snapshot`. If the command exits non-zero, IMMEDIATELY close the job: `uv run iw doc-job-done <job-id> --error 'job context not found'` — do NOT proceed.
2. Select the skill based on `editorial_category`:
   - `guide`, `compliance`, `marketing`, `release` → `iw-doc-system`
   - everything else → `iw-doc-generator`
3. Invoke the chosen skill with the job context. The skill is responsible for:
   - producing markdown content
   - persisting it via `iw doc-update <doc-id> --content-file - --generated-by skill:<skill> --trigger-reason job:<job-id>` (project auto-resolved from the worktree's `.iw-orch.json`; `<doc-id>` is the inner `ProjectDoc.doc_id` slug, NOT the UUID)
   - closing the job via `iw doc-job-done <job-id>` on success or `iw doc-job-done <job-id> --error '<short message>'` on failure.
4. ALWAYS terminate by calling `iw doc-job-done` exactly once. Never leave the job in `running` state.
```

The exact prose may need adjusting to match how opencode parses these files — keep frontmatter `description:` and `agent:` fields. Use `agent: build` if that's what `commands/execute.md` uses; if `commands/execute.md` uses a different agent name, copy the same name (consistency wins over picking a "doc-generation" string that opencode may not recognise).

### 3. New CLI command `iw doc-job-status <job-id> [--json]`

Add to `orch/cli/doc_commands.py`. Pattern: mirror `item-status` and the existing `doc-job-start` / `doc-job-done`.

Behaviour:

- **Read-only**: opens a session, executes a read query, closes. NEVER updates a row.
- Looks up by either internal UUID or public ID (`DOC-NNNNN`). Mirror the resolution logic from `JobsAggregator.get_job` (or use it directly).
- Joins `DocGenerationJob` against `ProjectDoc` (on `doc_id`) to fetch `title` and `editorial_category`. If `doc_id` is None (job decoupled from a doc) — return None for those keys.
- Returns the following keys (JSON mode):
  - `id` (UUID)
  - `public_id` (`DOC-NNNNN` or null)
  - `project_id`
  - `doc_id` (or null)
  - `doc_title` (from joined `ProjectDoc.title`, or null)
  - `editorial_category` (from joined `ProjectDoc.editorial_category`, or null — use the actual column name; verify in `models.py`)
  - `status` (`queued` | `running` | `completed` | `failed`)
  - `skill_used` (or null)
  - `trigger_reason` (or null)
  - `agent_pid` (or null)
  - `started_at`, `completed_at`, `requested_at`, `created_at` (ISO-8601 strings or null)
  - `section_guides_snapshot` (dict of {section_name: guide_md} or null)
  - `guide_snapshot` (string or null)
- Without `--json`: pretty human-readable table (each key on its own line). With `--json`: a single JSON object printed to stdout, one line.
- Missing job-id: print `Error: doc-generation job '<id>' not found` to stderr, exit code 1.
- Use `click.echo`, not `print`. Use `ctx.exit(1)` for failure paths (consistent with other commands in this file).

Register in `orch/cli/main.py` next to `doc_job_start` / `doc_job_done`:

```python
from orch.cli.doc_commands import doc_job_done, doc_job_start, doc_job_status, doc_update, docs_export
...
cli.add_command(doc_job_status, name="doc-job-status")
```

### 4. Update both doc-generation skills

In `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md`, append a new section near the bottom (additive — do not rewrite existing content):

```markdown
## Job lifecycle (when invoked via `/doc-job <job-id>`)

When this skill is invoked by the platform's `DocJobPoller` (i.e. the slash command `/doc-job <job-id>` is issued), you are running inside a queued documentation generation job. Your responsibilities:

1. **Read the job context.** Run `uv run iw doc-job-status <job-id> --json`. The JSON output gives you `editorial_category`, `doc_id`, `project_id`, `doc_title`, `section_guides_snapshot`, and `guide_snapshot` — everything you need to produce the right content. If this command exits non-zero, do NOT proceed — close the job immediately with `iw doc-job-done <job-id> --error 'job context not found'`.

2. **Generate the document content** following the editorial guide rules described in the rest of this skill.

3. **Persist content via `iw doc-update`:**
   ```
   uv run iw doc-update <doc-id> \
     --content-file - \
     --generated-by skill:<this-skill-name> \
     --trigger-reason job:<job-id>
   ```
   `<doc-id>` is the inner `ProjectDoc.doc_id` slug (e.g. `code-index`) returned by `iw doc-job-status`, NOT the UUID. Project is auto-resolved from the worktree's `.iw-orch.json` — do not pass project as a positional arg (the CLI accepts only `<doc-id>` and will reject extra positionals). Pipe markdown via stdin. Run this exactly once for the job's target doc. Do NOT call `iw doc-update` for any unrelated doc.

4. **Close the job** by calling EXACTLY ONE of:
   - `uv run iw doc-job-done <job-id>` — on success
   - `uv run iw doc-job-done <job-id> --error '<one-line message>'` — on failure

   Failing to close the job leaves it in `running` until the daemon's PID-liveness probe (within ~60s if your process exits) or the 15-minute wall-clock stall guard kicks in. Always close.

5. **Do NOT call `iw item-status`, `iw step-start`, `iw step-done`, or any work-item-oriented CLI commands.** Doc jobs are not work items. Mistakenly calling these will succeed-but-do-nothing for the job's outcome.
```

The wording must be **identical** between the two SKILL.md files (the only difference between them is the rest of the file's content). After editing, run `diff <(awk '/^## Job lifecycle/,0' skills/iw-doc-generator/SKILL.md) <(awk '/^## Job lifecycle/,0' skills/iw-doc-system/SKILL.md)` and confirm zero diff in your report.

## Project Conventions

Read `orch/CLAUDE.md` for daemon and CLI patterns. Critical rules:

- The daemon is a single-threaded sync polling loop. Don't introduce async or threads.
- Sessions: `with self._session_factory() as db:` per logical work-unit. `db.commit()` explicitly. Never share a session across worktree boundaries.
- ORM driver is psycopg v3 (`psycopg[binary]`).
- Click commands: use the same decorator + group registration pattern as existing commands.
- For tests: testcontainers only, never live DB on 5433.

## TDD Requirement

S11 writes the tests for the new `iw doc-job-status` command. You SHOULD smoke-test it manually before declaring `complete`:

```bash
uv run iw doc-job-status DOC-00004 --json | python -m json.tool
```

Confirm output is well-formed JSON with the documented keys. Do NOT over-invest — S11 has the formal coverage.

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
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00035",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/doc_job_poller.py",
    "orch/cli/doc_commands.py",
    "orch/cli/main.py",
    "commands/doc-job.md",
    "skills/iw-doc-generator/SKILL.md",
    "skills/iw-doc-system/SKILL.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "agent: <name> chosen for commands/doc-job.md frontmatter and rationale; confirm SKILL.md lifecycle sections are byte-identical; confirm no cross-step plumbing of command_issued (S05 reconstructs)."
}
```
