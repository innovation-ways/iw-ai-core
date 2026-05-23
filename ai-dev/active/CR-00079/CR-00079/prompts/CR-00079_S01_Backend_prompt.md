# CR-00079_S01_Backend_prompt

**Work Item**: CR-00079 — Generate smaller, single-concern workflow steps in the design-creation skills
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Do NOT run any command that changes Docker container/volume/network state.
This step touches only Markdown files — you should not need Docker at all.
`./ai-core.sh` / `make` targets and read-only `docker ps|inspect|logs` are
allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migration** and no schema change. If your work appears to
need one, STOP and raise a blocker.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00079 --json`.
- `ai-dev/work/CR-00079/CR-00079_CR_Design.md` — the design document. **Read it in full first** (especially Current Behavior, Desired Behavior, and all three ACs).
- `skills/iw-new-feature/SKILL.md`, `skills/iw-new-incident/SKILL.md`, `skills/iw-new-cr/SKILL.md` — the three design-creation skills to edit.
- `skills/iw-workflow/SKILL.md` — the workflow orchestration rules; the canonical step-granularity rule goes here.
- `templates/design/` — the master design-doc templates (`Feature_Design_Template.md`, `Issue_Design_Template.md`, `CR_Design_Template.md`).
- `CLAUDE.md` — note the skill-sync and template-sync rules.

## Output Files

- The four `skills/.../SKILL.md` files (modified)
- The affected `templates/design/*` files (modified)
- The synced `.claude/skills/**` and `ai-dev/templates/**` copies (regenerated)
- `ai-dev/work/CR-00079/reports/CR-00079_S01_Backend_report.md` — step report.

## Context

You are implementing all of CR-00079 — a Markdown-only guidance change. The
design-creation skills currently emit workflow manifests with no step-size
guidance, so a single step can bundle many unrelated concerns and overflow an
agent's context window (the CR-00076 S01 monolith — see the design's Current
Behavior). This step adds an explicit step-granularity rule and checklist so
generated packages default to small, single-concern steps.

## Requirements

### 1. Canonical step-granularity rule in `iw-workflow`

Add to `skills/iw-workflow/SKILL.md` a concise, **canonical** step-granularity
rule — the single source of truth the other three skills reference. It must
state, concretely:

- An implementation step targets **one cohesive concern** — roughly one module
  or one closely-related file group.
- Work spanning several unrelated concerns is **split across multiple steps**.
- **Many small steps are preferred over one large step** — small steps keep
  per-step agent context bounded (the failure mode is one large step, not many
  small ones).
- Documentation / skill / plan updates that ride along with code changes get
  **their own step**, not a tail bolted onto an implementation step.

Place it near the manifest-schema / step-definition section so authors see it
where they define steps.

### 2. Step-granularity rule + sizing checklist in the three design-creation skills

In each of `skills/iw-new-feature/SKILL.md`, `skills/iw-new-incident/SKILL.md`,
and `skills/iw-new-cr/SKILL.md`, in the section where the author drafts the
Implementation/Fix/Change Plan and the workflow manifest, add:

- A short statement of the step-granularity rule that **references the canonical
  rule in `iw-workflow`** (do not copy a divergent wording — point to the
  canonical one and summarise).
- A concrete **step-sizing checklist** the author applies to each proposed step,
  for example:
  - Does this step touch more than one unrelated area / module? → split it.
  - Would the step's own description need more than a handful of unrelated
    numbered sub-deliverables? → split it.
  - Do docs / skill / plan updates ride along with code changes in this step?
    → give them their own step.
  - Would one agent run have to read+edit+test across several modules? → split it.

Keep the wording consistent across the three skills (the same rule, phrased for
each item type). Match each skill's existing heading style and tone.

### 3. Template pointer

In each affected master template under `templates/design/` (the Feature, Issue,
and CR design templates), add a **one-line pointer** to the step-granularity
rule in the "Agents and Execution Order" section — so the rule is visible at
the moment the author fills in the step table. One line; do not bloat the
templates.

### 4. Sync

Run `uv run iw sync-skills` and `uv run iw sync-templates` so that:

- `.claude/skills/iw-new-feature/`, `.claude/skills/iw-new-incident/`,
  `.claude/skills/iw-new-cr/`, `.claude/skills/iw-workflow/` are byte-identical
  to their `skills/` masters.
- `ai-dev/templates/` is byte-identical to the affected `templates/design/` masters.

Verify with `diff -q` on at least the four skill files and the three templates.
If `sync-skills` only updates a subset, use `--force` for the affected skills.

### 5. Cross-repo propagation note

Per `CLAUDE.md`, `iw-*` skill edits must also reach the sibling repos
(IW-AI-DEV, InnoForge). You are in a worktree and **cannot** write outside it —
do NOT attempt to. Instead, **explicitly flag** in your report, under `notes`,
that an operator must propagate the four edited skills to the sibling repos
after merge.

## Project Conventions

Read `CLAUDE.md`. Skills master copies live in `skills/`; never hand-edit
`.claude/skills/` — edit the master and sync. Match the existing Markdown
heading and list style of each file.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run and fix anything reported:

1. `make format`
2. `make lint` — zero errors (a Markdown-only diff should not affect it; if it
   does, you touched something out of scope — STOP and reassess).

`make typecheck` is not meaningful for a Markdown-only change — record it as
`skipped:markdown-only` in the contract.

## Test Verification

There is no code and no test surface in this CR. Do NOT write or run tests.
Verify your work by re-reading each edited file and confirming the rule and
checklist are present, concrete, and consistent, and that the synced copies
are byte-identical (`diff -q`).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "skipped:markdown-only", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "n/a — Markdown guidance change, no test surface",
  "tdd_red_evidence": "n/a — Markdown guidance/template change, no production logic",
  "blockers": [],
  "notes": "OPERATOR FOLLOW-UP: propagate the four edited iw-* skills to the IW-AI-DEV and InnoForge repos. Confirm .claude/skills + ai-dev/templates byte-identical to masters."
}
```

## Lifecycle Commands

Start: `uv run iw step-start CR-00079 --step S01`
On success: write the report, then
`uv run iw step-done CR-00079 --step S01 --report ai-dev/work/CR-00079/reports/CR-00079_S01_Backend_report.md`
On failure: `uv run iw step-fail CR-00079 --step S01 --reason "<brief reason>"`
You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
