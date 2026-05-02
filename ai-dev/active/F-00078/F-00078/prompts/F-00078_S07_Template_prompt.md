# F-00078_S07_Template_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step**: S07
**Agent**: template-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt. Same rules apply.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00078 --json`.
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Design document
- `skills/iw-item-analyze/SKILL.md` -- Current Claude Code-only skill (you'll migrate it)
- `skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md` -- Design skills you'll update
- `skills/iw-workflow/SKILL.md` -- Canonical agent table; you'll add a row for `self-assess-impl`
- `docs/misc/guide_to_create_opencode_skills.md` -- OpenCode skill format reference (migration checklist in §9)
- `docs/misc/guide_to_create_opencode_agents.md` -- OpenCode agent format (for context, not directly edited)
- `templates/design/` -- Master copies of design templates; you'll add `SelfAssess_Prompt_Template.md`
- `ai-dev/templates/` -- Per-project copy of design templates (synced via `iw sync-templates`)
- `.claude/skills/` -- Claude Code-compatible skills directory
- `projects.toml` -- Where the design skills will read the `self_assess` flag at generation time

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S07_Template_report.md` -- Step report
- Modified: `skills/iw-item-analyze/SKILL.md` (OpenCode-compatible + new file output contract)
- Modified: `skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md` (conditional self_assess step injection)
- Modified: `skills/iw-workflow/SKILL.md` (canonical agent table + the `self-assess-impl` slug; document soft-step behavior)
- Created: `templates/design/SelfAssess_Prompt_Template.md`
- Synced copies: `.claude/skills/iw-item-analyze/SKILL.md`, `.claude/skills/iw-new-feature/SKILL.md`, `.claude/skills/iw-new-cr/SKILL.md`, `.claude/skills/iw-new-incident/SKILL.md`, `.claude/skills/iw-workflow/SKILL.md`, `ai-dev/templates/SelfAssess_Prompt_Template.md`

## Context

You are the template/skill specialist for F-00078. Your job is the documentation surface that drives agent behavior:

1. **Migrate the existing `iw-item-analyze` skill from Claude Code-native to OpenCode-compatible** — same logic, but stripped of CC-only frontmatter, with `$ARGUMENTS` replaced by the `IW_ITEM_ID` env var, and a new file-output contract (instead of chat output).
2. **Update the three design skills** so their generated manifests inject the `self_assess` step automatically when the project's `projects.toml` has `self_assess = true`.
3. **Add a new prompt template** at `templates/design/SelfAssess_Prompt_Template.md` so the design skills have a stable boilerplate to reference when emitting the step's prompt file.
4. **Sync everything** to the parallel `.claude/skills/` and `ai-dev/templates/` locations.

Read the design document first. Pay attention to AC2 (skill injection condition), AC6 (output contract: report MD + findings JSON), and the "Notes" section about why the master copy stays in `skills/`.

## Requirements

### 1. Migrate `skills/iw-item-analyze/SKILL.md` to OpenCode-compatible

Per `docs/misc/guide_to_create_opencode_skills.md` §9 (Migrating Skills Between Claude Code and OpenCode):

