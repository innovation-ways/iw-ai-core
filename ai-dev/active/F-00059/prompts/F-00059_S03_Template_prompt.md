# F-00059_S03_Template_prompt

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S03
**Agent**: template-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutation command.
See S01 banner for the full list.

---

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — see *Scope*, *AC1*, *AC2*, *AC7*, and *Notes / Forbidden-term regex*
- `ai-dev/templates/Feature_Design_Template.md` — existing template style reference
- `ai-dev/templates/Issue_Design_Template.md` and `CR_Design_Template.md` — same
- `skills/iw-new-feature/SKILL.md` — existing skill master to extend
- `skills/iw-new-incident/SKILL.md` — same
- `skills/iw-new-cr/SKILL.md` — same
- `skills/iw-review-design/SKILL.md` — existing review skill master

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S03_Template_report.md` (new)
- `ai-dev/templates/Functional_Design_Template.md` (new — canonical master)
- `templates/design/Functional_Design_Template.md` (new — synced mirror)
- `skills/iw-new-feature/SKILL.md` (modified)
- `skills/iw-new-incident/SKILL.md` (modified)
- `skills/iw-new-cr/SKILL.md` (modified)
- `skills/iw-review-design/SKILL.md` (modified)

## Context

S01 added the DB columns; S02 populates them at `iw register` time. This step
makes sure every new work item created via the `/iw-new-*` skills produces a
valid functional doc in the first place, and that `/iw-review-design` blocks
approval of invalid ones.

## Requirements

### 1. New template file — `Functional_Design_Template.md`

Create the file at `ai-dev/templates/Functional_Design_Template.md` and an
identical copy at `templates/design/Functional_Design_Template.md` (the sync
mirror used by other projects). Structure:

```markdown
# {ID} — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body under 500 words.
-->

## Why

Two to four sentences explaining why this work was requested — the problem,
the trigger (user complaint, incident, new requirement, …), and the goal.

## What Changed (for the User)

A bullet list or short prose describing what a user, operator, or dashboard
viewer experiences that is different after this work shipped. Focus on
observable behaviour, not mechanics.

## How It Behaves

The functional flow, happy path, and notable edge cases, in plain English.
A non-engineer reading this should be able to predict what the system does in
common scenarios.

## Out of Scope

One or two bullets naming things a reader might reasonably assume are part of
this work but are NOT. Omit this section entirely if the scope is obvious.
```

The HTML comment at the top is the author guidance; it is rendered harmlessly
by the dashboard's markdown pipeline.

### 2. Skill updates — `iw-new-feature`, `iw-new-incident`, `iw-new-cr`

For each of the three SKILL.md masters under `skills/`:

- In the "Create Design Document" step (Step 5 in `iw-new-feature` today, same
  conceptual step in the other two), add a parallel instruction to copy
  `ai-dev/templates/Functional_Design_Template.md` to
  `ai-dev/active/<ID>/<ID>_Functional.md` and fill in the `Why / What Changed /
  How It Behaves / Out of Scope` sections drafted from the user's intake
  conversation and the technical design's Description + Scope sections.
- Require the AI to keep the file under 500 words and to avoid implementation
  detail (file paths, class names, SQL, code fences).
- In the File Manifest section the skill tells the author to fill in, add the
  row for `ai-dev/active/<ID>/<ID>_Functional.md`.
- In the "Register in Platform" step, point out that `iw register` auto-loads
  the adjacent `<ID>_Functional.md` (S02's work) — no extra flag needed.

Keep the existing step numbering intact; the functional doc creation is a
substep inside the existing Create-Design-Document step, not a new numbered
step, to minimise drift with the documented sequence.

### 3. Skill update — `iw-review-design`

Extend the review checklist with a "Functional Design Document" section. It
runs structural checks (BLOCKING) and content checks (WARNING unless human
dismissed).

**Structural checks (BLOCKING — the skill must report a blocking error and
must not approve):**

- File `ai-dev/active/<ID>/<ID>_Functional.md` exists.
- File body contains H1 `# <ID> — Functional Design` (or variant with en-dash).
- File body contains H2 `## Why`.
- File body contains H2 `## What Changed (for the User)`.
- File body contains H2 `## How It Behaves`.
- Word count (prose, excluding the HTML comment and headings) is under 500.

**Content checks (WARNING — reported but non-blocking unless the reviewer
explicitly dismisses):**

- File-extension regex: `\b[A-Za-z0-9_./-]+\.(py|md|js|ts|tsx|sql|html|json|toml|yaml|yml)\b`.
- Path-fragment regex: `\b(orch|dashboard|scripts|ai-dev|tests|skills|templates|executor)/`.
- SQL-DDL regex (case-insensitive): `\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|INSERT\s+INTO|SELECT\s+\*)\b`.
- Fenced code block (three backticks) anywhere in the body.

Document the structural-vs-content distinction plainly in the skill so a
human reviewer understands when they can waive a warning.

### 4. Sync across projects

Note in the report that after this step merges, an operator must run
`iw skills sync` for every project in `projects.toml` (innoforge, cv) to
propagate the new skill bodies and the new template to those repos. This is
not automated by the pipeline — it's an operator step.

## Project Conventions

Read `CLAUDE.md`. Skill masters under `skills/` are synced to each project's
`.claude/skills/` by `iw skills sync`. Template masters under
`ai-dev/templates/` are mirrored to `templates/design/` for the same sync flow.
Match existing skill markdown style: numbered steps, bold labels, code blocks
for bash examples.

## TDD Requirement

Unit tests for the `/iw-review-design` validation logic (structural + content
regex) live in S05's `tests/unit/test_review_design_functional_validation.py`.
This step's own tests focus on static correctness:

- After this step lands, `grep '## Why' ai-dev/templates/Functional_Design_Template.md` must succeed.
- `grep 'Functional_Design_Template' skills/iw-new-feature/SKILL.md` must succeed (and same for incident/cr).
- `grep 'functional doc' skills/iw-review-design/SKILL.md` must succeed.

Report these greps in the S03 report.

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — pass.
2. `make test-unit` — pass (no regressions; the new validator tests are in S05).
3. No markdown lint errors in the new template (the dashboard's markdown
   renderer must accept it — simplest proof: open the file in a pre-merge
   sanity check).

## Subagent Result Contract

Standard JSON with `step: "S03"`, `agent: "template-impl"`, `work_item: "F-00059"`.
