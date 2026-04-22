# CR-00016_S01_Template_prompt

**Work Item**: CR-00016 — Agent prompt hardening — Docker is off-limits rule
**Step**: S01
**Agent**: template-impl

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md` — Design (Rule Text verbatim, AC1–AC2, AC4)
- Templates to update (11 files, all in `ai-dev/templates/`):
  - `Implementation_Prompt_Template.md`
  - `CodeReview_Prompt_Template.md`
  - `CodeReview_FIX_Prompt_Template.md`
  - `CodeReview_Final_Prompt_Template.md`
  - `CodeReview_FIX_Final_Prompt_Template.md`
  - `QualityValidation_Template.md`
  - `QualityValidation_FIX_Prompt_Template.md`
  - `QVBrowser_Prompt_Template.md`
  - `CR_Design_Template.md`
  - `Feature_Design_Template.md`
  - `Issue_Design_Template.md`
- `.claude/skills/iw-workflow/SKILL.md` — orchestrator skill
- `skills/iw-workflow/SKILL.md` (if it exists — master copy, keep in sync)

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S01_Template_report.md`
- `docs/IW_AI_Core_Agent_Constraints.md` (new)
- All 11 templates above, updated
- `.claude/skills/iw-workflow/SKILL.md`, updated
- Possibly `skills/iw-workflow/SKILL.md` (if it exists)

## Context

You're writing the authoritative agent-constraints policy document and embedding the Docker rule into every prompt template and the orchestrator skill. The rule text is in the design doc — copy it verbatim, do not paraphrase.

Read the design doc first — especially the **Rule Text** section (to be embedded verbatim) and AC2 (grep sanity test requires the exact marker).

## Requirements

### 1. Create `docs/IW_AI_Core_Agent_Constraints.md`

Structure the doc to support future rules (not just Docker). Target skeleton:

```markdown
# IW AI Core — Agent Constraints

This document is the authoritative policy for what AI agents running inside
this project are allowed and forbidden to do. Every agent-prompt template
and every `CLAUDE.md` references this file. Rules here take precedence over
step-specific instructions that contradict them.

## Scope

Applies to every agent invoked by the IW workflow, including:
- Step agents run by the daemon (`database-impl`, `backend-impl`, `api-impl`,
  `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`).
- Review agents (`code-review-impl`, `code-review-final-impl`).
- Quality-gate agents (`qv-gate`, `qv-browser`).
- Any sub-agent spawned via `Agent(...)` tool calls.

## Rules

### R1. ⛔ Docker is off-limits

<insert the exact Rule Text block from the design doc — verbatim, no edits>

### R2. (reserved for future rules)

---

## Adding rules

New rules must:
- Have an ID (R2, R3, ...) for stable cross-referencing.
- Name a unique marker phrase used by the grep sanity test in
  `tests/integration/test_agent_constraints_coverage.py`.
- Link from every touch-point (templates + CLAUDE.md files).

## Related

- `docs/IW_AI_Core_DB_Setup.md` — the 2026-04-22 data-loss incident that
  motivated R1.
- `CLAUDE.md` (and sub-CLAUDE.md files) — per-layer critical rules.
```

### 2. Update all 11 prompt templates

For each template in `ai-dev/templates/`:

- Insert the Docker rule block **verbatim** as a top-level `##` section, placed near the beginning of the document (after the front-matter / title but before specific step instructions). A good position is right after the first `---` separator.
- Do NOT paraphrase, reformat, or abbreviate the rule text. The grep sanity test in S05 matches on the exact marker phrase `⛔ Docker is off-limits`.
- For the design templates (`CR_Design_Template.md`, `Feature_Design_Template.md`, `Issue_Design_Template.md`), the rule is still included — these are read by designers/agents creating design packages, and the constraint applies during design as well.
- For each file, verify no other `##` section with the same title already exists (shouldn't, but guard against idempotency breakage).

### 3. Update `.claude/skills/iw-workflow/SKILL.md`

Read the file. Find the section that lists constraints/rules for the orchestrator (common names: "Constraints", "Hard Rules", "Invariants"; if none exists, add a new section near the top after the skill description).

Insert a short block:

```markdown
## Global agent constraints

All step agents MUST respect the rules in `docs/IW_AI_Core_Agent_Constraints.md`.
The orchestrator MUST surface these rules when enumerating constraints for a
step prompt if it is possible to do so programmatically. At minimum: the
"⛔ Docker is off-limits" rule applies to every agent without exception.

Summary of the Docker rule (full text in the policy doc):
- No docker kill / stop / rm / restart
- No docker compose up / down / restart (and the docker-compose v1 variants)
- No docker volume rm / prune
- No docker system / container / image prune
- Exceptions: testcontainers (pytest fixtures), read-only introspection
  (docker ps / inspect / logs), invoking ./ai-core.sh or make targets.
```

### 4. Keep `skills/iw-workflow/` master copy in sync

If `skills/iw-workflow/SKILL.md` exists as a master file (per the user's memory note, master skills live in `skills/` and get synced via `iw skills sync`), apply the same edit there. If the two files diverge in other ways, preserve both variants' existing content and only add the new constraint block.

Document in your report whether `skills/` was modified, and if so, which files.

### 5. Do NOT touch CLAUDE.md files

CLAUDE.md updates are S03's responsibility. Leave them untouched in S01.

### 6. Do NOT touch other docs

`docs/IW_AI_Core_DB_Setup.md` cross-reference is S03's job.

## Project Conventions

- Markdown style: match existing templates (backtick-fenced code blocks, `##` for section headers, `-` for bullets).
- Preserve existing front-matter and structure in each template — add the new section, do not reorganize.
- Link style: relative paths (`docs/...`).

## TDD Requirement

No automated tests in this step — S05 creates the grep sanity test. Your own verification is a manual grep after edits:

```bash
grep -l "⛔ Docker is off-limits" ai-dev/templates/*.md
# Should list all 11 files.

grep -c "⛔ Docker is off-limits" ai-dev/templates/Implementation_Prompt_Template.md
# Should be >= 1 for every template.

grep "Docker" .claude/skills/iw-workflow/SKILL.md
# Should list the constraint block.
```

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — pass.
2. Manual grep check above returns the expected hits.
3. Open one random template and one random design template and verify the rule reads cleanly in context (no formatting breakage).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "template-impl",
  "work_item": "CR-00016",
  "completion_status": "complete",
  "files_changed": [
    "docs/IW_AI_Core_Agent_Constraints.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
    "... (10 more templates)",
    ".claude/skills/iw-workflow/SKILL.md",
    "skills/iw-workflow/SKILL.md"  // if applicable
  ],
  "tests_passed": true,
  "test_summary": "lint green; marker phrase present in all 11 templates + iw-workflow SKILL",
  "blockers": [],
  "notes": "skills/iw-workflow/SKILL.md {did|did not} exist."
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S01
# edit ...
uv run iw step-done CR-00016 --step S01 --report ai-dev/active/CR-00016/reports/CR-00016_S01_Template_report.md
```