**Frontmatter changes:**
- REMOVE `allowed-tools` (OpenCode skills inherit the agent's tools).
- REMOVE `argument-hint` (OpenCode skills don't receive arguments directly).
- KEEP `name`, `description`, `version`.
- ADD `compatibility: opencode` per the OpenCode guide's example.
- The `description` may stay verbose — it's still useful for both tools.

**Body changes:**
- Replace `$ARGUMENTS` with the `IW_ITEM_ID` env var (the executor exports it; S03 verified or added this).
- Phase 0 step 1 was "Parse $ARGUMENTS as the item ID. If missing or malformed, ask the user once." Change to: "Read the item ID from `$IW_ITEM_ID`. If unset, fall back to the first positional argument or stop with an error — the daemon launches this step with the env var set."
- Replace any `!`backticked`` shell preprocessing (none currently present in this skill, but verify with a grep).

**Output contract change (this is the substantive update):**

The skill currently outputs to chat. The new contract: write two files. Replace "Phase 3 — Output (chat, no file written)" with "Phase 3 — Output (two files written)":

- `ai-dev/work/<ID>/reports/<ID>_self_assess_report.md` — the human-readable narrative (the same structure currently described under Phase 3, but written to disk).
- `ai-dev/work/<ID>/reports/<ID>_self_assess_findings.json` — structured JSON. Schema:

```json
{
  "item_id": "F-00078",
  "bottom_line": "Single sentence — the most useful change to make.",
  "coverage_notes": "Sampled tail (last 500 lines) of S05 log (12 MB); read S01-S04 logs in full. DB telemetry: full.",
  "findings": [
    {
      "severity": "HIGH",
      "class": "environment",
      "target": "iw-ai-core",
      "title": "Per-worktree pyright reinstall on every Tests step",
      "recommendation": "Add pyright to main repo's dev dependencies",
      "evidence": [".worktrees/F-00078/ai-dev/logs/F-00078_S05_run1.log:142 — 'Installing pyright...'"],
      "effort": "S",
      "paste_prompt": "/iw-new-cr Add pyright to main repo's dev dependencies so worktrees inherit it; analyzed in F-00078 (see ai-dev/active/F-00078/reports/F-00078_self_assess_report.md). Target file: pyproject.toml. Effort: S."
    }
  ]
}
```

Constraints to add to the SKILL.md body (under "Constraints"):
- **MUST** write the two files atomically (write to a tempfile then rename, OR write directly if a partial write is acceptable for failures — the soft-step semantics tolerate partial output).
- **MUST** populate `target` with exactly `"iw-ai-core"` or `"project"` for every finding. Default to `"iw-ai-core"` for `class in {prompt, design, convention, agent, platform}`. Default to `"project"` for `class == environment` when the suggested fix is a dependency / config in the project root rather than in iw-ai-core. The skill body must say this explicitly.
- **MUST** populate `paste_prompt` with a one-line, copy-pasteable prompt: `/iw-new-cr <one-sentence description>` or `/iw-new-incident <one-sentence description>`, plus a short context tail referencing this analysis report.
- **MUST** include `coverage_notes` describing what was sampled vs read in full. Use selective reads (`tail -500`, `head -200`, `grep -E '^Error|^error|failed'`) for any log file > 1 MB. Spelunk fully only when a specific anomaly demands it.
- **MUST NOT** write any files outside `ai-dev/work/<ID>/reports/`. Read-only with respect to the rest of the worktree.
- The previous "no findings" output also writes the report file (with a one-line "no actionable patterns" body) AND a findings JSON with `findings: []`.

**Selective-read instruction (large logs):**
Add a new section "Phase 0.5 — Inventory log sizes":
```
Run: ls -la .worktrees/<ID>/ai-dev/logs/ | awk '{print $5, $9}'
For any log > 1 MB, plan to use:
  - tail -500 <log>      (last lines, where errors usually live)
  - head -200 <log>      (initial setup / env)
  - grep -nE 'Error|error:|failed|Permission denied|command not found' <log>
Only read the full file when a specific match in grep needs full context.
Record what you skipped in coverage_notes.
```

### 2. Update the three design skills

For each of `skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md`:

- Identify the "Generate Workflow Manifest" step (it varies by template — find the section that produces the `workflow-manifest.json` step list).
- Add a new conditional sub-step BEFORE generating the manifest:

```markdown
### Sub-step: Check project self_assess flag

Read the project's `projects.toml` entry to see if `self_assess = true`:

```bash
project_id=$(uv run iw current-project)
self_assess=$(python3 -c "import tomllib, sys; data = tomllib.loads(open('projects.toml').read()); print(data.get('projects', {}).get('$project_id', {}).get('self_assess', False))")
```

If `self_assess` is `True`, you MUST inject the following step into `workflow-manifest.json` IMMEDIATELY BEFORE the first `qv-gate` step (and before any `qv-browser` step):

```json
{
  "step": "S{NN}",
  "agent": "self-assess-impl",
  "step_type": "self_assess",
  "description": "Self-assessment of the just-completed item via the iw-item-analyze skill",
  "prompt": "prompts/{ID}_S{NN}_SelfAssess_prompt.md"
}
```

The agent slug is `self-assess-impl` — registered in `skills/iw-workflow/SKILL.md`'s canonical agent table (this PR adds it) and in `executor/step_executor_lib.sh` (S03 adds the launcher case). Do NOT use `self-assess` or `self_assess` as the agent slug — those will fail orchestrator validation.

And generate the corresponding prompt file at `prompts/{ID}_S{NN}_SelfAssess_prompt.md` by copying `ai-dev/templates/SelfAssess_Prompt_Template.md` and substituting `{ID}` and `{NN}`.

Renumber the QV gate steps that follow.
```

- Document this clearly in the skill so future maintainers see the conditional behavior.
- Make sure the skill's "Constraints" section includes: "MUST inject the self_assess step iff the project's projects.toml has `self_assess = true`. Determinism is required (Invariant 6 in F-00078)."

### 3. Add `templates/design/SelfAssess_Prompt_Template.md`

Create a new prompt template (based on the Implementation_Prompt_Template structure) that produces the per-item self_assess prompt. The body should:

- Repeat the Docker / Migration prohibition headers.
- Define input files: the item ID (via `$IW_ITEM_ID`), the worktree's logs dir, the item's reports dir.
- Define output files: `<reports_dir>/<ID>_self_assess_report.md` and `<reports_dir>/<ID>_self_assess_findings.json`.
- Instruct the agent to invoke the `iw-item-analyze` skill — be explicit about the invocation mechanism so the agent does not try to inline the procedure:
  > **Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which reads the same path). In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).
- Briefly summarize the soft-step semantics: "This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON."
- Include the Subagent Result Contract (similar to other prompts).

The template uses `{ID}` and `{NN}` placeholders for substitution by the design skills.

### 3b. Extend the canonical agent table in `skills/iw-workflow/SKILL.md`

Open `skills/iw-workflow/SKILL.md`. Locate the "Agent Mapping" section (around line 68) — it has a markdown table with two columns: `Agent Label (for filenames)` and `"agent" value (in manifest)`.

Add a new row, preserving the table's alignment style:

```
| SelfAssess | `self-assess-impl` |
```

Place it AFTER the `Template` row and BEFORE the `CodeReview_*` block, so implementation-style agents stay grouped together. Then, immediately after the table, add a short paragraph documenting the soft-step behavior:

> **`self-assess-impl` is a soft step.** Failures never block batch_item progression to `merging` — the daemon coerces a `failed` self_assess step to `completed` for batch progression while preserving the actual run status on the StepRun row. No fix cycles are launched for self_assess failures. The step is opt-in per project via `projects.toml`'s `self_assess = true` flag and is injected automatically by the design skills (`/iw-new-feature`, `/iw-new-cr`, `/iw-new-incident`).

Sync the change to `.claude/skills/iw-workflow/SKILL.md` (Section 4).

### 4. Sync to `.claude/skills/` and `ai-dev/templates/`

- Copy each modified `skills/<name>/SKILL.md` to `.claude/skills/<name>/SKILL.md`. The OpenCode-compatible frontmatter should still work for Claude Code (CC ignores extra fields like `compatibility`).
- Copy `templates/design/SelfAssess_Prompt_Template.md` to `ai-dev/templates/SelfAssess_Prompt_Template.md`.
- If the project has an `iw skills sync` and `iw sync-templates` command (it does — see `orch/cli/skills_commands.py`), document in your report whether the master + synced copies are byte-identical or whether the sync command should be run as part of merge.

### 5. Do NOT touch

- Anything in `orch/`, `dashboard/`, `tests/` — that's S03/S05/S09's job.
- The Alembic migration — that's S01's job.

## Project Conventions

Read `CLAUDE.md` (root), `docs/misc/guide_to_create_opencode_skills.md`, and the existing skill files for:

- Skill naming regex: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Frontmatter must include `name`, `description`; `name` must match directory name.
- Don't include emojis unless the file already has them.
- Match the exact heading style of the existing skill files (the master in `skills/` and the synced copy in `.claude/skills/` should be identical).

## TDD Requirement

This is a documentation step — TDD applies in spirit:

1. Add a small test (in `tests/unit/test_skill_files.py` or similar) that asserts:
   - `skills/iw-item-analyze/SKILL.md` no longer contains `allowed-tools` or `$ARGUMENTS`.
   - `skills/iw-item-analyze/SKILL.md` mentions `IW_ITEM_ID` and `_self_assess_findings.json`.
   - `templates/design/SelfAssess_Prompt_Template.md` exists and contains the `{ID}` placeholder.
   - `skills/iw-workflow/SKILL.md` contains the literal string `self-assess-impl` in the agent table.
   - Each of `skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md` mentions the conditional injection rule (search for the literal `self-assess-impl` and a reference to `projects.toml`).
   - For each modified skill: `.claude/skills/<name>/SKILL.md` matches `skills/<name>/SKILL.md` byte-for-byte (sync invariant).

2. Run the test before and after your changes to verify.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format` (markdown is not auto-formatted, but Python tests added in §4 are)
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Must pass.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "template-impl",
  "work_item": "F-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "skills/iw-item-analyze/SKILL.md",
    "skills/iw-new-feature/SKILL.md",
    "skills/iw-new-cr/SKILL.md",
    "skills/iw-new-incident/SKILL.md",
    "skills/iw-workflow/SKILL.md",
    "templates/design/SelfAssess_Prompt_Template.md",
    ".claude/skills/iw-item-analyze/SKILL.md",
    ".claude/skills/iw-new-feature/SKILL.md",
    ".claude/skills/iw-new-cr/SKILL.md",
    ".claude/skills/iw-new-incident/SKILL.md",
    ".claude/skills/iw-workflow/SKILL.md",
    "ai-dev/templates/SelfAssess_Prompt_Template.md",
    "tests/unit/test_skill_files.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "...",
  "blockers": [],
  "notes": "Document whether the master + synced copies are byte-identical and whether `iw skills sync` / `iw sync-templates` should be added to the merge pipeline."
}
```
